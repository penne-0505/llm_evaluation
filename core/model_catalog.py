"""Model list fetch and cache"""

from __future__ import annotations

import importlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.app_paths import AppPaths
from core.provider_config_store import ProviderConfigStore
from core.secrets_store import SecretsStore

logger = logging.getLogger(__name__)


class ModelCatalog:
    """Fetch and cache provider model lists."""

    CACHE_PATH: Path | None = None
    # 固定枠。registry 追加分は動的にマージする（openrouter は重複取得しない）。
    PROVIDERS = ("openrouter", "lmstudio")
    DEFAULT_TTL_SECONDS = 21600
    TTL_ENV_NAME = "LLM_BENCHMARK_MODEL_CATALOG_TTL_SECONDS"
    FETCH_TIMEOUT_SECONDS = 20

    @classmethod
    def _cache_path(cls) -> Path:
        return cls.CACHE_PATH or AppPaths.model_cache_file()

    @classmethod
    def _legacy_cache_path(cls) -> Path:
        return AppPaths.repo_path("models", "models.json")

    @classmethod
    def _bundled_cache_path(cls) -> Path:
        return AppPaths.bundled_path("models", "models.json")

    @classmethod
    def _registry_entries(cls) -> List[Any]:
        """registry 一覧。FILE_PATH 未設定時も load するが、テストは FILE_PATH を差し替える。"""
        from core.provider_registry import ProviderRegistry

        return ProviderRegistry.list_providers()

    @classmethod
    def _catalog_provider_ids(cls, cached: Optional[Dict[str, Any]] = None) -> List[str]:
        ids: List[str] = list(cls.PROVIDERS)
        seen = set(ids)
        try:
            for entry in cls._registry_entries():
                if entry.id in seen:
                    continue
                ids.append(entry.id)
                seen.add(entry.id)
        except Exception as exc:
            logger.warning("model catalog registry list failed: %s", exc)

        if cached:
            for provider_id in cached.get("providers", {}):
                if provider_id not in seen:
                    ids.append(provider_id)
                    seen.add(provider_id)
        return ids

    @classmethod
    def update(
        cls, force: bool = False, ttl_seconds: int | None = None
    ) -> Dict[str, Any]:
        """Fetch model lists and update the cache."""
        cached = cls._load_cache()
        api_keys = SecretsStore.load_existing()
        effective_ttl = cls._resolve_ttl_seconds(ttl_seconds)

        if not force and cls._is_cache_fresh(cached, effective_ttl):
            logger.info("model catalog cache hit ttl_seconds=%s", effective_ttl)
            return cls._build_catalog_from_cache(cached, api_keys)

        catalog = {
            "updated_at": cls._now_iso(),
            "providers": {},
            "errors": {},
            "missing_keys": [],
        }

        fetch_specs: Dict[str, Tuple[Any, Any]] = {}

        # --- fixed: openrouter / lmstudio ---
        openrouter_key = api_keys.get("openrouter") or SecretsStore.load_provider_secret(
            "openrouter"
        )
        if not openrouter_key:
            catalog["missing_keys"].append("OPENROUTER_API_KEY")
        else:
            fetch_specs["openrouter"] = (openrouter_key, cls._fetch_openrouter_models)

        base_url = cls._lmstudio_base_url()
        api_token = api_keys.get("lmstudio")
        if base_url:
            fetch_specs["lmstudio"] = (
                {"base_url": base_url, "api_token": api_token},
                cls._fetch_lmstudio_models,
            )

        # --- registry openai_compatible / anthropic（openrouter は上で取得済み）---
        try:
            registry_entries = cls._registry_entries()
        except Exception as exc:
            logger.warning("model catalog registry load failed: %s", exc)
            registry_entries = []

        for entry in registry_entries:
            if entry.id == "openrouter":
                continue
            key = SecretsStore.load_provider_secret(entry.id) or api_keys.get(entry.id)
            if not key:
                catalog["missing_keys"].append(
                    SecretsStore.env_key_for_provider(entry.id)
                )
                continue

            if entry.kind == "openai_compatible":
                if not entry.base_url:
                    catalog["errors"][entry.id] = "base_url is not configured"
                    continue
                fetch_specs[entry.id] = (
                    {
                        "provider_id": entry.id,
                        "base_url": entry.base_url,
                        "api_key": key,
                    },
                    cls._fetch_openai_compatible_models,
                )
            elif entry.kind == "anthropic":
                fetch_specs[entry.id] = (
                    {"provider_id": entry.id, "api_key": key},
                    cls._fetch_anthropic_models_for_provider,
                )

        fetched_models: Dict[str, List[Dict[str, Any]]] = {}
        fetch_errors: Dict[str, str] = {}
        if fetch_specs:
            with ThreadPoolExecutor(max_workers=len(fetch_specs)) as executor:
                future_map = {
                    provider: executor.submit(fetcher, api_key)
                    for provider, (api_key, fetcher) in fetch_specs.items()
                }
                for provider, future in future_map.items():
                    try:
                        fetched_models[provider] = future.result(
                            timeout=cls.FETCH_TIMEOUT_SECONDS
                        )
                    except Exception as e:
                        logger.warning(
                            "model catalog fetch failed provider=%s error=%s",
                            provider,
                            e,
                        )
                        fetch_errors[provider] = str(e)

        provider_ids = cls._catalog_provider_ids(cached)
        # ensure freshly fetched providers appear even if not in registry snapshot
        for provider in fetch_specs:
            if provider not in provider_ids:
                provider_ids.append(provider)

        for provider in provider_ids:
            entries = fetched_models.get(provider, [])
            error = fetch_errors.get(provider)

            if error:
                catalog["errors"][provider] = error
                cached_entries = cls._cached_provider_entries(cached, provider)
                if cached_entries:
                    entries = cached_entries
                elif provider not in cls.PROVIDERS and provider not in fetched_models:
                    # anthropic 等: API 非対応時は空 + note
                    if "anthropic" in provider or error:
                        catalog["errors"][provider] = (
                            f"{error}; model list unavailable (use manual model id)"
                        )

            normalized_entries = cls._normalize_model_entries(entries)
            catalog["providers"][provider] = {
                "models": [entry["id"] for entry in normalized_entries],
                "entries": normalized_entries,
            }

        cls._write_cache(catalog)
        logger.info(
            "model catalog updated providers=%s missing_keys=%s errors=%s",
            list(catalog["providers"].keys()),
            catalog["missing_keys"],
            list(catalog["errors"].keys()),
        )
        return catalog

    @classmethod
    def _build_catalog_from_cache(
        cls, cached: Dict[str, Any], api_keys: Dict[str, str]
    ) -> Dict[str, Any]:
        catalog = {
            "updated_at": cached.get("updated_at", cls._now_iso()),
            "providers": {},
            "errors": {},
            "missing_keys": [],
        }

        for provider in cls._catalog_provider_ids(cached):
            api_key = api_keys.get(provider) or SecretsStore.load_provider_secret(
                provider
            )
            models = cls._cached_provider_models(cached, provider)
            has_access = bool(api_key)
            if provider == "lmstudio":
                has_access = bool(cls._lmstudio_base_url())

            if not has_access:
                if provider != "lmstudio":
                    catalog["missing_keys"].append(cls._provider_env_key(provider))
                models = []

            catalog["providers"][provider] = {
                "models": cls._unique_sorted(models),
                "entries": cls._cached_provider_entries(cached, provider),
            }

        return catalog

    @classmethod
    def collect_models(cls, catalog: Dict[str, Any]) -> List[str]:
        """Collect all model options from catalog."""
        options: List[str] = []
        providers = catalog.get("providers", {})
        for provider in providers:
            models = providers.get(provider, {}).get("models", [])
            for model in models:
                if model not in options:
                    options.append(model)
        return options

    @classmethod
    def _fetch_openai_models(cls, api_key: str) -> List[Dict[str, Any]]:
        data = cls._fetch_json(
            url="https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        return [{"id": item.get("id")} for item in data.get("data", []) if item.get("id")]

    @classmethod
    def _fetch_anthropic_models(cls, api_key: str) -> List[Dict[str, Any]]:
        data = cls._fetch_json(
            url="https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        return [{"id": item.get("id")} for item in data.get("data", []) if item.get("id")]

    @classmethod
    def _fetch_anthropic_models_for_provider(
        cls, settings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        provider_id = str(settings.get("provider_id") or "anthropic")
        api_key = str(settings.get("api_key") or "")
        raw = cls._fetch_anthropic_models(api_key)
        models: List[Dict[str, Any]] = []
        prefix = f"{provider_id}/"
        for item in raw:
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            prefixed = model_id if model_id.startswith(prefix) else f"{prefix}{model_id}"
            models.append({"id": prefixed})
        return models

    @classmethod
    def _fetch_openai_compatible_models(
        cls, settings: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        provider_id = str(settings.get("provider_id") or "").strip()
        base_url = str(settings.get("base_url") or "").rstrip("/")
        api_key = str(settings.get("api_key") or "")
        if not provider_id or not base_url or not api_key:
            raise RuntimeError("openai_compatible fetch requires provider_id, base_url, api_key")
        data = cls._fetch_json(
            url=f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        models: List[Dict[str, Any]] = []
        prefix = f"{provider_id}/"
        for item in data.get("data", []):
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            prefixed = model_id if model_id.startswith(prefix) else f"{prefix}{model_id}"
            models.append({"id": prefixed})
        return models

    @classmethod
    def _fetch_gemini_models(cls, api_key: str) -> List[Dict[str, Any]]:
        genai = cls._load_gemini_module()
        client = getattr(genai, "Client")(api_key=api_key)
        models = []
        try:
            for model in client.models.list():
                name = getattr(model, "name", "")
                if not name:
                    name = str(model)
                if not name:
                    continue
                if name.startswith("models/"):
                    name = name.split("/", 1)[1]
                models.append({"id": name})
        finally:
            close_method = getattr(client, "close", None)
            if callable(close_method):
                close_method()
        return models

    @classmethod
    def _fetch_openrouter_models(cls, api_key: str) -> List[Dict[str, Any]]:
        data = cls._fetch_json(
            url="https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        models = []
        for item in data.get("data", []):
            model_id = item.get("id")
            if not model_id:
                continue
            normalized_id = (
                model_id if model_id.startswith("openrouter/") else f"openrouter/{model_id}"
            )
            models.append(
                {
                    "id": normalized_id,
                    "pricing": {
                        "prompt": item.get("pricing", {}).get("prompt"),
                        "completion": item.get("pricing", {}).get("completion"),
                    },
                }
            )
        return models

    @classmethod
    def _fetch_lmstudio_models(cls, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        base_url = str(settings.get("base_url") or "").rstrip("/")
        api_token = str(settings.get("api_token") or "").strip()
        headers: Dict[str, str] = {}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        data = cls._fetch_json(url=f"{base_url}/models", headers=headers)

        models = []
        for item in data.get("data", []):
            model_id = str(item.get("id") or "").strip()
            if not model_id:
                continue
            prefixed_id = (
                model_id if model_id.startswith("lmstudio/") else f"lmstudio/{model_id}"
            )
            models.append({"id": prefixed_id})
        return models

    @classmethod
    def _fetch_json(cls, url: str, headers: Dict[str, str]) -> Dict[str, Any]:
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                payload = response.read().decode("utf-8")
                return json.loads(payload)
        except (HTTPError, URLError) as e:
            raise RuntimeError(f"HTTP error: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"JSON decode error: {e}") from e

    @classmethod
    def _load_cache(cls) -> Dict[str, Any]:
        candidates: list[Path] = []
        for path in (
            cls._cache_path(),
            cls._bundled_cache_path(),
            cls._legacy_cache_path(),
        ):
            if path not in candidates:
                candidates.append(path)

        for path in candidates:
            if not path.exists():
                continue
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
        return {}

    @classmethod
    def _resolve_ttl_seconds(cls, ttl_seconds: int | None) -> int:
        if ttl_seconds is not None:
            return max(0, int(ttl_seconds))

        env_value = os.getenv(cls.TTL_ENV_NAME)
        if env_value is None:
            return cls.DEFAULT_TTL_SECONDS

        try:
            return max(0, int(env_value))
        except ValueError:
            return cls.DEFAULT_TTL_SECONDS

    @classmethod
    def _is_cache_fresh(cls, cached: Dict[str, Any], ttl_seconds: int) -> bool:
        if ttl_seconds <= 0:
            return False

        updated_at = cached.get("updated_at")
        if not isinstance(updated_at, str):
            return False

        try:
            updated_at_dt = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return False

        age = datetime.now(timezone.utc) - updated_at_dt
        return age.total_seconds() < ttl_seconds

    @staticmethod
    def _load_gemini_module() -> Any:
        return importlib.import_module("google.genai")

    @classmethod
    def _write_cache(cls, catalog: Dict[str, Any]) -> None:
        cache_path = cls._cache_path()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @classmethod
    def _cached_provider_models(
        cls, cached: Dict[str, Any], provider: str
    ) -> List[str]:
        models = cached.get("providers", {}).get(provider, {}).get("models", [])
        if models:
            return models
        return [entry["id"] for entry in cls._cached_provider_entries(cached, provider)]

    @classmethod
    def _cached_provider_entries(
        cls, cached: Dict[str, Any], provider: str
    ) -> List[Dict[str, Any]]:
        entries = cached.get("providers", {}).get(provider, {}).get("entries", [])
        return cls._normalize_model_entries(entries)

    @classmethod
    def find_model_entry(cls, provider: str, model: str) -> Optional[Dict[str, Any]]:
        for entry in cls._cached_provider_entries(cls._load_cache(), provider):
            entry_id = str(entry.get("id", ""))
            if entry_id == model:
                return entry
            if provider == "openrouter" and entry_id.removeprefix("openrouter/") == model.removeprefix("openrouter/"):
                return entry
        return None

    @classmethod
    def _normalize_model_entries(cls, models: List[Any]) -> List[Dict[str, Any]]:
        entries: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in models or []:
            if isinstance(item, str):
                model_id = item
                entry: Dict[str, Any] = {"id": model_id}
            elif isinstance(item, dict):
                model_id = str(item.get("id") or "")
                if not model_id:
                    continue
                entry = {"id": model_id}
                pricing = item.get("pricing")
                if isinstance(pricing, dict):
                    entry["pricing"] = {
                        "prompt": pricing.get("prompt"),
                        "completion": pricing.get("completion"),
                    }
            else:
                continue

            if model_id in seen:
                continue
            seen.add(model_id)
            entries.append(entry)

        entries.sort(key=lambda row: row["id"])
        return entries

    @staticmethod
    def _provider_env_key(provider: str) -> str:
        try:
            return SecretsStore.env_key_for_provider(provider)
        except Exception:
            mapping = {
                "openrouter": "OPENROUTER_API_KEY",
                "lmstudio": "LMSTUDIO_API_TOKEN",
            }
            return mapping.get(provider, provider.upper())

    @staticmethod
    def _lmstudio_base_url() -> str | None:
        config = ProviderConfigStore.load_provider("lmstudio")
        base_url = str(config.get("base_url") or "").strip() or os.getenv(
            "LMSTUDIO_BASE_URL"
        )
        if not base_url:
            return None
        normalized = base_url.rstrip("/")
        if normalized.endswith("/v1"):
            return normalized
        return f"{normalized}/v1"

    @staticmethod
    def _unique_sorted(models: List[str]) -> List[str]:
        return sorted({m for m in models if m})

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

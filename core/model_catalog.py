"""Model list fetch and cache"""

from __future__ import annotations

import importlib
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from core.app_paths import AppPaths
from core.secrets_store import SecretsStore

logger = logging.getLogger(__name__)


class ModelCatalog:
    """Fetch and cache provider model lists."""

    CACHE_PATH: Path | None = None
    PROVIDERS = ("openai", "anthropic", "gemini", "openrouter")
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

        fetch_specs: Dict[str, tuple[str, Any]] = {}
        for provider in cls.PROVIDERS:
            if provider == "openai":
                api_key = api_keys.get("openai")
                if not api_key:
                    catalog["missing_keys"].append("OPENAI_API_KEY")
                else:
                    fetch_specs[provider] = (api_key, cls._fetch_openai_models)

            elif provider == "anthropic":
                api_key = api_keys.get("anthropic")
                if not api_key:
                    catalog["missing_keys"].append("ANTHROPIC_API_KEY")
                else:
                    fetch_specs[provider] = (api_key, cls._fetch_anthropic_models)

            elif provider == "gemini":
                api_key = api_keys.get("gemini")
                if not api_key:
                    catalog["missing_keys"].append("GEMINI_API_KEY")
                else:
                    fetch_specs[provider] = (api_key, cls._fetch_gemini_models)

            elif provider == "openrouter":
                api_key = api_keys.get("openrouter")
                if not api_key:
                    catalog["missing_keys"].append("OPENROUTER_API_KEY")
                else:
                    fetch_specs[provider] = (api_key, cls._fetch_openrouter_models)

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

        for provider in cls.PROVIDERS:
            entries = fetched_models.get(provider, [])
            error = fetch_errors.get(provider)

            if error:
                catalog["errors"][provider] = error
                cached_entries = cls._cached_provider_entries(cached, provider)
                if cached_entries:
                    entries = cached_entries

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

        for provider in cls.PROVIDERS:
            api_key = api_keys.get(provider)
            models = cls._cached_provider_models(cached, provider)
            if not api_key:
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
        for provider in cls.PROVIDERS:
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
        mapping = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }
        return mapping.get(provider, provider.upper())

    @staticmethod
    def _unique_sorted(models: List[str]) -> List[str]:
        return sorted({m for m in models if m})

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

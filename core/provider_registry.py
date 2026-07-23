"""名前付きプロバイダ registry（公式経路の組み込みプリセット含む）。"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Literal, Optional

from core.app_paths import AppPaths

ProviderKind = Literal["openai_compatible", "anthropic"]
PricingProfile = Literal["openrouter", "openai", "anthropic", "google", "none"]

# intent: DEC-004/010 (Core/openai-compat-anthropic-providers) — builtin id と lmstudio/or を予約
RESERVED_PROVIDER_IDS = frozenset(
    {
        "openrouter",
        "openai",
        "google-ai-studio",
        "anthropic",
        "lmstudio",
        "or",
    }
)

OPENROUTER_PRESET_ID = "openrouter"
OPENAI_PRESET_ID = "openai"
GOOGLE_AI_STUDIO_PRESET_ID = "google-ai-studio"
ANTHROPIC_PRESET_ID = "anthropic"

OPENROUTER_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
GOOGLE_AI_STUDIO_DEFAULT_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")

_BUILTIN_IDS = frozenset(
    {
        OPENROUTER_PRESET_ID,
        OPENAI_PRESET_ID,
        GOOGLE_AI_STUDIO_PRESET_ID,
        ANTHROPIC_PRESET_ID,
    }
)


@dataclass
class ProviderEntry:
    id: str
    display_name: str
    kind: ProviderKind
    pricing_profile: PricingProfile
    base_url: Optional[str] = None
    profile: Optional[str] = None
    builtin: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if data.get("base_url") is None:
            data.pop("base_url", None)
        if data.get("profile") is None:
            data.pop("profile", None)
        return data

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "ProviderEntry":
        kind = str(raw.get("kind") or "").strip()
        if kind not in ("openai_compatible", "anthropic"):
            raise ValueError(f"unsupported provider kind: {kind!r}")
        pricing_profile = str(raw.get("pricing_profile") or "none").strip()
        if pricing_profile not in (
            "openrouter",
            "openai",
            "anthropic",
            "google",
            "none",
        ):
            raise ValueError(f"unsupported pricing_profile: {pricing_profile!r}")
        provider_id = str(raw.get("id") or "").strip()
        display_name = str(raw.get("display_name") or "").strip()
        if not provider_id or not display_name:
            raise ValueError("provider id and display_name are required")
        base_url = raw.get("base_url")
        profile = raw.get("profile")
        return cls(
            id=provider_id,
            display_name=display_name,
            kind=kind,  # type: ignore[arg-type]
            pricing_profile=pricing_profile,  # type: ignore[arg-type]
            base_url=str(base_url).strip() if base_url else None,
            profile=str(profile).strip() if profile else None,
            builtin=bool(raw.get("builtin", False)),
        )


class ProviderRegistry:
    """App-local JSON に名前付きプロバイダを永続化する。"""

    FILE_PATH: Path | None = None
    SCHEMA_VERSION = 1

    @classmethod
    def _file_path(cls) -> Path:
        return cls.FILE_PATH or AppPaths.provider_registry_file()

    @classmethod
    def builtin_presets(cls) -> List[ProviderEntry]:
        # intent: DEC-010 (Core/openai-compat-anthropic-providers) — 集合 A のみ常駐 seed
        return [
            ProviderEntry(
                id=OPENROUTER_PRESET_ID,
                display_name="OpenRouter",
                kind="openai_compatible",
                pricing_profile="openrouter",
                base_url=OPENROUTER_DEFAULT_BASE_URL,
                profile="openrouter",
                builtin=True,
            ),
            ProviderEntry(
                id=OPENAI_PRESET_ID,
                display_name="OpenAI",
                kind="openai_compatible",
                pricing_profile="openai",
                base_url=OPENAI_DEFAULT_BASE_URL,
                builtin=True,
            ),
            ProviderEntry(
                id=GOOGLE_AI_STUDIO_PRESET_ID,
                display_name="Google AI Studio",
                kind="openai_compatible",
                pricing_profile="google",
                base_url=GOOGLE_AI_STUDIO_DEFAULT_BASE_URL,
                builtin=True,
            ),
            ProviderEntry(
                id=ANTHROPIC_PRESET_ID,
                display_name="Anthropic",
                kind="anthropic",
                pricing_profile="anthropic",
                builtin=True,
            ),
        ]

    @classmethod
    def openrouter_preset(cls) -> ProviderEntry:
        return cls.builtin_presets()[0]

    @classmethod
    def slugify(cls, display_name: str) -> str:
        text = unicodedata.normalize("NFKD", display_name)
        text = text.encode("ascii", "ignore").decode("ascii")
        text = text.lower().strip()
        text = _SLUG_RE.sub("-", text).strip("-")
        return text or "provider"

    @classmethod
    def allocate_id(cls, display_name: str, existing_ids: Iterable[str]) -> str:
        base = cls.slugify(display_name)
        taken = set(existing_ids) | RESERVED_PROVIDER_IDS
        if base not in taken:
            return base
        suffix = 2
        while f"{base}-{suffix}" in taken:
            suffix += 1
        return f"{base}-{suffix}"

    @classmethod
    def default_pricing_profile(
        cls,
        *,
        kind: ProviderKind,
        base_url: Optional[str] = None,
        profile: Optional[str] = None,
    ) -> PricingProfile:
        if profile == "openrouter":
            return "openrouter"
        if kind == "anthropic":
            return "anthropic"
        url = (base_url or "").lower()
        if "openai.com" in url:
            return "openai"
        if "generativelanguage" in url or "googleapis.com" in url:
            return "google"
        return "none"

    @classmethod
    def ensure_builtins(
        cls, providers: List[ProviderEntry]
    ) -> tuple[List[ProviderEntry], bool]:
        """欠落している builtin を補完し、安定順に並べる。変更があれば True。"""
        by_id = {entry.id: entry for entry in providers}
        changed = False
        for preset in cls.builtin_presets():
            existing = by_id.get(preset.id)
            if existing is None:
                by_id[preset.id] = preset
                changed = True
                continue
            if not existing.builtin:
                existing.builtin = True
                changed = True
            if preset.id == OPENROUTER_PRESET_ID:
                if existing.profile != "openrouter":
                    existing.profile = "openrouter"
                    changed = True
                if not existing.base_url:
                    existing.base_url = OPENROUTER_DEFAULT_BASE_URL
                    changed = True
                if existing.pricing_profile != "openrouter":
                    existing.pricing_profile = "openrouter"
                    changed = True
            elif preset.id == OPENAI_PRESET_ID and not existing.base_url:
                existing.base_url = OPENAI_DEFAULT_BASE_URL
                changed = True
            elif preset.id == GOOGLE_AI_STUDIO_PRESET_ID and not existing.base_url:
                existing.base_url = GOOGLE_AI_STUDIO_DEFAULT_BASE_URL
                changed = True
            elif preset.id == ANTHROPIC_PRESET_ID and existing.kind != "anthropic":
                existing.kind = "anthropic"
                changed = True

        builtin_order = [p.id for p in cls.builtin_presets()]
        builtins: List[ProviderEntry] = []
        customs: List[ProviderEntry] = []
        seen: set[str] = set()
        for bid in builtin_order:
            entry = by_id.get(bid)
            if entry and bid not in seen:
                builtins.append(entry)
                seen.add(bid)
        for entry in providers:
            if entry.id in seen:
                continue
            customs.append(entry)
            seen.add(entry.id)
        ordered = builtins + customs
        if [e.id for e in ordered] != [e.id for e in providers]:
            changed = True
        return ordered, changed

    @classmethod
    def load(cls) -> List[ProviderEntry]:
        path = cls._file_path()
        if not path.exists():
            providers = cls.builtin_presets()
            cls._write(providers)
            return list(providers)

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            providers = cls.builtin_presets()
            cls._write(providers)
            return list(providers)

        providers = cls._parse_providers(raw)
        providers, changed = cls.ensure_builtins(providers)
        if changed or not providers:
            if not providers:
                providers = cls.builtin_presets()
            cls._write(providers)
        return providers

    @classmethod
    def get(cls, provider_id: str) -> Optional[ProviderEntry]:
        target = str(provider_id or "").strip()
        if not target:
            return None
        for entry in cls.load():
            if entry.id == target:
                return entry
        return None

    @classmethod
    def list_providers(cls) -> List[ProviderEntry]:
        return cls.load()

    @classmethod
    def add(
        cls,
        *,
        display_name: str,
        kind: ProviderKind,
        base_url: Optional[str] = None,
        profile: Optional[str] = None,
        pricing_profile: Optional[PricingProfile] = None,
        provider_id: Optional[str] = None,
    ) -> ProviderEntry:
        name = str(display_name or "").strip()
        if not name:
            raise ValueError("display_name is required")
        if kind not in ("openai_compatible", "anthropic"):
            raise ValueError(f"unsupported provider kind: {kind!r}")

        providers = cls.load()
        existing_ids = {entry.id for entry in providers}
        if provider_id is not None:
            candidate = str(provider_id).strip()
            if not re.fullmatch(r"[a-z0-9-]+", candidate):
                raise ValueError(f"invalid provider id: {candidate!r}")
            if candidate in RESERVED_PROVIDER_IDS:
                raise ValueError(f"provider id is reserved: {candidate!r}")
            if candidate in existing_ids:
                raise ValueError(f"provider id already exists: {candidate!r}")
            new_id = candidate
        else:
            new_id = cls.allocate_id(name, existing_ids)

        resolved_profile = pricing_profile or cls.default_pricing_profile(
            kind=kind, base_url=base_url, profile=profile
        )
        entry = ProviderEntry(
            id=new_id,
            display_name=name,
            kind=kind,
            pricing_profile=resolved_profile,
            base_url=str(base_url).strip() if base_url else None,
            profile=str(profile).strip() if profile else None,
            builtin=False,
        )
        providers.append(entry)
        cls._write(providers)
        return entry

    @classmethod
    def update(
        cls,
        provider_id: str,
        *,
        display_name: Optional[str] = None,
        base_url: Optional[str] = None,
        clear_base_url: bool = False,
        pricing_profile: Optional[PricingProfile] = None,
        profile: Optional[str] = None,
    ) -> ProviderEntry:
        # intent: DEC-004 (Core/openai-compat-anthropic-providers) — id は作成後不変
        providers = cls.load()
        index = next(
            (i for i, entry in enumerate(providers) if entry.id == provider_id),
            None,
        )
        if index is None:
            raise KeyError(f"provider not found: {provider_id!r}")

        entry = providers[index]
        if display_name is not None:
            name = display_name.strip()
            if not name:
                raise ValueError("display_name cannot be empty")
            entry.display_name = name
        if clear_base_url:
            if entry.builtin and entry.id in (
                OPENROUTER_PRESET_ID,
                OPENAI_PRESET_ID,
                GOOGLE_AI_STUDIO_PRESET_ID,
            ):
                raise ValueError(f"cannot clear base_url for builtin preset: {entry.id}")
            entry.base_url = None
        elif base_url is not None:
            entry.base_url = str(base_url).strip() or None
        if pricing_profile is not None:
            if pricing_profile not in (
                "openrouter",
                "openai",
                "anthropic",
                "google",
                "none",
            ):
                raise ValueError(f"unsupported pricing_profile: {pricing_profile!r}")
            entry.pricing_profile = pricing_profile
        if profile is not None:
            if (
                entry.builtin
                and entry.id == OPENROUTER_PRESET_ID
                and profile != "openrouter"
            ):
                raise ValueError("openrouter preset profile is immutable")
            entry.profile = str(profile).strip() or None

        providers[index] = entry
        cls._write(providers)
        return entry

    @classmethod
    def delete(cls, provider_id: str) -> None:
        providers = cls.load()
        index = next(
            (i for i, entry in enumerate(providers) if entry.id == provider_id),
            None,
        )
        if index is None:
            raise KeyError(f"provider not found: {provider_id!r}")
        entry = providers[index]
        # intent: DEC-010 (Core/openai-compat-anthropic-providers) — builtin は常駐（key のみ消去可）
        if entry.builtin or entry.id in _BUILTIN_IDS:
            raise ValueError(f"cannot delete builtin provider: {entry.id}")
        providers.pop(index)
        cls._write(providers)

    @classmethod
    def _parse_providers(cls, raw: Any) -> List[ProviderEntry]:
        if not isinstance(raw, dict):
            return []
        items = raw.get("providers")
        if not isinstance(items, list):
            return []
        providers: List[ProviderEntry] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                entry = ProviderEntry.from_dict(item)
            except ValueError:
                continue
            if entry.id in seen:
                continue
            seen.add(entry.id)
            providers.append(entry)
        return providers

    @classmethod
    def _write(cls, providers: List[ProviderEntry]) -> None:
        payload = {
            "version": cls.SCHEMA_VERSION,
            "providers": [entry.to_dict() for entry in providers],
        }
        path = cls._file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

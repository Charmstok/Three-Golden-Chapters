from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class ProviderConfig:
    """Provider connection info."""

    type: str
    base_url: str
    api_key: str


@dataclass(frozen=True)
class ChatParams:
    """Chat API parameters (configurable in llm.json profiles)."""

    temperature: float = 0.2
    max_tokens: int = 10000
    timeout_s: int = 120
    thinking: Dict[str, Any] = field(default_factory=lambda: {"type": "disabled"})


@dataclass(frozen=True)
class ChatRunConfig:
    """Resolved runtime config for one chat invocation."""

    provider_name: str
    provider: ProviderConfig
    model: str
    params: ChatParams


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_api_key(value_or_env: str) -> str:
    value_or_env = str(value_or_env or "")
    return os.getenv(value_or_env) or value_or_env


def find_default_llm_config() -> Optional[Path]:
    for name in ("llm.json", "llm.example.json"):
        p = Path(name)
        if p.exists():
            return p
    return None


def load_provider_config(path: Path, provider_name: str) -> Tuple[ProviderConfig, str]:
    """Return (provider_config, provider_default_model)."""

    data = _load_json(path)
    providers = data.get("providers") or {}
    p = providers.get(provider_name)
    if not isinstance(p, dict):
        raise RuntimeError(f"Provider not found in {path}: {provider_name}")

    api_key = _resolve_api_key(p.get("api_key") or "")
    if not api_key:
        raise RuntimeError(f"Missing api_key for provider={provider_name}")

    provider = ProviderConfig(
        type=str(p.get("type") or ""),
        base_url=str(p.get("base_url") or ""),
        api_key=api_key,
    )
    default_model = str(p.get("model") or "")
    return provider, default_model


def load_chat_run_config(
    path: Path,
    *,
    profile: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> ChatRunConfig:
    """Resolve provider/model/params from llm.json.

    Preferred config style (supports many models):

      {
        "providers": { ... },
        "profiles": {
          "phase2": {
            "provider": "volc_doubao",
            "model": "doubao-seed-...",
            "params": {"temperature": 0.2, "max_tokens": 10000, "timeout_s": 120}
          }
        },
        "default_profile": "phase2"
      }

    Backward compatible:
    - If profiles are missing, fall back to providers.<provider>.model.
    """

    data = _load_json(path)

    profiles = data.get("profiles") or {}
    default_profile = data.get("default_profile")

    chosen_profile = profile or default_profile
    if not chosen_profile and "phase2" in profiles:
        chosen_profile = "phase2"
    if profile and chosen_profile and chosen_profile not in profiles:
        raise RuntimeError(f"Profile not found in {path}: {chosen_profile}")
    if (not profile) and default_profile and chosen_profile and chosen_profile not in profiles:
        raise RuntimeError(f"default_profile not found in {path}: {chosen_profile}")

    profile_obj = profiles.get(chosen_profile) if chosen_profile else None

    provider_name: Optional[str] = None
    chosen_model = ""
    params_obj: Dict[str, Any] = {}

    if isinstance(profile_obj, dict):
        provider_name = str(profile_obj.get("provider") or "") or None
        chosen_model = str(profile_obj.get("model") or "")
        params_obj = profile_obj.get("params") or {}

    # CLI overrides (optional)
    if provider:
        provider_name = provider
    if model:
        chosen_model = model

    # Provider fallback
    if not provider_name:
        default_provider = data.get("default_provider")
        if isinstance(default_provider, str) and default_provider:
            provider_name = default_provider
        else:
            providers = data.get("providers") or {}
            if not providers:
                raise RuntimeError(f"No providers in {path}")
            provider_name = next(iter(providers.keys()))

    prov, provider_default_model = load_provider_config(path, provider_name)

    # Model fallback
    if not chosen_model:
        chosen_model = provider_default_model
    if not chosen_model:
        raise RuntimeError(
            f"Missing model. Set providers.{provider_name}.model or profiles.<name>.model in {path}"
        )

    params = ChatParams(
        temperature=float(params_obj.get("temperature", ChatParams.temperature)),
        max_tokens=int(params_obj.get("max_tokens", ChatParams.max_tokens)),
        timeout_s=int(params_obj.get("timeout_s", ChatParams.timeout_s)),
        thinking=dict(params_obj.get("thinking", ChatParams().thinking)),
    )

    return ChatRunConfig(
        provider_name=provider_name,
        provider=prov,
        model=chosen_model,
        params=params,
    )

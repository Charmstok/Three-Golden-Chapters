from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class ProviderConfig:
    type: str
    base_url: str
    api_key: str
    model: str


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_provider_config(path: Path, provider_name: str) -> ProviderConfig:
    """
    读取 llm.json，并返回指定 provider 的配置。

    api_key 字段既可以直接写 key，也可以写“环境变量名”（推荐），脚本会优先从环境变量取值。
    """
    data = _load_json(path)
    providers = data.get("providers") or {}
    p = providers.get(provider_name)
    if not isinstance(p, dict):
        raise RuntimeError(f"Provider not found in {path}: {provider_name}")

    api_key_value = str(p.get("api_key") or "")
    api_key = os.getenv(api_key_value) or api_key_value
    if not api_key:
        raise RuntimeError(f"Missing api_key for provider={provider_name} (set env: {api_key_value})")

    return ProviderConfig(
        type=str(p.get("type") or ""),
        base_url=str(p.get("base_url") or ""),
        api_key=api_key,
        model=str(p.get("model") or ""),
    )


def find_default_llm_config() -> Optional[Path]:
    for name in ("llm.json", "llm.example.json"):
        p = Path(name)
        if p.exists():
            return p
    return None


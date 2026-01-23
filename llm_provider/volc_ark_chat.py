from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


def _build_url(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/api/v3"):
        return f"{base}/chat/completions"
    return f"{base}/api/v3/chat/completions"


def chat_completions(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: List[ChatMessage],
    temperature: float = 0.2,
    max_tokens: int = 10000,
    thinking: Optional[Dict[str, Any]] = None,
    timeout_s: int = 120,
) -> str:
    """Call Volc Ark Chat Completions API and return assistant.message.content."""

    url = _build_url(base_url)
    if thinking is None:
        thinking = {"type": "disabled"}

    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "thinking": thinking,
    }

    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
        raise RuntimeError(f"HTTPError {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"URLError: {e}") from e

    try:
        obj = json.loads(raw)
        return str(obj["choices"][0]["message"]["content"])
    except Exception as e:
        raise RuntimeError(f"Unexpected response: {raw[:500]}") from e
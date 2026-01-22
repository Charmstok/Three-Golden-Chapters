from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


def read_text(path: Path) -> str:
    """以 UTF-8 读取文本；本项目的提示词文件统一按 UTF-8 存储。"""
    return path.read_text(encoding="utf-8")


def safe_print(s: str) -> None:
    """避免 Windows 终端编码导致的打印报错：非 ASCII 内容用 unicode_escape 输出。"""
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode("unicode_escape", "backslashreplace").decode("ascii", "ignore"))


def extract_json_object(s: str) -> Optional[Any]:
    """
    从模型返回内容中提取 JSON 对象。

    约定模型应只返回 JSON，但为防止出现前后缀文本，这里做一次兜底提取。
    """
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(s[start : end + 1])
    except json.JSONDecodeError:
        return None


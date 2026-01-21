from __future__ import annotations

"""一些通用的文本清洗工具。"""

import html
import re


def norm_text(s: str) -> str:
    """基础清洗：HTML 反转义、统一空白、去掉首尾空格。"""
    s = html.unescape(s)
    s = s.replace("\u00a0", " ").replace("\u3000", " ")
    s = re.sub(r"[\r\n\t]+", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

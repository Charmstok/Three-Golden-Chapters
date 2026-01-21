from __future__ import annotations

"""
章节标题解析与文件名清洗。

支持识别：
- 第1章/节/回 标题
- 1、标题
- 1. 标题 / 1．标题
"""

import re
from typing import Optional, Tuple

from text_utils import norm_text

# 章节标题匹配（用 unicode 转义避免编码差异导致的匹配问题）
CHAPTER_RE_1 = re.compile(
    r"^\s*\u7b2c\s*([0-9]+|[\u3007\u96f6\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e24]+)\s*[\u7ae0\u8282\u56de]\s*(.*?)\s*$"
)
CHAPTER_RE_2 = re.compile(
    r"^\s*([0-9]+|[\u3007\u96f6\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u5343\u4e24]+)\s*[\u3001\.\uFF0E]\s*(.+?)\s*$"
)

_CN_DIGIT = {
    "\u96f6": 0,
    "\u3007": 0,
    "\u4e00": 1,
    "\u4e8c": 2,
    "\u4e24": 2,
    "\u4e09": 3,
    "\u56db": 4,
    "\u4e94": 5,
    "\u516d": 6,
    "\u4e03": 7,
    "\u516b": 8,
    "\u4e5d": 9,
}
_CN_UNIT = {"\u5341": 10, "\u767e": 100, "\u5343": 1000}


def cn_numeral_to_int(s: str) -> Optional[int]:
    """把常见中文数字（含“十/百/千”）转成 int；不处理“万/亿”等更大单位。"""
    s = norm_text(s)
    if not s:
        return None
    if s.isdigit():
        try:
            return int(s)
        except ValueError:
            return None

    total = 0
    num = 0
    saw_any = False
    for ch in s:
        if ch in _CN_DIGIT:
            num = _CN_DIGIT[ch]
            saw_any = True
            continue
        if ch in _CN_UNIT:
            unit = _CN_UNIT[ch]
            saw_any = True
            if num == 0:
                num = 1  # "十" => 10
            total += num * unit
            num = 0
            continue
        return None

    return (total + num) if saw_any else None


def sanitize_filename_component(name: str) -> str:
    """清洗章节名为可用文件名片段（Windows 下不能包含 <>:\"/\\|?*）。"""
    name = norm_text(name)
    # Windows forbidden characters: <>:"/\|?*
    name = re.sub(r'[<>:"/\\\\|?*]+', "_", name)
    name = re.sub(r"\s{2,}", " ", name).strip()
    return name or "\u672a\u547d\u540d"


def parse_chapter_heading(text: str, *, allow_numbered: bool = True) -> Optional[Tuple[int, str]]:
    """尝试把一行文本解析为章节标题，返回 (章序, 章节名)。"""
    t = norm_text(text)
    # 章节标题一般较短，长度限制可以减少误判
    if not t or len(t) > 60:
        return None

    m1 = CHAPTER_RE_1.match(t)
    if m1:
        n = cn_numeral_to_int(m1.group(1))
        if n is None:
            return None
        title = norm_text(m1.group(2))
        title = re.sub(r"^[\s:\uFF1A\-\u2014_]+", "", title)
        title = title or f"\u7b2c{n}\u7ae0"
        return n, title

    if allow_numbered:
        m2 = CHAPTER_RE_2.match(t)
        if m2:
            n = cn_numeral_to_int(m2.group(1))
            if n is None:
                return None
            title = norm_text(m2.group(2))
            title = re.sub(r"^[\s:\uFF1A\-\u2014_]+", "", title)
            if not title or len(title) > 50:
                return None
            return n, title

    return None

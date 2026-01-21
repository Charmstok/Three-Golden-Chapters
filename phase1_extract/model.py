from __future__ import annotations

"""数据结构定义。"""

from dataclasses import dataclass
from typing import List


@dataclass
class Chapter:
    """一个章节：章序、标题、以及章节正文段落（不含章节标题行）。"""
    no: int
    title: str
    paragraphs: List[str]

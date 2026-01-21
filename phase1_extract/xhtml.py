from __future__ import annotations

import re
from typing import Iterator, List

from xml.etree import ElementTree as ET

from text_utils import norm_text


def strip_ns(tag: str) -> str:
    """去掉 XML 命名空间前缀，便于用 tag 名做判断。"""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def iter_text_blocks_from_xhtml(xhtml: str) -> Iterator[str]:
    """从 XHTML 中按阅读顺序抽取“文本块”（优先 h1-h6、p）。"""
    try:
        root = ET.fromstring(xhtml)
    except Exception:
        # 部分 EPUB 的 XHTML 不够规范：这里做一个无依赖的“尽力而为”标签剥离。
        body = re.sub(r"(?is)<script.*?</script>", " ", xhtml)
        body = re.sub(r"(?is)<style.*?</style>", " ", body)
        body = re.sub(r"(?is)<br\\s*/?>", "\n", body)
        body = re.sub(r"(?is)</p\\s*>", "\n", body)
        body = re.sub(r"(?is)<[^>]+>", " ", body)
        for line in body.splitlines():
            t = norm_text(line)
            if t:
                yield t
        return

    blocks: List[str] = []
    for el in root.iter():
        tag = strip_ns(el.tag).lower()
        if tag in {"script", "style"}:
            continue
        # 绝大多数小说段落都在 <p>，章节标题常在 <h1>/<h2>。
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6", "p"}:
            t = norm_text("".join(el.itertext()))
            if t:
                blocks.append(t)

    if not blocks:
        # 兜底：如果完全找不到 h/p，就直接从整份文本里切分出非空块。
        text = norm_text(" ".join(root.itertext()))
        for part in re.split(r"\s{2,}|\n+", text):
            t = norm_text(part)
            if t:
                blocks.append(t)

    yield from blocks

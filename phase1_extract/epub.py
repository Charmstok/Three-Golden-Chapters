from __future__ import annotations

"""
EPUB 读取与 OPF(spine) 解析。

这里不依赖第三方库：直接把 EPUB 当作 zip 读取，再从 container.xml 找到 OPF，
最后按 OPF 的 spine 顺序读取 XHTML/HTML 内容。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

import zipfile
from xml.etree import ElementTree as ET

from xhtml import strip_ns


@dataclass(frozen=True)
class EpubSpineItem:
    href: str


def read_text_from_zip(zf: zipfile.ZipFile, name: str) -> str:
    """读取 zip 内文件为文本（EPUB 常见编码优先级：utf-8 -> gb18030 -> 兜底）。"""
    data = zf.read(name)
    for enc in ("utf-8", "utf-8-sig", "gb18030", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def resolve_path(base: str, href: str) -> str:
    base_dir = str(Path(base).parent).replace("\\", "/")
    if base_dir in {"", "."}:
        return href
    return f"{base_dir}/{href}".replace("\\", "/")


def parse_container_rootfile(zf: zipfile.ZipFile) -> str:
    # EPUB 规范：META-INF/container.xml 指向 OPF 的 full-path。
    container_xml = read_text_from_zip(zf, "META-INF/container.xml")
    root = ET.fromstring(container_xml)
    for el in root.iter():
        if strip_ns(el.tag).lower() == "rootfile":
            full_path = el.attrib.get("full-path") or el.attrib.get("fullpath")
            if full_path:
                return full_path
    raise RuntimeError("Invalid EPUB: META-INF/container.xml missing rootfile full-path")


def parse_opf_spine(zf: zipfile.ZipFile, opf_path: str) -> List[EpubSpineItem]:
    opf_xml = read_text_from_zip(zf, opf_path)
    root = ET.fromstring(opf_xml)

    # manifest: id -> href（只收录可阅读的 xhtml/html）
    manifest: Dict[str, str] = {}
    for el in root.iter():
        if strip_ns(el.tag).lower() == "item":
            item_id = el.attrib.get("id")
            href = el.attrib.get("href")
            media_type = (el.attrib.get("media-type") or "").lower()
            if item_id and href and ("xhtml" in media_type or "html" in media_type):
                manifest[item_id] = href

    # spine: 以阅读顺序排列的内容列表（itemref -> manifest href）
    spine: List[EpubSpineItem] = []
    for el in root.iter():
        if strip_ns(el.tag).lower() == "itemref":
            idref = el.attrib.get("idref")
            if not idref:
                continue
            href = manifest.get(idref)
            if href:
                spine.append(EpubSpineItem(href=resolve_path(opf_path, href)))

    if not spine:
        raise RuntimeError("Invalid EPUB: OPF spine is empty (no readable XHTML items found)")
    return spine

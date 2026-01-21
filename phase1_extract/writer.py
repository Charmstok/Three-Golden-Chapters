from __future__ import annotations

import json
from pathlib import Path
from typing import List

from chapter import sanitize_filename_component
from model import Chapter


def write_chapters_jsonl(chapters: List[Chapter], out_dir: Path) -> int:
    """把多个章节写成多个 jsonl 文件：<章序>_<章节名>.jsonl。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    used: set[str] = set()
    files = 0

    for ch in chapters:
        safe_title = sanitize_filename_component(ch.title)
        base = f"{ch.no}_{safe_title}.jsonl"
        name = base
        k = 2
        # 保持输出确定性：重复运行会覆盖同名文件；
        # 只在同一次运行内发生重名时才追加后缀。
        while name.lower() in used:
            name = f"{ch.no}_{safe_title}_{k}.jsonl"
            k += 1
        used.add(name.lower())

        out_path = out_dir / name
        with out_path.open("w", encoding="utf-8") as f:
            for i, p in enumerate(ch.paragraphs, start=1):
                f.write(json.dumps({"paragraph_id": i, "text": p}, ensure_ascii=False) + "\n")
        files += 1

    return files

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from extractor import extract_first_chapters
from writer import write_chapters_jsonl

# 在某些环境/目录下写入会被拒绝（我们只需要读写 book/ 输出），禁用 .pyc 生成避免报错。
sys.dont_write_bytecode = True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract the first 3 chapters from an EPUB into book/<novel>/1_<title>.jsonl ...",
        usage="python phase1_extract/extract_three_chapters.py <path-to-book.epub>",
    )
    parser.add_argument("input", type=Path)
    args = parser.parse_args(argv)

    epub_path: Path = args.input
    if not epub_path.exists():
        print("Input not found", file=sys.stderr)
        return 2
    if epub_path.suffix.lower() != ".epub":
        print("Input must be .epub", file=sys.stderr)
        return 2

    # 约定：无论输入 epub 路径在哪里，输出都固定写到 book/<小说名>/ 下。
    out_dir = Path("book") / epub_path.stem
    # 只抽取前三章。
    chapters = extract_first_chapters(epub_path, max_chapters=3)
    if not chapters:
        print("No chapters extracted", file=sys.stderr)
        return 1

    # 每章独立写文件：<章序>_<章节名>.jsonl，段落从 1 开始编号。
    files = write_chapters_jsonl(chapters, out_dir)
    print(f"OK ({files} chapter files)")
    return 0

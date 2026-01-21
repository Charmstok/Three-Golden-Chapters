#!/usr/bin/env python3
"""超薄入口文件。

Command:
  python phase1_extract/extract_three_chapters.py book/书名.epub

Output:
  book/<小说名>/<章序>_<章节名>.jsonl（只提取前三章）
"""

from __future__ import annotations

import sys

# 在某些环境/目录下写入会被拒绝（我们只需要读写 book/ 输出），禁用 .pyc 生成避免报错。
sys.dont_write_bytecode = True

from cli import main


if __name__ == "__main__":
    raise SystemExit(main())

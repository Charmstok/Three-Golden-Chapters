from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Optional

from analysis_loader import chapter_rows_from_analysis, iter_analysis_json_files, load_chapter_analysis
from xlsx_writer import build_workbook


def _strip_quotes(s: str) -> str:
    s = str(s or "").strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    return s


def _find_novel_dir(input_path: Path) -> Path:
    """
    Phase3 输入只需要小说目录（book/书名）。
    兼容用户只传“书名”，脚本会自动补齐为 book/<书名>。
    """
    s = _strip_quotes(str(input_path))
    p = Path(s)
    if p.exists() and p.is_dir():
        return p
    cand = Path("book") / p.name
    if cand.exists() and cand.is_dir():
        return cand
    raise SystemExit(f"未找到小说目录：{p}\n请传入类似：python3 phase3_excel/run_phase3.py 书名")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase3: convert phase2 analysis json to a single Excel (.xlsx).",
        usage='python3 phase3_excel/run_phase3.py "book/书名"',
    )
    parser.add_argument("input", type=Path, help='Novel dir, e.g. "book/书名"')
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help='Output xlsx path (default: "<book_dir>/<book_name>.xlsx")',
    )
    args = parser.parse_args(argv)

    try:
        import openpyxl  # noqa: F401
    except Exception as e:
        raise SystemExit("缺少依赖 openpyxl，请先安装：pip install openpyxl") from e

    novel_dir = _find_novel_dir(args.input)
    analysis_dir = novel_dir / "analysis"
    if not analysis_dir.exists():
        raise SystemExit(f"未找到分析目录：{analysis_dir}\n请先运行第二阶段生成 analysis/*.json")

    print("[阶段 1/3] 扫描分析 JSON 文件")
    json_files = iter_analysis_json_files(analysis_dir)
    if not json_files:
        raise SystemExit(f"在目录中未找到分析 JSON：{analysis_dir}\n请确认已运行第二阶段（会生成 analysis/1_*.json 等）")

    # 通常只有前三章；如果有额外文件，这里仍按序合并。
    print(f"[阶段 1/3] 找到 {len(json_files)} 个文件，将合并到同一个 Excel 中")

    print("[阶段 2/3] 解析 JSON 并生成表格行")
    rows = []
    for p in json_files:
        meta, obj = load_chapter_analysis(p)
        rows.extend(chapter_rows_from_analysis(meta, obj))

    print(f"[阶段 2/3] 共 {len(rows)} 行")

    # 默认输出文件名使用“书名.xlsx”
    out_path = args.output or (novel_dir / f"{novel_dir.name}.xlsx")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("[阶段 3/3] 写入 Excel")
    wb = build_workbook(rows=rows)
    try:
        wb.save(out_path)
        print(f"[完成] 输出：{out_path}")
    except PermissionError:
        # Common: file is open in Excel so we cannot overwrite it.
        alt_path = out_path.with_name(f"{out_path.stem}_new{out_path.suffix}")
        wb.save(alt_path)
        print(f"[提示] 目标文件正在被占用，已改为输出到：{alt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

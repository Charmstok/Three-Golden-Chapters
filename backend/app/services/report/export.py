from __future__ import annotations

from pathlib import Path

from .xlsx_writer import build_workbook


def cell_text(value) -> str:
    # 模型与电子书中的内容始终作为文本写入，避免 Excel 将其当作公式。
    text = str(value or "")[:32000]
    text = "".join(c for c in text if ord(c) >= 32 or c in "\n\r\t")
    return "'" + text if text.startswith(("=", "+", "-", "@")) else text


def export_report(chapters: list[dict], analyses: list[dict], destination: Path) -> None:
    rows = []
    by_id = {ch["id"]: ch for ch in chapters}
    for analysis in analyses:
        chapter = by_id[analysis["chapter_id"]]
        chapter_label = f"第{chapter['no']}章 {chapter['title']}"
        for chunk in analysis["chunks"]:
            common = {"章节": cell_text(chapter_label),
                      "剧情块": cell_text(f"{chunk['chunk_id']} {chunk['chunk_title']}")}
            for part in chunk["slices"]:
                rows.append({**common, "起始段落": part["start"], "结束段落": part["end"],
                             "内容概述": cell_text(part["content_summary"]),
                             "节奏分析": cell_text(part["pacing_analysis"]),
                             "爆点提取": cell_text(part["hook_extraction"])})
            for label, key in [("剧情概述", "plot_summary"), ("节奏概述", "pacing_summary")]:
                rows.append({**common, "起始段落": label, "内容概述": cell_text(chunk[key])})
    temporary = destination.with_suffix(".tmp.xlsx")
    workbook = build_workbook(rows=rows)
    try:
        workbook.save(temporary)
        temporary.replace(destination)
    finally:
        workbook.close()
        temporary.unlink(missing_ok=True)

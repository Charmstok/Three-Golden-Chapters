from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class ChapterMeta:
    """Metadata derived from analysis json filename and content."""

    chapter_no: int
    chapter_title: str
    source_path: Path


_CHAPTER_STEM_RE = re.compile(r"^(?P<no>\d+)(?:_(?P<title>.+))?$")


def _parse_chapter_from_stem(stem: str) -> Tuple[Optional[int], str]:
    m = _CHAPTER_STEM_RE.match(stem.strip())
    if not m:
        return None, ""
    no = int(m.group("no"))
    title = (m.group("title") or "").strip()
    return no, title


def iter_analysis_json_files(analysis_dir: Path) -> List[Path]:
    """Return analysis json files in a stable chapter order (1..)."""
    files: List[Tuple[int, Path]] = []
    for p in analysis_dir.glob("*.json"):
        no, _ = _parse_chapter_from_stem(p.stem)
        if no is None:
            continue
        files.append((no, p))
    files.sort(key=lambda x: x[0])
    return [p for _, p in files]


def load_chapter_analysis(path: Path) -> Tuple[ChapterMeta, Dict[str, Any]]:
    """Load one chapter analysis json and infer chapter_no/title from filename."""
    no, title = _parse_chapter_from_stem(path.stem)
    obj = json.loads(path.read_text(encoding="utf-8"))

    # 兼容旧文件名（例如 1.json），优先用文件名序号；兜底使用内容里的 chapter_id。
    if no is None:
        try:
            no = int(obj.get("chapter_id") or 0)
        except Exception:
            no = 0

    # If the analysis filename doesn't contain a title (e.g. 1.json),
    # infer it from phase1 chapter jsonl name like 1_<title>.jsonl.
    if no and (not title.strip()):
        try:
            novel_dir = path.parent.parent
            cand = sorted(novel_dir.glob(f"{no}_*.jsonl"))
            if cand:
                _, t = _parse_chapter_from_stem(cand[0].stem)
                if t:
                    title = t
        except Exception:
            pass
    return ChapterMeta(chapter_no=no, chapter_title=title, source_path=path), obj


def _safe_cell_text(value: Any, *, limit: int = 32000) -> str:
    """Excel 单元格最大长度约 32767，这里做一个保守截断。"""
    if value is None:
        return ""
    s = str(value)
    if len(s) <= limit:
        return s
    return s[: limit - 3] + "..."


def chapter_rows_from_analysis(
    meta: ChapterMeta, obj: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Convert one chapter analysis json into a single table (one row per slice).
    """
    rows: List[Dict[str, Any]] = []

    chapter_title = meta.chapter_title.strip() or "（无标题）"
    chapter_label = f"第{meta.chapter_no}章 {chapter_title}".strip()

    chunks = obj.get("chunks") or []
    if not isinstance(chunks, list):
        return rows

    for c in chunks:
        if not isinstance(c, dict):
            continue

        chunk_id = c.get("chunk_id")
        chunk_title = _safe_cell_text(c.get("chunk_title"))
        chunk_label = f"{chunk_id} {chunk_title}".strip()
        plot_summary = _safe_cell_text(c.get("plot_summary"))
        pacing_summary = _safe_cell_text(c.get("pacing_summary"))

        slices = c.get("slices") or []
        if isinstance(slices, list):
            for s in slices:
                if not isinstance(s, dict):
                    continue
                rows.append(
                    {
                        "章节": chapter_label,
                        "剧情块": chunk_label,
                        "起始段落": s.get("start"),
                        "结束段落": s.get("end"),
                        "内容概述": _safe_cell_text(s.get("content_summary")),
                        "节奏分析": _safe_cell_text(s.get("pacing_analysis")),
                        "爆点提取": _safe_cell_text(s.get("hook_extraction")),
                    }
                )

        # chunk 总结行（两行）：在 chunk 结束后插入，用合并单元格展示“剧情概述/节奏概述”
        rows.append(
            {
                "章节": chapter_label,
                "剧情块": chunk_label,
                "起始段落": "\u5267\u60c5\u6982\u8ff0",
                "结束段落": "",
                "内容概述": plot_summary,
                "节奏分析": "",
                "爆点提取": "",
            }
        )
        rows.append(
            {
                "章节": chapter_label,
                "剧情块": chunk_label,
                "起始段落": "\u8282\u594f\u6982\u8ff0",
                "结束段落": "",
                "内容概述": pacing_summary,
                "节奏分析": "",
                "爆点提取": "",
            }
        )

    return rows

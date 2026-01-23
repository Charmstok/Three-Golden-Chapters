from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from io_utils import extract_json_object, safe_print
from prompts import load_prompts, render_prompt_1, render_prompt_23

# 允许从仓库根目录导入 llm_provider/（脚本从 phase2_analysis/ 直接运行时默认不会包含父目录）
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from llm_provider.llm_config import find_default_llm_config, load_chat_run_config
from llm_provider.volc_ark_chat import ChatMessage, chat_completions


def _progress_bar(done: int, total: int, width: int = 20) -> str:
    """Simple ASCII progress bar for console output."""
    if total <= 0:
        return f"进度[{'-' * width}] 0/0"
    done = max(0, min(done, total))
    filled = int(width * done / total)
    return f"进度[{'#' * filled}{'-' * (width - filled)}] {done}/{total}"


def _find_novel_dir(input_path: Path) -> Path:
    """
    输入既可以是：
    - book/小说名（目录，包含 1_*.jsonl 等）
    - book/书名.epub（文件）
    - 任意路径的 .epub（文件）
    """
    if input_path.is_dir():
        return input_path
    if input_path.suffix.lower() == ".epub":
        return Path("book") / input_path.stem
    raise SystemExit("input must be a novel dir (book/<name>) or an .epub file path")


def _iter_chapter_jsonl_files(novel_dir: Path) -> List[Tuple[int, Path]]:
    files: List[Tuple[int, Path]] = []
    for p in novel_dir.glob("*.jsonl"):
        # 期望格式：<章序>_<章节名>.jsonl
        try:
            no = int(p.name.split("_", 1)[0])
        except Exception:
            continue
        files.append((no, p))
    files.sort(key=lambda x: x[0])
    return files


def _read_jsonl_as_text(path: Path) -> str:
    # 直接把 jsonl 原样作为 prompt 的输入（保证 paragraph_id 严格对应）。
    return path.read_text(encoding="utf-8")


def _sanitize_filename_component(name: str) -> str:
    """用于输出文件名的安全清洗（主要兼容 Windows 文件名限制）。"""
    name = name.strip()
    name = name.replace("\u00a0", " ").replace("\u3000", " ")
    # Windows forbidden characters: <>:"/\|?*
    name = re.sub(r'[<>:"/\\\\|?*]+', "_", name)
    name = re.sub(r"\s{2,}", " ", name).strip()
    # 避免极端情况下文件名过长
    return (name[:80] or "untitled")


def _summarize_previous(result: Dict) -> str:
    """
    为第 2/3 章生成“上一章总结”占位内容。
    这里从模型输出的 chunks 中提取 plot_summary + pacing_summary 简要拼接。
    """
    chunks = result.get("chunks") or []
    parts: List[str] = []
    for c in chunks:
        title = (c.get("chunk_title") or "").strip()
        if title:
            parts.append(f"- 小节：{title}")
        ps = (c.get("plot_summary") or "").strip()
        pace = (c.get("pacing_summary") or "").strip()
        if ps:
            parts.append(f"- 剧情：{ps}")
        if pace:
            parts.append(f"- 节奏：{pace}")
    return "\n".join(parts).strip() or "无"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Phase2: send extracted chapter jsonl to LLM for story analysis (Volc Ark).",
        usage="python phase2_analysis/run_phase2.py book/小说名 或 python phase2_analysis/run_phase2.py book/书名.epub",
    )
    parser.add_argument("input", type=Path, help="Novel dir (book/<name>) or .epub file path")
    parser.add_argument("--profile", default=None, help="Profile name in llm.json (preferred when you have many models)")
    parser.add_argument("--provider", default=None, help="Override provider name in llm.json/profile")
    parser.add_argument("--model", default=None, help="Override model id")
    parser.add_argument("--temperature", type=float, default=None, help="Override temperature")
    parser.add_argument("--max-tokens", type=int, default=None, help="Override max_tokens")
    parser.add_argument("--llm-config", type=Path, default=None, help="Path to llm.json (default: auto-detect)")
    parser.add_argument("--dry-run", action="store_true", help="Render prompts only; do not call LLM")
    args = parser.parse_args(argv)

    safe_print("[阶段 1/4] 读取 LLM 配置")
    llm_config_path = args.llm_config or find_default_llm_config()
    if llm_config_path is None:
        raise SystemExit("llm.json not found (create one or pass --llm-config)")

    run_cfg = load_chat_run_config(
        llm_config_path,
        profile=args.profile,
        provider=args.provider,
        model=args.model,
    )
    if run_cfg.provider.type != "volc_ark":
        raise SystemExit(f"Unsupported provider type: {run_cfg.provider.type} (only volc_ark is implemented)")

    temperature = args.temperature if args.temperature is not None else run_cfg.params.temperature
    max_tokens = args.max_tokens if args.max_tokens is not None else run_cfg.params.max_tokens
    thinking = run_cfg.params.thinking
    timeout_s = run_cfg.params.timeout_s

    safe_print(
        f"[阶段 1/4] 选择模型：provider={run_cfg.provider_name} model={run_cfg.model} "
        f"temperature={temperature} max_tokens={max_tokens}"
    )

    safe_print("[阶段 2/4] 读取提示词")
    prompts = load_prompts(Path("prompt"))

    safe_print("[阶段 3/4] 扫描章节文件")
    novel_dir = _find_novel_dir(args.input)
    chapter_files = _iter_chapter_jsonl_files(novel_dir)
    if not chapter_files:
        raise SystemExit(f"No chapter jsonl files found in: {novel_dir}")

    # 只处理前三章
    chapter_files = [(no, p) for (no, p) in chapter_files if 1 <= no <= 3]
    if not chapter_files:
        raise SystemExit("No chapter jsonl files in range 1..3")

    out_dir = novel_dir / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_print("[阶段 4/4] 调用模型生成分析")
    previous_summary = ""
    total = len(chapter_files)
    for idx, (chapter_no, jsonl_path) in enumerate(chapter_files, start=1):
        jsonl_content = _read_jsonl_as_text(jsonl_path)
        # 输出文件名带上章节标题，便于人工对齐（例如：1_妖魔乱世.json / 1_妖魔乱世.raw.txt）
        out_stem = _sanitize_filename_component(jsonl_path.stem)
        safe_print(f"{_progress_bar(idx - 1, total)} 开始：第{chapter_no}章 输入={jsonl_path.name}")

        if chapter_no == 1:
            user_prompt = render_prompt_1(prompts.prompt_1, jsonl_content=jsonl_content, chapter_id=1)
        else:
            user_prompt = render_prompt_23(
                prompts.prompt_23,
                jsonl_content=jsonl_content,
                previous_summary=previous_summary,
                chapter_id=chapter_no,
            )

        if args.dry_run:
            safe_print(f"{_progress_bar(idx, total)} 跳过调用（dry-run）：第{chapter_no}章 提示词长度={len(user_prompt)}")
            continue

        content = chat_completions(
            base_url=run_cfg.provider.base_url,
            api_key=run_cfg.provider.api_key,
            model=run_cfg.model,
            messages=[
                ChatMessage(role="system", content=prompts.system),
                ChatMessage(role="user", content=user_prompt),
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            thinking=thinking,
            timeout_s=timeout_s,
        )

        out_json_path = out_dir / f"{out_stem}.json"
        out_raw_path = out_dir / f"{out_stem}.raw.txt"
        out_raw_path.write_text(content, encoding="utf-8")

        obj = extract_json_object(content)
        if obj is None:
            safe_print(f"ERROR chapter={chapter_no}: invalid JSON (saved raw)")
            return 1

        out_json_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        previous_summary = _summarize_previous(obj)
        safe_print(f"{_progress_bar(idx, total)} 完成：第{chapter_no}章 输出={out_json_path.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

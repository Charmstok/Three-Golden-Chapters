from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from io_utils import read_text


@dataclass(frozen=True)
class PromptBundle:
    system: str
    prompt_1: str
    prompt_23: str


def load_prompts(dir_path: Path) -> PromptBundle:
    """从指定目录读取提示词文件（system.md / prompt_1.md / prompt_23.md）。"""
    return PromptBundle(
        system=read_text(dir_path / "system.md"),
        prompt_1=read_text(dir_path / "prompt_1.md"),
        prompt_23=read_text(dir_path / "prompt_23.md"),
    )


def render_prompt_1(template: str, *, jsonl_content: str, chapter_id: int) -> str:
    # 注意：模板内包含大量 JSON 花括号，不能用 str.format；这里只做定向替换。
    s = template.replace("{jsonl_content}", jsonl_content)
    s += f"\n\n# 注意\n本次输出中的 chapter_id 必须为 {chapter_id}。\n"
    return s


def render_prompt_23(template: str, *, jsonl_content: str, previous_summary: str, chapter_id: int) -> str:
    s = template.replace("{jsonl_content}", jsonl_content).replace("{previous_chapter_summary}", previous_summary)
    s += f"\n\n# 注意\n本次输出中的 chapter_id 必须为 {chapter_id}。\n"
    return s

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError

from ...config import Settings
from ...model_repository import ModelRepository
from ...repository import BookRepository
from ...schemas import ChapterAnalysis
from ..report.export import export_report
from .client import generate_text
from .prompts import load_prompts, render_prompt_1, render_prompt_23

logger = logging.getLogger(__name__)


def parse_analysis(content: str, chapter: dict) -> dict:
    start, end = content.find("{"), content.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型未返回有效的 JSON 分析，请重试。")
    try:
        analysis = ChapterAnalysis.model_validate_json(content[start:end + 1])
    except ValidationError as exc:
        raise ValueError("模型分析缺少必要字段或 JSON 格式不正确，请重试。") from exc
    analysis.check_ranges(chapter["id"], len(chapter["paragraphs"]))
    return analysis.model_dump()


def previous_summary(analysis: dict) -> str:
    return "\n".join(
        f"小节：{chunk['chunk_title']}\n剧情：{chunk['plot_summary']}\n节奏：{chunk['pacing_summary']}"
        for chunk in analysis["chunks"]
    )


class AnalysisJobs:
    def __init__(self, settings: Settings, repository: BookRepository, models: ModelRepository):
        self.settings = settings
        self.repository = repository
        self.models = models
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chapter-analysis")

    def start(self, book_id: str, profile_id: str | None) -> None:
        model = self.models.resolve(profile_id)
        if not self.repository.reserve(book_id, model.id):
            raise RuntimeError("这本书正在分析，请等待任务完成。")
        try:
            self.executor.submit(self.run, book_id, model.base_url, model.api_key, model.model, model.params)
        except RuntimeError:
            self.repository.update(book_id, status="failed", error="任务服务正在关闭，请重试。", message="任务未启动")
            raise

    def run(self, book_id: str, base_url: str, api_key: str, model: str, params) -> None:
        try:
            book = self.repository.get(book_id)
            self.repository.update(book_id, status="running", message="正在准备章节分析")
            directory = self.settings.data_dir / book_id
            (directory / "report.xlsx").unlink(missing_ok=True)
            prompts = load_prompts(self.settings.prompts_dir)
            analyses = []
            summary = ""
            for index, chapter in enumerate(book["chapters"]):
                self.repository.update(book_id, message=f"正在分析第 {index + 1} / {len(book['chapters'])} 章")
                text = "\n".join(json.dumps(p, ensure_ascii=False) for p in chapter["paragraphs"])
                if index == 0:
                    prompt = render_prompt_1(prompts.prompt_1, jsonl_content=text, chapter_id=chapter["id"])
                else:
                    prompt = render_prompt_23(prompts.prompt_23, jsonl_content=text,
                                              previous_summary=summary, chapter_id=chapter["id"])
                content = generate_text(base_url=base_url, api_key=api_key, model=model, params=params,
                                           messages=[{"role": "system", "content": prompts.system},
                                                     {"role": "user", "content": prompt}])
                analysis = parse_analysis(content, chapter)
                analyses.append(analysis)
                summary = previous_summary(analysis)
                self.repository.update(book_id, analyses=analyses,
                                       progress=round(90 * (index + 1) / len(book["chapters"])))
            self.repository.update(book_id, message="正在生成 Excel 报告", progress=95)
            export_report(book["chapters"], analyses, directory / "report.xlsx")
            self.repository.update(book_id, status="completed", progress=100, message="分析完成，报告已就绪")
        except ValueError as exc:
            self.repository.update(book_id, status="failed", error=str(exc), message="分析未完成，可重新开始")
        except Exception:
            logger.exception("Analysis failed for book %s", book_id)
            self.repository.update(book_id, status="failed", error="分析过程中发生错误，请查看后端日志后重试。",
                                   message="分析未完成，可重新开始")

    def close(self) -> None:
        self.executor.shutdown(wait=True)

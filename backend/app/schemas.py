from __future__ import annotations

from pydantic import BaseModel, Field


class AnalysisRequest(BaseModel):
    profile_id: str | None = None


class Slice(BaseModel):
    slice_id: int = Field(ge=1, strict=True)
    start: int = Field(ge=1, strict=True)
    end: int = Field(ge=1, strict=True)
    content_summary: str
    pacing_analysis: str
    hook_extraction: str


class Chunk(BaseModel):
    chunk_id: int = Field(ge=1, strict=True)
    chunk_title: str = Field(min_length=1)
    start_paragraph: int = Field(ge=1, strict=True)
    end_paragraph: int = Field(ge=1, strict=True)
    slices: list[Slice] = Field(min_length=1)
    plot_summary: str
    pacing_summary: str


class ChapterAnalysis(BaseModel):
    chapter_id: int = Field(ge=1, strict=True)
    chunks: list[Chunk] = Field(min_length=1)

    def check_ranges(self, chapter_id: int, paragraph_count: int) -> None:
        if self.chapter_id != chapter_id:
            raise ValueError("模型返回的章节编号与原文不一致。")
        last_end = 0
        for chunk in self.chunks:
            if not last_end < chunk.start_paragraph <= chunk.end_paragraph <= paragraph_count:
                raise ValueError("模型返回的剧情块段落范围无效或重复。")
            last_end = chunk.end_paragraph
            slice_end = chunk.start_paragraph - 1
            for part in chunk.slices:
                if not slice_end < part.start <= part.end <= chunk.end_paragraph:
                    raise ValueError("模型返回的切片段落范围无效或重复。")
                slice_end = part.end

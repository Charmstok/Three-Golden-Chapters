from __future__ import annotations

import json
import shutil
import uuid
import zipfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from xml.etree.ElementTree import ParseError

from fastapi import FastAPI, HTTPException, Path as ApiPath, UploadFile
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles

from .config import Settings, ModelInput, ModelProbe
from .repository import BookRepository
from .model_repository import ModelRepository
from .services.analysis.client import generate_text, discover_models
from .schemas import AnalysisRequest
from .services.analysis.jobs import AnalysisJobs
from .services.epub.extractor import extract_first_chapters

BookId = Annotated[str, ApiPath(pattern=r"^[a-f0-9]{32}$")]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.repository = BookRepository(settings.data_dir)
        app.state.models = ModelRepository(settings.data_dir)
        app.state.jobs = AnalysisJobs(settings, app.state.repository, app.state.models)
        yield
        app.state.jobs.close()

    app = FastAPI(title="黄金三章 API", version="2.0.0", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Pydantic 的默认错误可能包含原始输入，配置表单中的密钥不能出现在响应里。
        return JSONResponse(status_code=422, content={
            "detail": "请求参数不正确，请检查表单中的地址、模型和高级参数。",
            "errors": [{"loc": list(error["loc"]), "msg": error["msg"]} for error in exc.errors()],
        })

    def get_book(book_id: str) -> dict:
        book = app.state.repository.get(book_id)
        if not book:
            raise HTTPException(404, "书籍不存在。")
        return book

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "2.0.0"}

    @app.get("/api/models")
    def models():
        return app.state.models.public()

    @app.post("/api/models", status_code=201)
    def create_model(value: ModelInput):
        return app.state.models.save(value)

    @app.post("/api/models/discover")
    def discover(value: ModelProbe):
        try:
            key = app.state.models.probe_key(value)
            return {"models": discover_models(base_url=value.base_url, api_key=key)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/api/models/test")
    def test_model(value: ModelProbe):
        if not value.model.strip():
            raise HTTPException(400, "请先选择或填写模型 ID。")
        try:
            key = app.state.models.probe_key(value)
            params = value.params.model_copy(update={"max_tokens": 256, "timeout_s": min(value.params.timeout_s, 30)})
            started = time.monotonic()
            generate_text(base_url=value.base_url, api_key=key, model=value.model.strip(),
                             messages=[{"role": "user", "content": "Reply with OK."}], params=params, allow_truncated=True)
            return {"ok": True, "latency_ms": round((time.monotonic() - started) * 1000)}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.put("/api/models/{model_id}")
    def update_model(model_id: BookId, value: ModelInput):
        try:
            return app.state.models.save(value, model_id)
        except KeyError as exc:
            raise HTTPException(404, "模型配置不存在。") from exc

    @app.post("/api/models/{model_id}/default")
    def default_model(model_id: BookId):
        try:
            return app.state.models.set_default(model_id)
        except KeyError as exc:
            raise HTTPException(404, "模型配置不存在。") from exc

    @app.delete("/api/models/{model_id}", status_code=204)
    def delete_model(model_id: BookId):
        try:
            app.state.models.delete(model_id)
        except KeyError as exc:
            raise HTTPException(404, "模型配置不存在。") from exc
        return Response(status_code=204)

    @app.get("/api/books")
    def books():
        return app.state.repository.list()

    @app.post("/api/books", status_code=201)
    def upload(file: UploadFile):
        filename = Path((file.filename or "").replace("\\", "/")).name
        if not filename.lower().endswith(".epub"):
            raise HTTPException(415, "请上传 EPUB 格式的电子书。")
        book_id = uuid.uuid4().hex
        directory = settings.data_dir / book_id
        directory.mkdir(parents=True)
        source = directory / "source.epub"
        try:
            size = 0
            with source.open("wb") as destination:
                while chunk := file.file.read(1024 * 1024):
                    size += len(chunk)
                    if size > settings.max_upload_bytes:
                        raise HTTPException(413, "电子书不能超过 50 MB。")
                    destination.write(chunk)
            with zipfile.ZipFile(source) as archive:
                entries = archive.infolist()
                if len(entries) > 5000 or sum(item.file_size for item in entries) > 200 * 1024 * 1024:
                    raise HTTPException(413, "EPUB 解压后的内容过大。")
                if any(item.flag_bits & 1 for item in entries):
                    raise HTTPException(422, "暂不支持加密 EPUB，请上传无加密版本。")
            extracted = extract_first_chapters(source, max_chapters=3)
            if not extracted or any(not chapter.paragraphs for chapter in extracted):
                raise HTTPException(422, "未识别到有效章节正文，请确认书籍使用「第 X 章」或「X、标题」格式。")
            chapters = [{"id": index, "no": chapter.no, "title": chapter.title,
                         "paragraphs": [{"paragraph_id": i, "text": text}
                                        for i, text in enumerate(chapter.paragraphs, start=1)]}
                        for index, chapter in enumerate(extracted, start=1)]
            return app.state.repository.create(book_id, Path(filename).stem[:100], filename[:255], chapters)
        except (zipfile.BadZipFile, KeyError, ParseError, RuntimeError, NotImplementedError, ValueError) as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise HTTPException(422, "无法读取 EPUB，文件可能损坏、加密或缺少有效章节。") from exc
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        finally:
            file.file.close()

    @app.get("/api/books/{book_id}")
    def detail(book_id: BookId):
        return get_book(book_id)

    @app.post("/api/books/{book_id}/analysis", status_code=202)
    def analyze(book_id: BookId, request: AnalysisRequest):
        get_book(book_id)
        try:
            app.state.jobs.start(book_id, request.profile_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return get_book(book_id)

    @app.delete("/api/books/{book_id}", status_code=204)
    def delete(book_id: BookId):
        get_book(book_id)
        if not app.state.repository.delete(book_id):
            raise HTTPException(409, "分析中的书籍暂时不能删除。")
        shutil.rmtree(settings.data_dir / book_id, ignore_errors=True)
        return Response(status_code=204)

    @app.get("/api/books/{book_id}/report")
    def report(book_id: BookId):
        book = get_book(book_id)
        path = settings.data_dir / book_id / "report.xlsx"
        if book["status"] != "completed" or not path.is_file():
            raise HTTPException(409, "分析尚未完成，报告暂不可下载。")
        return FileResponse(path, filename=f"{book['title']}_黄金三章.xlsx",
                            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.get("/api/books/{book_id}/analysis.json")
    def analysis_json(book_id: BookId):
        book = get_book(book_id)
        if not book["analyses"]:
            raise HTTPException(409, "暂无分析结果。")
        return Response(json.dumps({"title": book["title"], "analyses": book["analyses"]}, ensure_ascii=False, indent=2),
                        media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{book_id}.json"'})

    # 必须在静态站点之前拦截未知 API，避免返回 HTML 伪装成成功响应。
    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    def api_not_found(path: str):
        raise HTTPException(404, "API 不存在。")

    if settings.frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="web")
    else:
        @app.get("/")
        def frontend_not_built():
            return {"message": "前端尚未构建。开发时访问 http://127.0.0.1:5173；部署前运行 npm run build。",
                    "docs": "/docs"}

    return app


app = create_app()

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.app.config import ROOT, Settings
from backend.app.main import create_app


def make_epub(count=4, title_prefix="故事", malformed=False):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/content.opf" /></rootfiles></container>')
        manifest = '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav" />'
        spine = '<itemref idref="nav" />'
        archive.writestr("OEBPS/nav.xhtml", '<html><body><p>第一章 目录</p><p>第二章 目录</p><p>第三章 目录</p></body></html>')
        for n in range(1, count + 1):
            manifest += f'<item id="c{n}" href="Text/../chapter{n}.xhtml#start" media-type="application/xhtml+xml" />'
            spine += f'<itemref idref="c{n}" />'
            content = f'<html><body><h1>第{n}章 {title_prefix}{n}</h1><p>主角发现了秘密。</p><p>门外忽然传来脚步声。</p></body></html>'
            if malformed:
                content = content.replace('</body>', '<br></body>')
            archive.writestr(f"OEBPS/chapter{n}.xhtml", content)
        archive.writestr("OEBPS/content.opf", f'<package><manifest>{manifest}</manifest><spine>{spine}</spine></package>')
    return buffer.getvalue()


def model_result(chapter_id):
    return {"chapter_id": chapter_id, "chunks": [{
        "chunk_id": 1, "chunk_title": "危机初现", "start_paragraph": 1, "end_paragraph": 2,
        "plot_summary": "主角发现秘密，危机逼近。", "pacing_summary": "从平静转向紧张。",
        "slices": [{"slice_id": 1, "start": 1, "end": 2, "content_summary": "秘密与脚步声。",
                    "pacing_analysis": "悬念升级", "hook_extraction": "门外来者是谁？"}],
    }]}


@pytest.fixture
def settings(tmp_path):
    return Settings(data_dir=tmp_path / "data", frontend_dist=tmp_path / "dist",
                    prompts_dir=ROOT / "backend/prompts")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def book(client):
    response = client.post('/api/books', files={"file": ("测试小说.epub", make_epub(), "application/epub+zip")})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def configured(client):
    response = client.post('/api/models', json={
        'label': '测试模型', 'base_url': 'https://example.com/v1',
        'model': 'test-model', 'api_key': 'test-secret',
    })
    assert response.status_code == 201, response.text
    return response.json()['profiles'][0]

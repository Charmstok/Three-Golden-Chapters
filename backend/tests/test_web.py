import io
import json
import re
import threading
import time

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.app.main import create_app
from backend.app.repository import BookRepository
from backend.app.services.analysis import jobs
from backend.app.services.analysis.client import chat_completions
from backend.app.services.report.export import cell_text
from backend.app.config import Parameters
from conftest import make_epub, model_result


def wait_for_result(client, book_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        result = client.get(f"/api/books/{book_id}").json()
        if result["status"] in {"completed", "failed"}:
            return result
        time.sleep(.01)
    pytest.fail("Analysis did not finish")


def test_upload_extracts_three_body_chapters(client, book):
    assert book['chapter_count'] == 3
    assert book['paragraph_count'] == 6
    assert [ch['title'] for ch in book['chapters']] == ['故事1', '故事2', '故事3']
    assert [p['paragraph_id'] for p in book['chapters'][0]['paragraphs']] == [1, 2]
    assert book['status'] == 'ready'
    summary = client.get('/api/books').json()[0]
    assert summary['id'] == book['id']
    assert 'chapters' not in summary


@pytest.mark.parametrize('filename,content,status', [
    ('readme.txt', b'hello', 415), ('bad.epub', b'invalid zip', 422),
    ('empty.epub', make_epub(0), 422),
])
def test_invalid_upload_cleans_files(client, settings, filename, content, status):
    assert client.post('/api/books', files={'file': (filename, content)}).status_code == status
    assert client.get('/api/books').json() == []
    assert not list(settings.data_dir.glob('*/source.epub'))


def test_fewer_chapters_and_malformed_html_are_supported(client):
    response = client.post('/api/books', files={'file': ('one.epub', make_epub(1, malformed=True))})
    assert response.status_code == 201
    assert response.json()['chapter_count'] == 1
    assert len(response.json()['chapters'][0]['paragraphs']) == 2


def test_full_analysis_context_export_and_persistence(client, book, settings, monkeypatch, configured):
    calls = []

    def fake_chat(**kwargs):
        prompt = kwargs['messages'][1]['content']
        chapter_id = int(re.search(r'chapter_id 必须为 (\d+)', prompt)[1])
        assert kwargs['api_key'] == 'test-secret'
        if chapter_id > 1:
            assert '主角发现秘密，危机逼近。' in prompt
        calls.append(chapter_id)
        return '```json\n' + json.dumps(model_result(chapter_id), ensure_ascii=False) + '\n```'

    monkeypatch.setattr(jobs, 'generate_text', fake_chat)
    assert client.post(f"/api/books/{book['id']}/analysis", json={'profile_id': configured['id']}).status_code == 202
    result = wait_for_result(client, book['id'])
    assert result['status'] == 'completed', result
    assert result['progress'] == 100
    assert calls == [1, 2, 3]
    report = client.get(f"/api/books/{book['id']}/report")
    assert report.status_code == 200
    workbook = load_workbook(io.BytesIO(report.content))
    assert workbook.sheetnames == ['分析']
    assert workbook['分析']['A2'].value == '第1章 故事1'
    assert workbook['分析']['G2'].value == '门外来者是谁？'
    assert workbook['分析'].freeze_panes == 'A2'
    assert len(workbook['分析'].merged_cells.ranges) > 0
    download = client.get(f"/api/books/{book['id']}/analysis.json")
    assert len(download.json()['analyses']) == 3
    assert BookRepository(settings.data_dir).get(book['id'])['analyses'] == result['analyses']


def test_empty_models_blocks_analysis(client, book):
    assert client.get('/api/models').json() == {'profiles': [], 'default_profile': None}
    response = client.post(f"/api/books/{book['id']}/analysis", json={})
    assert response.status_code == 400
    assert '模型设置' in response.json()['detail']
    assert client.get(f"/api/books/{book['id']}").json()['status'] == 'ready'


def test_active_book_blocks_duplicate_and_delete(client, book, monkeypatch, configured):
    release = threading.Event()

    def slow_chat(**kwargs):
        release.wait(timeout=5)
        return 'not JSON'

    monkeypatch.setattr(jobs, 'generate_text', slow_chat)
    try:
        assert client.post(f"/api/books/{book['id']}/analysis", json={}).status_code == 202
        assert client.post(f"/api/books/{book['id']}/analysis", json={}).status_code == 409
        assert client.delete(f"/api/books/{book['id']}").status_code == 409
        assert client.get(f"/api/books/{book['id']}/report").status_code == 409
    finally:
        release.set()
    assert wait_for_result(client, book['id'])['status'] == 'failed'


@pytest.mark.parametrize('bad', ['not JSON', json.dumps({'chapter_id': 1, 'chunks': []}),
                               json.dumps(model_result(5))])
def test_invalid_model_results_become_visible_failures(client, book, monkeypatch, bad, configured):
    monkeypatch.setattr(jobs, 'generate_text', lambda **kwargs: bad)
    client.post(f"/api/books/{book['id']}/analysis", json={})
    result = wait_for_result(client, book['id'])
    assert result['status'] == 'failed'
    assert result['error']
    assert client.get(f"/api/books/{book['id']}/report").status_code == 409


def test_restart_recovers_interrupted_tasks(client, book, settings):
    client.app.state.repository.update(book['id'], status='running', progress=30)
    result = BookRepository(settings.data_dir).get(book['id'])
    assert result['status'] == 'failed'
    assert '中断' in result['error']


def test_delete_cleans_source_and_database(client, book, settings):
    assert client.delete(f"/api/books/{book['id']}").status_code == 204
    assert client.get(f"/api/books/{book['id']}").status_code == 404
    assert not (settings.data_dir / book['id']).exists()


def test_static_frontend_and_api_boundary(settings):
    settings.frontend_dist.mkdir()
    (settings.frontend_dist / 'index.html').write_text('<html>Golden Chapters</html>')
    with TestClient(create_app(settings)) as client:
        assert 'Golden Chapters' in client.get('/').text
        assert client.get('/api/missing').status_code == 404
        assert client.get('/api/missing').headers['content-type'] == 'application/json'
        assert client.get('/api/books/not-a-uuid').status_code == 422


def test_invalid_model_config_does_not_echo_key(client):
    response = client.post('/api/models', json={'label': 'bad', 'base_url': 'file:///tmp',
                                               'model': 'model', 'api_key': 'private-value'})
    assert response.status_code == 422
    assert 'private-value' not in response.text
    assert client.get('/api/models').json()['profiles'] == []


def test_report_text_cannot_become_formula():
    assert cell_text('=HYPERLINK("evil")').startswith("'=")
    assert cell_text('@SUM(A1)') == "'@SUM(A1)"
    assert cell_text('正文\x00') == '正文'


def test_model_transport_uses_generic_url_and_handles_http_error(monkeypatch):
    import httpx

    def respond(request):
        assert str(request.url) == 'https://example.com/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer secret'
        return httpx.Response(401, json={'error': 'private content'})

    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    with pytest.raises(ValueError, match='HTTP 401') as error:
        chat_completions(base_url='https://example.com/v1', api_key='secret', model='model',
                         messages=[], params=Parameters())
    assert 'private content' not in str(error.value)


def test_socks_proxy_dependencies_are_available(monkeypatch):
    import httpx
    monkeypatch.setenv('ALL_PROXY', 'socks5://127.0.0.1:1080')
    with httpx.Client():
        pass


def test_partial_results_survive_failure_and_retry_replaces_them(client, book, monkeypatch, configured):
    calls = 0

    def partial(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError('模型请求超时')
        return json.dumps(model_result(calls))

    monkeypatch.setattr(jobs, 'generate_text', partial)
    client.post(f"/api/books/{book['id']}/analysis", json={})
    result = wait_for_result(client, book['id'])
    assert result['status'] == 'failed'
    assert len(result['analyses']) == 1
    assert client.get(f"/api/books/{book['id']}/analysis.json").status_code == 200

    def success(**kwargs):
        chapter_id = int(re.search(r'chapter_id 必须为 (\d+)', kwargs['messages'][1]['content'])[1])
        return json.dumps(model_result(chapter_id))

    monkeypatch.setattr(jobs, 'generate_text', success)
    assert client.post(f"/api/books/{book['id']}/analysis", json={}).status_code == 202
    result = wait_for_result(client, book['id'])
    assert result['status'] == 'completed'
    assert result['error'] is None
    assert len(result['analyses']) == 3


def test_model_cannot_reference_missing_paragraphs(client, book, monkeypatch, configured):
    invalid = model_result(1)
    invalid['chunks'][0]['end_paragraph'] = 500
    monkeypatch.setattr(jobs, 'generate_text', lambda **kwargs: json.dumps(invalid))
    client.post(f"/api/books/{book['id']}/analysis", json={})
    result = wait_for_result(client, book['id'])
    assert result['status'] == 'failed'
    assert '段落范围' in result['error']


def test_upload_size_limit_cleans_partial_file(settings):
    from dataclasses import replace
    with TestClient(create_app(replace(settings, max_upload_bytes=100))) as client:
        response = client.post('/api/books', files={'file': ('large.epub', make_epub())})
        assert response.status_code == 413
        assert client.get('/api/books').json() == []
        assert not list(settings.data_dir.glob('*/source.epub'))

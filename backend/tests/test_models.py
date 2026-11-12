import json

import httpx
import pytest

from backend.app.config import Parameters
from backend.app.main import create_app
from backend.app.services.analysis import client as transport
from fastapi.testclient import TestClient


def test_web_settings_crud_default_and_secret_preservation(client, settings):
    first = client.post('/api/models', json={'label': '服务 A', 'base_url': 'https://a.example/v1/',
                                            'model': 'model-a', 'api_key': 'secret-a'}).json()
    model = first['profiles'][0]
    assert first['default_profile'] == model['id']
    assert model['base_url'] == 'https://a.example/v1'
    assert model['has_api_key']
    assert 'api_key' not in model
    assert 'secret-a' not in json.dumps(first)
    second = client.post('/api/models', json={'label': '服务 B', 'base_url': 'http://localhost:11434/v1',
                                             'model': 'local', 'make_default': True}).json()
    second_id = second['profiles'][1]['id']
    assert second['default_profile'] == second_id
    response = client.put('/api/models/' + model['id'], json={
        'label': '服务 A 新名称', 'base_url': model['base_url'], 'model': 'model-a2', 'api_key': ''})
    assert response.status_code == 200
    assert client.app.state.models.resolve(model['id']).api_key == 'secret-a'
    assert client.app.state.models.resolve(model['id']).model == 'model-a2'
    assert client.post('/api/models/' + model['id'] + '/default').json()['default_profile'] == model['id']
    assert client.delete('/api/models/' + model['id']).status_code == 204
    assert client.get('/api/models').json()['default_profile'] == second_id
    assert client.delete('/api/models/' + second_id).status_code == 204
    assert client.get('/api/models').json()['default_profile'] is None
    assert client.delete('/api/models/' + second_id).status_code == 404


def test_config_persists_across_restart_without_returning_secret(client, settings, configured):
    with TestClient(create_app(settings)) as reopened:
        response = reopened.get('/api/models')
        assert response.json()['profiles'][0]['model'] == 'test-model'
        assert 'test-secret' not in response.text
        assert reopened.app.state.models.resolve(None).api_key == 'test-secret'
    assert settings.data_dir.joinpath('models.sqlite3').stat().st_mode & 0o777 == 0o600


def test_key_can_be_replaced_and_cleared(client, configured):
    body = {'label': '配置', 'base_url': configured['base_url'], 'model': 'model', 'api_key': 'new-secret'}
    assert client.put('/api/models/' + configured['id'], json=body).status_code == 200
    assert client.app.state.models.resolve(None).api_key == 'new-secret'
    body.update(api_key=None, clear_api_key=True)
    response = client.put('/api/models/' + configured['id'], json=body)
    assert not response.json()['profiles'][0]['has_api_key']
    assert client.app.state.models.resolve(None).api_key == ''


def test_discover_and_test_use_unsaved_form_and_stored_key(client, configured, monkeypatch):
    requests = []

    def respond(request):
        requests.append(request)
        assert request.headers['authorization'] == 'Bearer test-secret'
        if request.method == 'GET':
            assert str(request.url) == 'https://example.com/v1/models'
            return httpx.Response(200, json={'data': [{'id': 'z'}, {'id': 'a'}, {'id': 'z'}]})
        body = json.loads(request.content)
        assert body['model'] == 'unsaved-model'
        assert body['stream'] is False
        assert 'thinking' not in body
        return httpx.Response(200, json={'choices': [{'message': {'content': 'OK'}}]})

    original = httpx.Client
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    form = {'base_url': configured['base_url'], 'saved_id': configured['id'], 'model': 'unsaved-model'}
    assert client.post('/api/models/discover', json=form).json()['models'] == ['a', 'z']
    response = client.post('/api/models/test', json=form)
    assert response.status_code == 200
    assert response.json()['ok']
    assert 'test-secret' not in response.text
    assert len(requests) == 2
    assert client.app.state.models.resolve(None).model == 'test-model'


def test_unsaved_new_service_cannot_receive_existing_key(client, configured, monkeypatch):
    calls = []
    monkeypatch.setattr(transport, 'request_json', lambda **kw: calls.append(kw))
    response = client.post('/api/models/discover', json={
        'base_url': 'https://different.example/v1', 'saved_id': configured['id']})
    assert response.status_code == 400
    assert calls == []


@pytest.mark.parametrize('base', ['file:///tmp', 'https://user:pass@example.com/v1', 'https://example.com/v1?q=secret', 'https://example.com:invalid/v1'])
def test_invalid_service_urls_rejected(client, base):
    response = client.post('/api/models', json={'label': 'test', 'base_url': base, 'model': 'model', 'api_key': 'private-token'})
    assert response.status_code == 422
    assert 'private-token' not in response.text


def test_validation_never_echoes_long_api_key(client):
    secret = 'private-token-' * 400
    response = client.post('/api/models', json={'label': 'test', 'base_url': 'https://example.com/v1', 'model': 'model', 'api_key': secret})
    assert response.status_code == 422
    assert 'private-token' not in response.text


@pytest.mark.parametrize('base', ['https://example.com/v1', 'https://example.com/api/v3', 'http://localhost:1234/custom'])
def test_generic_transport_respects_prefix_and_optional_parameters(monkeypatch, base):
    def respond(request):
        assert str(request.url) == base + '/chat/completions'
        assert 'authorization' not in request.headers
        body = json.loads(request.content)
        assert 'temperature' not in body
        assert 'max_tokens' not in body
        assert body['max_completion_tokens'] == 200
        assert body['reasoning_effort'] == 'low'
        assert 'thinking' not in body
        return httpx.Response(200, json={'choices': [{'message': {'content': 'valid'}}]})

    original = httpx.Client
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    params = Parameters(temperature=None, max_tokens=200, token_limit_field='max_completion_tokens', extra_body={'reasoning_effort': 'low'})
    assert transport.chat_completions(base_url=base, api_key='', model='any-model', messages=[], params=params) == 'valid'


def test_full_chat_url_is_normalized(client):
    result = client.post('/api/models', json={'label': 'test', 'base_url': 'https://example.com/v1/chat/completions/', 'model': 'model'})
    assert result.status_code == 201
    assert result.json()['profiles'][0]['base_url'] == 'https://example.com/v1'


def test_upstream_errors_do_not_expose_key_or_body(client, configured, monkeypatch):
    original = httpx.Client
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(401, json={'error': 'test-secret private-body'})), **kw))
    response = client.post('/api/models/test', json={'base_url': configured['base_url'], 'saved_id': configured['id'], 'model': 'any'})
    assert response.status_code == 400
    assert 'HTTP 401' in response.text
    assert 'test-secret' not in response.text
    assert 'private-body' not in response.text


def test_reserved_extra_parameters_cannot_replace_messages(client):
    response = client.post('/api/models', json={'label': 'test', 'base_url': 'https://example.com/v1', 'model': 'model',
                                                'params': {'extra_body': {'messages': []}}})
    assert response.status_code == 422


def test_connection_probe_accepts_reasoning_token_limit_but_analysis_requires_full_output(client, configured, monkeypatch):
    original = httpx.Client
    response = {'choices': [{'finish_reason': 'length', 'message': {'content': None}}]}
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=response)), **kw))
    form = {'base_url': configured['base_url'], 'saved_id': configured['id'], 'model': 'reasoning-model'}
    assert client.post('/api/models/test', json=form).json()['ok']
    with pytest.raises(ValueError, match='输出达到上限'):
        transport.chat_completions(base_url=configured['base_url'], api_key='', model='model', messages=[], params=Parameters())


@pytest.mark.parametrize('base,api_format,expected_path', [
    ('https://example.com/api/v3/responses', 'auto', '/api/v3/responses'),
    ('https://example.com/v1/responses/', 'auto', '/v1/responses'),
    ('https://example.com/v1', 'responses', '/v1/responses'),
    ('https://example.com/v1/chat/completions', 'responses', '/v1/responses'),
])
def test_responses_endpoint_input_and_reasoning_output(monkeypatch, base, api_format, expected_path):
    def respond(request):
        assert request.url.path == expected_path
        body = json.loads(request.content)
        assert body['input'][0] == {'role': 'system', 'content': [{'type': 'input_text', 'text': 'Analyze the story.'}]}
        assert body['input'][1]['content'][0]['text'] == 'Chapter text'
        assert body['max_output_tokens'] == 10000
        assert 'messages' not in body and 'max_tokens' not in body
        assert 'max_completion_tokens' not in body
        assert body['store'] is False
        return httpx.Response(200, json={'status': 'completed', 'output': [
            {'type': 'reasoning', 'summary': [{'type': 'summary_text', 'text': 'private reasoning'}]},
            {'type': 'message', 'content': [{'type': 'output_text', 'text': '{"chapter_id":1,'},
                                           {'type': 'output_text', 'text': '"chunks":[]}' }]},
        ]})
    original = httpx.Client
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    result = transport.generate_text(base_url=base, api_key='test', model='any-model',
                                     messages=[{'role': 'system', 'content': 'Analyze the story.'},
                                               {'role': 'user', 'content': 'Chapter text'}],
                                     params=Parameters(api_format=api_format))
    assert json.loads(result) == {'chapter_id': 1, 'chunks': []}
    assert 'private reasoning' not in result


def test_responses_form_probe_uses_saved_full_url_and_key(client, monkeypatch):
    value = {'label': 'Responses', 'base_url': 'https://example.com/api/v3/responses',
             'model': 'reasoning-model', 'api_key': 'private-key'}
    profile = client.post('/api/models', json=value).json()['profiles'][0]
    assert profile['params']['api_format'] == 'auto'
    def respond(request):
        assert request.url.path == '/api/v3/responses'
        assert request.headers['authorization'] == 'Bearer private-key'
        return httpx.Response(200, json={'status': 'completed', 'output': [
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'OK'}]}]})
    original = httpx.Client
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    response = client.post('/api/models/test', json={'base_url': value['base_url'], 'model': value['model'], 'saved_id': profile['id']})
    assert response.status_code == 200
    assert response.json()['ok']
    assert 'private-key' not in response.text


def test_model_list_uses_root_of_full_responses_url(monkeypatch):
    def respond(request):
        assert request.url.path == '/api/v3/models'
        return httpx.Response(200, json={'data': [{'id': 'model'}]})
    original = httpx.Client
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    assert transport.discover_models(base_url='https://example.com/api/v3/responses', api_key='') == ['model']


def test_responses_incomplete_status_is_not_a_successful_analysis(monkeypatch):
    original = httpx.Client
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
        'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}, 'output': []})), **kw))
    kwargs = dict(base_url='https://example.com/v1/responses', api_key='', model='model', messages=[], params=Parameters())
    with pytest.raises(ValueError, match='输出达到上限'):
        transport.generate_text(**kwargs)
    assert transport.generate_text(**kwargs, allow_truncated=True) == ''


def test_404_diagnostic_includes_actual_path_without_secret(monkeypatch):
    original = httpx.Client
    monkeypatch.setattr(transport.httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(lambda request: httpx.Response(404, text='private-key')), **kw))
    with pytest.raises(ValueError, match='POST /api/v3/responses') as error:
        transport.generate_text(base_url='https://example.com/api/v3/responses', api_key='private-key',
                                model='model', messages=[], params=Parameters())
    assert 'private-key' not in str(error.value)

from __future__ import annotations

from urllib.parse import urlsplit

import httpx

from ...config import Parameters


class ModelServiceError(ValueError):
    pass


def api_root(base_url: str) -> str:
    base = base_url.rstrip('/')
    for suffix in ('/chat/completions', '/responses'):
        if base.endswith(suffix):
            return base[:-len(suffix)]
    return base


def endpoint(base_url: str, path: str) -> str:
    return f"{api_root(base_url)}/{path.lstrip('/')}"


def selected_format(base_url: str, params: Parameters) -> str:
    if params.api_format != 'auto':
        return params.api_format
    return 'responses' if base_url.rstrip('/').endswith('/responses') else 'chat_completions'



def request_json(*, base_url: str, api_key: str, path: str, timeout: int, payload: dict | None = None) -> dict:
    headers = {'Authorization': f'Bearer {api_key}'} if api_key else {}
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            response = client.request('GET' if payload is None else 'POST', endpoint(base_url, path),
                                      headers=headers, **({'json': payload} if payload is not None else {}))
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError('Expected JSON object')
            return result
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        message = {
            401: '认证失败，请检查 API Key。', 403: '模型服务拒绝访问，请检查权限或余额。',
            404: ('服务未提供模型列表，可手动填写模型 ID 后测试连接。' if path == 'models'
                  else '服务未找到本次请求的接口或模型，请核对接口格式。'),
            429: '模型服务限流或额度不足，请稍后重试。',
        }.get(status, '请检查接口地址、模型和请求参数。')
        method = 'GET' if payload is None else 'POST'
        request_path = urlsplit(endpoint(base_url, path)).path
        raise ModelServiceError(f'模型服务返回 HTTP {status}。{message} 请求：{method} {request_path}') from exc
    except httpx.TimeoutException as exc:
        raise ModelServiceError('模型请求超时，可在「模型设置」中增加超时时间后重试。') from exc
    except (httpx.RequestError, httpx.InvalidURL) as exc:
        raise ModelServiceError('无法连接模型服务，请检查后端网络和 Base URL。') from exc
    except (TypeError, ValueError) as exc:
        raise ModelServiceError('模型服务未返回有效的 JSON 数据。') from exc


def chat_completions(*, base_url: str, api_key: str, model: str,
                     messages: list[dict], params: Parameters, allow_truncated: bool = False) -> str:
    payload = {'model': model, 'messages': messages, 'stream': False, **params.extra_body}
    if params.temperature is not None:
        payload['temperature'] = params.temperature
    if params.max_tokens is not None:
        payload[params.token_limit_field] = params.max_tokens
    result = request_json(base_url=base_url, api_key=api_key, path='chat/completions',
                          timeout=params.timeout_s, payload=payload)
    try:
        choice = result['choices'][0]
        if choice.get('finish_reason') == 'length':
            if allow_truncated:
                return ''
            raise ModelServiceError('模型输出达到上限，请在「模型设置」中增加最大输出 Token 数。')
        content = choice['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Empty content')
        return content
    except ModelServiceError:
        raise
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ModelServiceError('模型没有返回有效的文本内容，请检查是否支持 Chat Completions。') from exc


def discover_models(*, base_url: str, api_key: str) -> list[str]:
    result = request_json(base_url=base_url, api_key=api_key, path='models', timeout=30)
    try:
        data = result['data']
        if not isinstance(data, list):
            raise ValueError('Invalid model list')
        return sorted({item['id'] for item in data if isinstance(item, dict) and isinstance(item.get('id'), str) and item['id']})
    except (KeyError, TypeError, ValueError) as exc:
        raise ModelServiceError('服务未返回标准模型列表，可手动填写模型 ID。') from exc


def responses(*, base_url: str, api_key: str, model: str, messages: list[dict],
              params: Parameters, allow_truncated: bool = False) -> str:
    inputs = [{**message, 'content': [{'type': 'input_text', 'text': message['content']}]}
              if isinstance(message.get('content'), str) else message for message in messages]
    payload = {'model': model, 'input': inputs, 'stream': False, 'store': False, **params.extra_body}
    if params.temperature is not None:
        payload['temperature'] = params.temperature
    if params.max_tokens is not None:
        payload['max_output_tokens'] = params.max_tokens
    result = request_json(base_url=base_url, api_key=api_key, path='responses',
                          timeout=params.timeout_s, payload=payload)
    if result.get('status') == 'incomplete':
        details = result.get('incomplete_details')
        reason = details.get('reason') if isinstance(details, dict) else None
        if reason == 'max_output_tokens':
            if allow_truncated:
                return ''
            raise ModelServiceError('模型输出达到上限，请在「模型设置」中增加最大输出 Token 数。')
        raise ModelServiceError('模型响应未完成，请稍后重试。')
    if result.get('status') in {'failed', 'cancelled', 'queued', 'in_progress'} or result.get('error'):
        raise ModelServiceError('模型服务未完成 Responses 请求，请稍后重试。')
    try:
        texts = []
        for item in result.get('output', []):
            if item.get('type') == 'message':
                for part in item.get('content', []):
                    if part.get('type') == 'refusal':
                        raise ModelServiceError('模型拒绝处理本次内容。')
                    if part.get('type') == 'output_text' and isinstance(part.get('text'), str):
                        texts.append(part['text'])
        content = ''.join(texts) or result.get('output_text')
        if not isinstance(content, str) or not content.strip():
            raise ValueError('Empty output')
        return content
    except ModelServiceError:
        raise
    except (TypeError, AttributeError, ValueError) as exc:
        raise ModelServiceError('模型没有返回有效的 Responses 文本内容。') from exc


def generate_text(*, base_url: str, api_key: str, model: str, messages: list[dict],
                  params: Parameters, allow_truncated: bool = False) -> str:
    generate = responses if selected_format(base_url, params) == 'responses' else chat_completions
    return generate(base_url=base_url, api_key=api_key, model=model, messages=messages,
                    params=params, allow_truncated=allow_truncated)

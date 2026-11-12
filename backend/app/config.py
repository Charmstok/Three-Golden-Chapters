from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
import json
import os

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    frontend_dist: Path
    prompts_dir: Path
    max_upload_bytes: int = 50 * 1024 * 1024

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(ROOT / '.env')
        path = Path(os.getenv('TGC_DATA_DIR', 'data')).expanduser()
        return cls(data_dir=path if path.is_absolute() else ROOT / path,
                   frontend_dist=ROOT / 'frontend/dist', prompts_dir=ROOT / 'backend/prompts')


class Parameters(BaseModel):
    model_config = ConfigDict(extra='forbid')
    api_format: Literal['auto', 'chat_completions', 'responses'] = 'auto'
    temperature: float | None = Field(default=0.2, ge=0, le=2)
    max_tokens: int | None = Field(default=10000, ge=1, le=131072)
    token_limit_field: Literal['max_tokens', 'max_completion_tokens'] = 'max_tokens'
    timeout_s: int = Field(default=180, ge=1, le=600)
    extra_body: dict = Field(default_factory=dict)

    @field_validator('extra_body')
    @classmethod
    def check_extra_body(cls, value: dict) -> dict:
        reserved = {'model', 'messages', 'input', 'stream', 'temperature', 'max_tokens', 'max_completion_tokens', 'max_output_tokens'}
        if value.keys() & reserved:
            raise ValueError('额外参数不能覆盖模型、消息、流式开关或表单中的温度和输出上限。')
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False)) > 8192:
            raise ValueError('额外参数过长。')
        return value


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_url: str = Field(min_length=1, max_length=2000)
    api_key: SecretStr | None = Field(default=None, max_length=4096)
    clear_api_key: bool = False

    @field_validator('base_url')
    @classmethod
    def validate_url(cls, value: str) -> str:
        value = value.strip().rstrip('/')
        try:
            parts = urlsplit(value)
            port = parts.port
        except ValueError as exc:
            raise ValueError('接口地址格式不正确。') from exc
        if parts.scheme not in {'http', 'https'} or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('请输入不包含用户名、密码或查询参数的 HTTP(S) API 地址。')
        if value.endswith('/chat/completions'):
            value = value[:-len('/chat/completions')]
        return value


class ModelInput(ConnectionInput):
    label: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=200)
    params: Parameters = Field(default_factory=Parameters)
    make_default: bool = False

    @field_validator('label', 'model')
    @classmethod
    def strip_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError('名称和模型 ID 不能为空。')
        return value.strip()


class ModelProbe(ConnectionInput):
    saved_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    model: str = ''
    params: Parameters = Field(default_factory=Parameters)


@dataclass(frozen=True)
class RuntimeModel:
    id: str
    base_url: str
    api_key: str
    model: str
    params: Parameters

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path

from .config import ModelInput, ModelProbe, Parameters, RuntimeModel


class ModelRepository:
    """服务端保存连接配置；所有公开响应均去除密钥。"""

    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.database = data_dir / 'models.sqlite3'
        with self.connect() as conn:
            conn.execute('''CREATE TABLE IF NOT EXISTS models (
                id TEXT PRIMARY KEY, label TEXT NOT NULL, base_url TEXT NOT NULL,
                model TEXT NOT NULL, api_key TEXT NOT NULL, params TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )''')
            conn.execute('CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.database.chmod(0o600)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.database, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @staticmethod
    def public_row(row) -> dict:
        return {'id': row['id'], 'label': row['label'], 'base_url': row['base_url'],
                'model': row['model'], 'params': Parameters.model_validate_json(row['params']).model_dump(),
                'configured': True, 'has_api_key': bool(row['api_key'])}

    def public(self) -> dict:
        with self.connect() as conn:
            rows = conn.execute('SELECT * FROM models ORDER BY created_at, rowid').fetchall()
            default = conn.execute("SELECT value FROM preferences WHERE key='default_model'").fetchone()
        return {'default_profile': default['value'] if default else None,
                'profiles': [self.public_row(row) for row in rows]}

    def resolve(self, model_id: str | None) -> RuntimeModel:
        with self.connect() as conn:
            if not model_id:
                default = conn.execute("SELECT value FROM preferences WHERE key='default_model'").fetchone()
                model_id = default['value'] if default else None
            row = conn.execute('SELECT * FROM models WHERE id=?', (model_id,)).fetchone()
        if not row:
            raise ValueError('请先在「模型设置」中添加并选择一个模型。')
        return RuntimeModel(id=row['id'], base_url=row['base_url'], api_key=row['api_key'],
                            model=row['model'], params=Parameters.model_validate_json(row['params']))

    def save(self, value: ModelInput, model_id: str | None = None) -> dict:
        with self.connect() as conn:
            old = conn.execute('SELECT api_key FROM models WHERE id=?', (model_id,)).fetchone() if model_id else None
            if model_id and not old:
                raise KeyError('模型配置不存在。')
            key = old['api_key'] if old else ''
            if value.clear_api_key:
                key = ''
            elif value.api_key and value.api_key.get_secret_value().strip():
                key = value.api_key.get_secret_value().strip()
            identifier = model_id or uuid.uuid4().hex
            fields = (value.label, value.base_url, value.model, key, value.params.model_dump_json())
            if old:
                conn.execute('UPDATE models SET label=?,base_url=?,model=?,api_key=?,params=? WHERE id=?', (*fields, identifier))
            else:
                conn.execute('INSERT INTO models(label,base_url,model,api_key,params,id) VALUES(?,?,?,?,?,?)', (*fields, identifier))
            conn.execute("INSERT OR IGNORE INTO preferences(key,value) VALUES('default_model',?)", (identifier,))
            if value.make_default:
                conn.execute("UPDATE preferences SET value=? WHERE key='default_model'", (identifier,))
        return self.public()

    def set_default(self, model_id: str) -> dict:
        with self.connect() as conn:
            if not conn.execute('SELECT 1 FROM models WHERE id=?', (model_id,)).fetchone():
                raise KeyError('模型配置不存在。')
            conn.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('default_model',?)", (model_id,))
        return self.public()

    def delete(self, model_id: str) -> None:
        with self.connect() as conn:
            if conn.execute('DELETE FROM models WHERE id=?', (model_id,)).rowcount == 0:
                raise KeyError('模型配置不存在。')
            default = conn.execute("SELECT value FROM preferences WHERE key='default_model'").fetchone()
            if default and default['value'] == model_id:
                next_model = conn.execute('SELECT id FROM models ORDER BY created_at,rowid LIMIT 1').fetchone()
                if next_model:
                    conn.execute("UPDATE preferences SET value=? WHERE key='default_model'", (next_model['id'],))
                else:
                    conn.execute("DELETE FROM preferences WHERE key='default_model'")

    def probe_key(self, value: ModelProbe) -> str:
        if value.clear_api_key:
            return ''
        if value.api_key and value.api_key.get_secret_value().strip():
            return value.api_key.get_secret_value().strip()
        if value.saved_id:
            saved = self.resolve(value.saved_id)
            # 更换地址的未保存表单不能把已存密钥带到另一个服务。
            if saved.base_url != value.base_url:
                raise ValueError('接口地址已更改，请重新填写 API Key 或先保存配置。')
            return saved.api_key
        return ''

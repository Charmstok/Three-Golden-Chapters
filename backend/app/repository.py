from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ACTIVE = {"queued", "running"}


class BookRepository:
    def __init__(self, data_dir: Path):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.database = data_dir / "library.sqlite3"
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, filename TEXT NOT NULL,
                created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'ready',
                progress INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '章节已提取，等待分析',
                error TEXT, profile_id TEXT, chapters TEXT NOT NULL, analyses TEXT NOT NULL DEFAULT '[]'
            )""")
            conn.execute("""UPDATE books SET status='failed', message='分析已中断，可重新开始',
                error='服务重启导致任务中断，请重新分析。' WHERE status IN ('queued','running')""")

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
    def decode(row) -> dict:
        book = dict(row)
        book["chapters"] = json.loads(book["chapters"])
        book["analyses"] = json.loads(book["analyses"])
        book["chapter_count"] = len(book["chapters"])
        book["paragraph_count"] = sum(len(ch["paragraphs"]) for ch in book["chapters"])
        return book

    def create(self, book_id: str, title: str, filename: str, chapters: list[dict]) -> dict:
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO books(id,title,filename,created_at,chapters) VALUES(?,?,?,?,?)",
                (book_id, title, filename, datetime.now(timezone.utc).isoformat(),
                 json.dumps(chapters, ensure_ascii=False)),
            )
        return self.get(book_id)

    def get(self, book_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        return self.decode(row) if row else None

    def list(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM books ORDER BY created_at DESC").fetchall()
        books = []
        for row in rows:
            book = self.decode(row)
            del book["chapters"], book["analyses"]
            books.append(book)
        return books

    def update(self, book_id: str, **fields) -> None:
        allowed = {"status", "progress", "message", "error", "profile_id", "analyses"}
        if not fields or not fields.keys() <= allowed:
            raise ValueError("Invalid book update")
        if "analyses" in fields:
            fields["analyses"] = json.dumps(fields["analyses"], ensure_ascii=False)
        with self.connect() as conn:
            conn.execute(
                f"UPDATE books SET {','.join(f'{key}=?' for key in fields)} WHERE id=?",
                (*fields.values(), book_id),
            )

    def reserve(self, book_id: str, profile_id: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute("""UPDATE books SET status='queued', progress=0,
                message='任务已加入队列', error=NULL, analyses='[]', profile_id=?
                WHERE id=? AND status NOT IN ('queued','running')""", (profile_id, book_id))
            return cursor.rowcount == 1

    def delete(self, book_id: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM books WHERE id=? AND status NOT IN ('queued','running')", (book_id,))
            return cursor.rowcount == 1

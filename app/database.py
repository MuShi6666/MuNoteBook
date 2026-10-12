"""SQLite 数据访问层。

统一封装 notes 表的建表、增删改查、搜索、软删除/恢复等操作，
UI 层不直接编写 SQL。
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from .config import SUMMARY_LENGTH
from . import image_utils
from .models import Note

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL DEFAULT '未命名笔记',
    content     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    is_pinned   INTEGER NOT NULL DEFAULT 0,
    is_favorite INTEGER NOT NULL DEFAULT 0,
    is_deleted  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notes_state ON notes (is_deleted, is_pinned DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_notes_favorite ON notes (is_favorite, is_deleted, updated_at DESC);
"""

_LIST_COLUMNS = """
    id, title, created_at, updated_at, is_pinned, is_favorite, is_deleted,
    substr(content, 1, :limit) AS summary
"""


class Database:
    """SQLite 数据访问层（单连接 + WAL 模式）。"""

    def __init__(self, db_path: Path | str):
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    # ---------- 连接管理 ----------

    @property
    def connection(self) -> sqlite3.Connection:
        if self._conn is None:
            conn = sqlite3.connect(self._db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._conn = conn
        return self._conn

    def init_schema(self) -> None:
        """建表与索引（幂等）。"""
        with self.transaction() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """事务上下文：成功提交，异常回滚。"""
        conn = self.connection
        try:
            yield conn
            conn.commit()
        except sqlite3.Error:
            conn.rollback()
            logger.exception("SQLite 操作失败，已回滚")
            raise

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None

    # ---------- 行转换 ----------

    @staticmethod
    def _to_note(row: sqlite3.Row, *, full_content: bool = False) -> Note:
        keys = row.keys()
        return Note(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            is_pinned=bool(row["is_pinned"]),
            is_favorite=bool(row["is_favorite"]),
            is_deleted=bool(row["is_deleted"]),
            summary=row["summary"] if "summary" in keys else "",
            content=row["content"] if full_content else None,
        )

    # ---------- 查询 ----------

    def list_notes(
        self,
        *,
        favorite_only: bool = False,
        deleted: bool = False,
        keyword: str = "",
    ) -> list[Note]:
        """列出笔记：置顶优先，按修改时间倒序。

        ``favorite_only`` 仅看收藏；``deleted`` 为 True 时列出回收站；
        ``keyword`` 匹配标题或正文。
        """
        sql = f"SELECT {_LIST_COLUMNS} FROM notes WHERE is_deleted = :deleted"
        params: dict = {"limit": SUMMARY_LENGTH, "deleted": int(deleted)}
        if favorite_only:
            sql += " AND is_favorite = 1"
        if keyword:
            sql += " AND (title LIKE :kw OR content LIKE :kw)"
            params["kw"] = f"%{keyword}%"
        sql += " ORDER BY is_pinned DESC, updated_at DESC, id DESC"
        with self.transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._to_note(row) for row in rows]

    def get_note(self, note_id: int) -> Optional[Note]:
        """按 id 查询完整笔记（含正文）。"""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT * FROM notes WHERE id = :id", {"id": note_id}
            ).fetchone()
        return self._to_note(row, full_content=True) if row else None

    def count_notes(self, *, deleted: bool = False) -> int:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM notes WHERE is_deleted = :deleted",
                {"deleted": int(deleted)},
            ).fetchone()
        return int(row["c"]) if row else 0

    # ---------- 变更 ----------

    def create_note(self, title: str = "未命名笔记", content: str = "") -> int:
        """新建笔记，返回新笔记 id。"""
        now = datetime.now().isoformat(timespec="seconds")
        sql = """INSERT INTO notes (title, content, created_at, updated_at)
                 VALUES (:title, :content, :created, :updated)"""
        with self.transaction() as conn:
            cursor = conn.execute(
                sql,
                {"title": title, "content": content, "created": now, "updated": now},
            )
            return int(cursor.lastrowid)

    def update_note(
        self,
        note_id: int,
        *,
        title: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        """更新笔记标题/正文（同时刷新 updated_at）。"""
        assignments: list[str] = []
        params: dict = {
            "id": note_id,
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        if title is not None:
            assignments.append("title = :title")
            params["title"] = title
        if content is not None:
            assignments.append("content = :content")
            params["content"] = content
        if not assignments:
            return
        assignments.append("updated_at = :updated")
        sql = f"UPDATE notes SET {', '.join(assignments)} WHERE id = :id"
        with self.transaction() as conn:
            conn.execute(sql, params)

    def _toggle_flag(self, note_id: int, column: str) -> bool:
        """切换布尔标记位，返回切换后的值。"""
        with self.transaction() as conn:
            conn.execute(
                f"UPDATE notes SET {column} = 1 - {column} WHERE id = :id",
                {"id": note_id},
            )
            row = conn.execute(
                f"SELECT {column} AS v FROM notes WHERE id = :id", {"id": note_id}
            ).fetchone()
        return bool(row["v"]) if row else False

    def toggle_pinned(self, note_id: int) -> bool:
        return self._toggle_flag(note_id, "is_pinned")

    def toggle_favorite(self, note_id: int) -> bool:
        return self._toggle_flag(note_id, "is_favorite")

    # ---------- 回收站 ----------

    def move_to_trash(self, note_id: int) -> None:
        """软删除：移入回收站。"""
        with self.transaction() as conn:
            conn.execute(
                "UPDATE notes SET is_deleted = 1 WHERE id = :id", {"id": note_id}
            )

    def restore_note(self, note_id: int) -> None:
        """从回收站恢复。"""
        with self.transaction() as conn:
            conn.execute(
                "UPDATE notes SET is_deleted = 0 WHERE id = :id", {"id": note_id}
            )

    def delete_permanently(self, note_id: int) -> None:
        """彻底删除单条笔记，并清理其引用的图片库文件。"""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT content FROM notes WHERE id = :id", {"id": note_id}
            ).fetchone()
            if row is not None:
                conn.execute("DELETE FROM notes WHERE id = :id", {"id": note_id})
        if row is not None:
            image_utils.remove_images_in_content(row["content"])

    def clear_trash(self) -> None:
        """清空回收站，并清理所有被删笔记引用的图片库文件。"""
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT content FROM notes WHERE is_deleted = 1"
            ).fetchall()
            conn.execute("DELETE FROM notes WHERE is_deleted = 1")
        for row in rows:
            image_utils.remove_images_in_content(row["content"])

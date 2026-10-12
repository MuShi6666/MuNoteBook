"""收藏页：复用笔记页结构，仅展示收藏笔记。"""

from __future__ import annotations

from .notes_page import NotesPage


class FavoritesPage(NotesPage):
    """收藏笔记页（隐藏新建按钮，列表过滤收藏项）。"""

    def __init__(self, parent=None, *, db):
        super().__init__(parent, db=db, favorite_only=True)

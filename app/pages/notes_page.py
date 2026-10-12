"""所有笔记页：工具栏 + 笔记列表 + Markdown 编辑器（收藏页复用）。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget
from qfluentwidgets import (
    Action,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    RoundMenu,
    ToolButton,
    TransparentToolButton,
)

from .. import config
from ..database import Database
from ..models import Note
from ..widgets.markdown_editor import MarkdownEditor
from ..widgets.note_list_widget import NoteListWidget

logger = logging.getLogger(__name__)


class NotesPage(QWidget):
    """笔记工作区页面（收藏页通过继承仅改变过滤条件）。"""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        db: Database,
        favorite_only: bool = False,
    ):
        super().__init__(parent)
        self.setObjectName("favoritesPage" if favorite_only else "notesPage")
        self.db = db
        self.favorite_only = favorite_only

        self._build_ui()
        self._connect_signals()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # 左侧：工具栏 + 笔记列表
        left_widget = QWidget()
        left_widget.setObjectName("listPanel")
        left_widget.setFixedWidth(config.LIST_WIDTH)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(4)
        self.new_btn = ToolButton(FluentIcon.ADD, self)
        self.new_btn.setToolTip("新建笔记")
        self.export_btn = TransparentToolButton(FluentIcon.DOWNLOAD, self)
        self.export_btn.setToolTip("导出当前笔记 (.md)")
        if self.favorite_only:
            self.new_btn.setVisible(False)
        tools_row.addWidget(self.new_btn)
        tools_row.addWidget(self.export_btn)
        tools_row.addStretch(1)
        left_layout.addLayout(tools_row)

        self.note_list = NoteListWidget(
            self, db=self.db, favorite_only=self.favorite_only
        )
        left_layout.addWidget(self.note_list, 1)

        layout.addWidget(left_widget)

        # 右侧：Markdown 编辑器
        self.editor = MarkdownEditor(self)
        layout.addWidget(self.editor, 1)

    def _connect_signals(self) -> None:
        self.new_btn.clicked.connect(self.create_note)
        self.export_btn.clicked.connect(
            lambda: self.export_note(self.editor.current_note_id)
        )
        self.note_list.note_selected.connect(self._on_note_selected)
        self.note_list.context_menu_requested.connect(self._show_context_menu)
        self.editor.save_requested.connect(self._on_save_requested)
        self.editor.favorite_toggled.connect(self._on_favorite_toggled)
        self.editor.pinned_toggled.connect(self._on_pinned_toggled)

    # ---------- 刷新 ----------

    def refresh(self) -> None:
        self.note_list.refresh()

    def refresh_theme(self) -> None:
        self.editor.refresh_theme()

    # ---------- 笔记选择 ----------

    def _on_note_selected(self, note_id: Optional[int]) -> None:
        if note_id == self.editor.current_note_id:
            return
        self.flush_editor()
        if note_id is None:
            self.editor.load_note(None)
            return
        try:
            note = self.db.get_note(note_id)
        except Exception:
            logger.exception("加载笔记失败：%s", note_id)
            note = None
        self.editor.load_note(note)

    # ---------- 保存 ----------

    def flush_editor(self) -> None:
        """把编辑器未保存内容写入数据库（信号同步落库）。"""
        self.editor.flush()

    def _on_save_requested(self, title: str, content: str) -> None:
        note_id = self.editor.current_note_id
        if note_id is None:
            return
        try:
            self.db.update_note(note_id, title=title, content=content)
        except Exception:
            logger.exception("保存笔记失败：%s", note_id)

    # ---------- 新建 ----------

    def create_note(self) -> None:
        try:
            note_id = self.db.create_note()
        except Exception:
            logger.exception("新建笔记失败")
            return
        self.note_list.refresh()
        self.note_list.select_note(note_id)
        self.editor.title_edit.setFocus()
        self.editor.title_edit.selectAll()

    # ---------- 收藏 / 置顶 ----------

    def _on_favorite_toggled(self, note_id: int, _checked: bool) -> None:
        try:
            state = self.db.toggle_favorite(note_id)
        except Exception:
            logger.exception("切换收藏失败：%s", note_id)
            return
        self.editor.set_favorite(state)
        self.refresh()

    def _on_pinned_toggled(self, note_id: int, _checked: bool) -> None:
        try:
            state = self.db.toggle_pinned(note_id)
        except Exception:
            logger.exception("切换置顶失败：%s", note_id)
            return
        self.editor.set_pinned(state)
        self.refresh()

    def _toggle_pinned(self, note_id: int) -> None:
        try:
            self.db.toggle_pinned(note_id)
        except Exception:
            logger.exception("切换置顶失败：%s", note_id)
        self.refresh()

    def _toggle_favorite(self, note_id: int) -> None:
        try:
            state = self.db.toggle_favorite(note_id)
        except Exception:
            logger.exception("切换收藏失败：%s", note_id)
            return
        if self.editor.current_note_id == note_id:
            self.editor.set_favorite(state)
        self.refresh()

    # ---------- 删除 ----------

    def _move_to_trash(self, note_id: int) -> None:
        if self.editor.current_note_id == note_id:
            self.editor.load_note(None)
        try:
            self.db.move_to_trash(note_id)
        except Exception:
            logger.exception("移到回收站失败：%s", note_id)
            return
        self.refresh()

    # ---------- 导出 ----------

    def export_note(self, note_id: Optional[int]) -> None:
        if note_id is None:
            InfoBar.warning(
                title="无法导出",
                content="请先选择一篇笔记",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return
        try:
            note = self.db.get_note(note_id)
        except Exception:
            logger.exception("导出前加载笔记失败：%s", note_id)
            return
        if note is None:
            return
        default_name = f"{note.title or '未命名笔记'}.md"
        path, _ = QFileDialog.getSaveFileName(
            self, "导出 Markdown", default_name, "Markdown 文件 (*.md)"
        )
        if not path:
            return
        try:
            Path(path).write_text(note.content or "", encoding="utf-8")
        except OSError:
            logger.exception("导出失败：%s", path)
            InfoBar.error(
                title="导出失败",
                content=f"无法写入文件：{path}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            return
        InfoBar.success(
            title="导出成功",
            content=str(path),
            parent=self,
            position=InfoBarPosition.TOP,
            duration=2500,
        )

    # ---------- 右键菜单 ----------

    def _show_context_menu(self, note_id: int, pos) -> None:
        try:
            note = self.db.get_note(note_id)
        except Exception:
            logger.exception("加载笔记失败：%s", note_id)
            return
        if note is None:
            return

        menu = RoundMenu(parent=self)
        menu.addAction(
            Action(
                FluentIcon.PIN,
                "取消置顶" if note.is_pinned else "置顶",
                triggered=lambda: self._toggle_pinned(note_id),
            )
        )
        menu.addAction(
            Action(
                FluentIcon.HEART,
                "取消收藏" if note.is_favorite else "收藏",
                triggered=lambda: self._toggle_favorite(note_id),
            )
        )
        menu.addSeparator()
        menu.addAction(
            Action(
                FluentIcon.DOWNLOAD,
                "导出 Markdown",
                triggered=lambda: self.export_note(note_id),
            )
        )
        menu.addAction(
            Action(
                FluentIcon.DELETE,
                "移到回收站",
                triggered=lambda: self._move_to_trash(note_id),
            )
        )
        menu.exec(self.note_list.mapToGlobal(pos))

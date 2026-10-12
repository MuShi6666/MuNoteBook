"""回收站页：恢复、彻底删除、清空回收站。"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    BodyLabel,
    FluentIcon,
    MessageBox,
    PushButton,
    RoundMenu,
    SubtitleLabel,
    TransparentToolButton,
)

from .. import config
from ..app_settings import settings
from ..database import Database
from ..widgets.note_list_widget import NoteListWidget

logger = logging.getLogger(__name__)


class TrashPage(QWidget):
    """回收站页面。"""

    def __init__(
        self, parent: Optional[QWidget] = None, *, db: Database
    ):
        super().__init__(parent)
        self.setObjectName("trashPage")
        self.db = db

        self._build_ui()
        self._connect_signals()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 左右面板通过 QSplitter 分隔，列表宽度可拖拽调整并持久化
        self.panel_splitter = QSplitter(Qt.Horizontal, self)
        self.panel_splitter.setObjectName("pageSplitter")
        self.panel_splitter.setChildrenCollapsible(False)
        self.panel_splitter.setHandleWidth(3)

        left_widget = QWidget()
        left_widget.setObjectName("listPanel")
        left_widget.setMinimumWidth(config.MIN_LIST_WIDTH)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(16, 12, 8, 12)
        left_layout.setSpacing(8)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(4)
        # 注意：qfluentwidgets 的 ToolButton 自定义绘制会忽略 toolButtonStyle，
        # 图标与文字会重叠；带文字的操作按钮统一使用 PushButton（图标文字并排）。
        self.restore_btn = PushButton("恢复", self, FluentIcon.ADD)
        self.restore_btn.setToolTip("恢复到所有笔记")
        self.delete_btn = PushButton("删除", self, FluentIcon.DELETE)
        self.delete_btn.setToolTip("彻底删除所选笔记")
        self.clear_btn = TransparentToolButton(FluentIcon.REMOVE, self)
        self.clear_btn.setText("清空")
        self.clear_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.clear_btn.setToolTip("清空回收站")
        tools_row.addWidget(self.restore_btn)
        tools_row.addWidget(self.delete_btn)
        tools_row.addStretch(1)
        tools_row.addWidget(self.clear_btn)
        left_layout.addLayout(tools_row)

        self.note_list = NoteListWidget(self, db=self.db, deleted=True)
        left_layout.addWidget(self.note_list, 1)
        self.panel_splitter.addWidget(left_widget)

        # 右侧：说明区（随窗口伸缩）
        hint_widget = QWidget()
        hint_widget.setObjectName("trashHint")
        hint_layout = QVBoxLayout(hint_widget)
        hint_layout.setContentsMargins(8, 12, 16, 12)
        hint_layout.setAlignment(Qt.AlignCenter)
        hint_layout.setSpacing(8)
        hint_layout.addWidget(SubtitleLabel("回收站"))
        hint_layout.addWidget(
            BodyLabel("删除的笔记会先进入回收站，可在此恢复或彻底删除。")
        )
        self.panel_splitter.addWidget(hint_widget)
        self.panel_splitter.setStretchFactor(1, 1)
        self.panel_splitter.setSizes([settings.list_width, 600])

        layout.addWidget(self.panel_splitter)

        # 拖拽结束（防抖）后持久化列表宽度
        self._save_width_timer = QTimer(self)
        self._save_width_timer.setSingleShot(True)
        self._save_width_timer.setInterval(400)
        self._save_width_timer.timeout.connect(self._save_list_width)
        self.panel_splitter.splitterMoved.connect(self._on_panel_splitter_moved)

    def _on_panel_splitter_moved(self, *_args) -> None:
        self._save_width_timer.start()

    def _save_list_width(self) -> None:
        sizes = self.panel_splitter.sizes()
        if sizes and sizes[0] >= config.MIN_LIST_WIDTH:
            settings.list_width = sizes[0]

    def _connect_signals(self) -> None:
        self.restore_btn.clicked.connect(self.restore_selected)
        self.delete_btn.clicked.connect(self.delete_selected)
        self.clear_btn.clicked.connect(self.clear_trash)
        self.note_list.note_selected.connect(self._update_buttons)
        self.note_list.context_menu_requested.connect(self._show_context_menu)
        self._update_buttons(None)

    # ---------- 刷新 ----------

    def refresh(self) -> None:
        self.note_list.refresh()

    def rebind_database(self, db: Database) -> None:
        """切换存储位置后重新绑定数据库并刷新。"""
        self.db = db
        self.note_list.db = db
        self.refresh()

    def refresh_theme(self) -> None:
        pass

    # ---------- 操作 ----------

    def _update_buttons(self, _note_id) -> None:
        has_selection = self.note_list.selected_note_id() is not None
        self.restore_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def restore_selected(self) -> None:
        note_id = self.note_list.selected_note_id()
        if note_id is None:
            return
        try:
            self.db.restore_note(note_id)
        except Exception:
            logger.exception("恢复笔记失败：%s", note_id)
            return
        self.refresh()

    def delete_selected(self) -> None:
        note_id = self.note_list.selected_note_id()
        if note_id is None:
            return
        box = MessageBox(
            "彻底删除",
            "彻底删除后无法恢复，确定继续吗？",
            self,
        )
        if not box.exec():
            return
        try:
            self.db.delete_permanently(note_id)
        except Exception:
            logger.exception("彻底删除失败：%s", note_id)
            return
        self.refresh()

    def clear_trash(self) -> None:
        box = MessageBox(
            "清空回收站",
            "将彻底删除回收站中的全部笔记，无法恢复。确定继续吗？",
            self,
        )
        if not box.exec():
            return
        try:
            self.db.clear_trash()
        except Exception:
            logger.exception("清空回收站失败")
            return
        self.refresh()

    # ---------- 右键菜单 ----------

    def _show_context_menu(self, note_id: int, pos) -> None:
        menu = RoundMenu(parent=self)
        menu.addAction(
            Action(
                FluentIcon.ADD,
                "恢复",
                triggered=self.restore_selected,
            )
        )
        menu.addSeparator()
        menu.addAction(
            Action(
                FluentIcon.DELETE,
                "彻底删除",
                triggered=self.delete_selected,
            )
        )
        menu.exec(self.note_list.mapToGlobal(pos))

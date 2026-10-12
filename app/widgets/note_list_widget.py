"""笔记列表控件：搜索框 + 自定义列表项。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import FluentIcon, SearchLineEdit

from ..database import Database
from ..models import Note

_ITEM_HEIGHT = 66
_SUMMARY_MAX_LEN = 64


class NoteItemWidget(QWidget):
    """自定义笔记列表项：标题 + 摘要 + 修改时间 + 置顶/收藏标记。"""

    def __init__(self, note: Note, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("noteItemWidget")
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(4)
        self.title_label = QLabel(note.title or "无标题")
        self.title_label.setObjectName("titleLabel")

        self.pin_label = QLabel()
        self.pin_label.setPixmap(FluentIcon.PIN.icon().pixmap(QSize(12, 12)))
        self.pin_label.setToolTip("已置顶")
        self.pin_label.setVisible(note.is_pinned)

        self.fav_label = QLabel()
        self.fav_label.setPixmap(FluentIcon.HEART.icon().pixmap(QSize(12, 12)))
        self.fav_label.setToolTip("已收藏")
        self.fav_label.setVisible(note.is_favorite)

        title_row.addWidget(self.title_label, 1)
        title_row.addWidget(self.pin_label)
        title_row.addWidget(self.fav_label)

        summary = note.summary or "无内容"
        if len(summary) > _SUMMARY_MAX_LEN:
            summary = summary[:_SUMMARY_MAX_LEN] + "…"
        self.summary_label = QLabel(summary)
        self.summary_label.setObjectName("summaryLabel")
        self.summary_label.setWordWrap(False)

        bottom_row = QHBoxLayout()
        self.time_label = QLabel(note.updated_at_display)
        self.time_label.setObjectName("timeLabel")
        bottom_row.addWidget(self.time_label)
        bottom_row.addStretch(1)

        layout.addLayout(title_row)
        layout.addWidget(self.summary_label)
        layout.addLayout(bottom_row)


class NoteListWidget(QWidget):
    """笔记列表：顶部搜索框 + 自定义项列表（支持收藏/回收站模式）。"""

    # 选中笔记变化（None 表示取消选中）
    note_selected = Signal(object)
    # 右键菜单请求：(note_id, 本地坐标)
    context_menu_requested = Signal(int, object)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        db: Database,
        favorite_only: bool = False,
        deleted: bool = False,
    ):
        super().__init__(parent)
        self.db = db
        self.favorite_only = favorite_only
        self.deleted = deleted

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.search_edit = SearchLineEdit(self)
        self.search_edit.setPlaceholderText("搜索标题或内容…")
        self.search_edit.setClearButtonEnabled(True)
        layout.addWidget(self.search_edit)

        self.list_widget = QListWidget(self)
        self.list_widget.setObjectName("noteListWidget")
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_widget.setFrameShape(QListWidget.NoFrame)
        self.list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        layout.addWidget(self.list_widget, 1)

        self.empty_label = QLabel(
            "回收站是空的" if deleted else "暂无笔记", self
        )
        self.empty_label.setObjectName("emptyLabel")
        self.empty_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.empty_label)

        # 信号
        self.search_edit.textChanged.connect(self.refresh)
        self.list_widget.currentItemChanged.connect(self._on_current_item_changed)
        self.list_widget.customContextMenuRequested.connect(
            self._on_context_menu
        )

        self._items: dict[int, QListWidgetItem] = {}
        self.refresh()

    # ---------- 数据 ----------

    def refresh(self, keep_selection: bool = True) -> None:
        """重新加载列表。

        keep_selection 为 True 时尽量保持当前选中；若原选中项已不存在
        （如被删除/过滤），且列表非空，则自动选中第一条并发出选中信号。
        """
        previous_id = self.selected_note_id() if keep_selection else None
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            self._items.clear()
            notes = self.db.list_notes(
                favorite_only=self.favorite_only,
                deleted=self.deleted,
                keyword=self.search_edit.text().strip(),
            )
            for note in notes:
                item = QListWidgetItem()
                item.setData(Qt.UserRole, note.id)
                item.setSizeHint(QSize(0, _ITEM_HEIGHT))
                self.list_widget.addItem(item)
                self.list_widget.setItemWidget(item, NoteItemWidget(note))
                self._items[note.id] = item
            has_items = bool(notes)
            self.list_widget.setVisible(has_items)
            self.empty_label.setVisible(not has_items)
            if previous_id is not None and previous_id in self._items:
                self.list_widget.setCurrentItem(self._items[previous_id])
            elif has_items:
                self.list_widget.setCurrentRow(0)
        finally:
            self.list_widget.blockSignals(False)
        current_id = self.selected_note_id()
        if current_id != previous_id:
            self.note_selected.emit(current_id)

    # ---------- 选中 ----------

    def selected_note_id(self) -> Optional[int]:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def select_note(self, note_id: int) -> None:
        item = self._items.get(note_id)
        if item is not None:
            self.list_widget.setCurrentItem(item)

    def clear_selection(self) -> None:
        self.list_widget.setCurrentItem(None)

    # ---------- 内部信号处理 ----------

    def _on_current_item_changed(self, current, _previous) -> None:
        if current is None:
            self.note_selected.emit(None)
        else:
            self.note_selected.emit(current.data(Qt.UserRole))

    def _on_context_menu(self, pos) -> None:
        item = self.list_widget.itemAt(pos)
        if item is None:
            return
        self.context_menu_requested.emit(item.data(Qt.UserRole), pos)

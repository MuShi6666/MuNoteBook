"""所有笔记页：工具栏 + 笔记列表 + Markdown 编辑器（收藏页复用）。"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    Action,
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    RoundMenu,
    ToolButton,
    TransparentToolButton,
)

from .. import config, document_utils
from ..app_settings import settings
from ..database import Database
from ..markdown_utils import extract_title
from ..models import Note
from ..widgets.markdown_editor import MarkdownEditor
from ..widgets.note_list_widget import NoteListWidget
from ..widgets.pdf_viewer import PdfViewer
from ..widgets.rich_text_editor import RichTextEditor

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

    # ---------- 编辑器路由 ----------

    @property
    def editor(self):
        """当前激活的编辑器（按笔记内容类型）。"""
        return self._active_editor

    def _set_active_editor(self, editor) -> None:
        if editor is self._active_editor:
            return
        self._active_editor = editor
        for candidate in self._editors.values():
            candidate.setVisible(candidate is editor)

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

        # 左侧：工具栏 + 笔记列表（最小宽度受限，初始宽度取持久化值）
        left_widget = QWidget()
        left_widget.setObjectName("listPanel")
        left_widget.setMinimumWidth(config.MIN_LIST_WIDTH)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(16, 12, 8, 12)
        left_layout.setSpacing(8)

        tools_row = QHBoxLayout()
        tools_row.setSpacing(4)
        self.new_btn = ToolButton(FluentIcon.ADD, self)
        self.new_btn.setToolTip("新建笔记")
        self.import_btn = TransparentToolButton(FluentIcon.FOLDER, self)
        self.import_btn.setToolTip("导入文档（md / txt / docx / pdf）")
        self.export_btn = TransparentToolButton(FluentIcon.DOWNLOAD, self)
        self.export_btn.setToolTip("导出当前笔记")
        if self.favorite_only:
            self.new_btn.setVisible(False)
        tools_row.addWidget(self.new_btn)
        tools_row.addWidget(self.import_btn)
        tools_row.addWidget(self.export_btn)
        tools_row.addStretch(1)
        left_layout.addLayout(tools_row)

        self.note_list = NoteListWidget(
            self, db=self.db, favorite_only=self.favorite_only
        )
        left_layout.addWidget(self.note_list, 1)
        self.panel_splitter.addWidget(left_widget)

        # 右侧：按笔记类型路由的编辑器（md / docx / pdf 三选一显示）
        editor_wrap = QWidget()
        editor_layout = QHBoxLayout(editor_wrap)
        editor_layout.setContentsMargins(8, 12, 16, 12)
        editor_layout.setSpacing(0)

        self.markdown_editor = MarkdownEditor(self)
        self.rich_editor = RichTextEditor(self)
        self.pdf_viewer = PdfViewer(self)
        self._editors = {
            "md": self.markdown_editor,
            "docx": self.rich_editor,
            "pdf": self.pdf_viewer,
        }
        self._active_editor = self.markdown_editor
        for editor in self._editors.values():
            editor_layout.addWidget(editor)
            editor.setVisible(editor is self.markdown_editor)
        self.panel_splitter.addWidget(editor_wrap)
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
        self.new_btn.clicked.connect(self.create_note)
        self.import_btn.clicked.connect(self.import_documents)
        self.export_btn.clicked.connect(self._show_export_menu)
        self.note_list.note_selected.connect(self._on_note_selected)
        self.note_list.context_menu_requested.connect(self._show_context_menu)
        # 三个编辑器统一连接（按激活的编辑器分别响应）
        for editor in self._editors.values():
            editor.save_requested.connect(self._on_save_requested)
            editor.favorite_toggled.connect(self._on_favorite_toggled)
            editor.pinned_toggled.connect(self._on_pinned_toggled)
        self.rich_editor.export_requested.connect(
            lambda: self.export_note(self.rich_editor.current_note_id, "docx")
        )
        self.pdf_viewer.export_requested.connect(
            lambda: self.export_note(self.pdf_viewer.current_note_id, "original")
        )

    # ---------- 刷新 ----------

    def refresh(self) -> None:
        self.note_list.refresh()

    def rebind_database(self, db: Database) -> None:
        """切换存储位置后重新绑定数据库并刷新。"""
        self.db = db
        self.note_list.db = db
        self._active_editor.load_note(None)
        self.refresh()

    def refresh_theme(self) -> None:
        for editor in self._editors.values():
            editor.refresh_theme()

    # ---------- 笔记选择 ----------

    def _on_note_selected(self, note_id: Optional[int]) -> None:
        if note_id == self._active_editor.current_note_id:
            return
        self.flush_editor()
        if note_id is None:
            self._active_editor.load_note(None)
            return
        try:
            note = self.db.get_note(note_id)
        except Exception:
            logger.exception("加载笔记失败：%s", note_id)
            note = None
        content_type = (note.content_type if note else None) or "md"
        editor = self._editors.get(content_type, self.markdown_editor)
        self._set_active_editor(editor)
        editor.load_note(note)

    # ---------- 保存 ----------

    def flush_editor(self) -> None:
        """把编辑器未保存内容写入数据库（信号同步落库）。"""
        self.editor.flush()

    def set_auto_save(self, enabled: bool) -> None:
        """同步自动保存开关到本页所有编辑器。"""
        for editor in self._editors.values():
            editor.set_auto_save(enabled)

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

    # ---------- 导入 ----------

    def import_documents(self) -> None:
        """导入本地文档（md / txt / docx / pdf）为对应类型的笔记。

        - md/txt -> Markdown 笔记（现有编辑器）
        - docx   -> Word 富文本笔记（所见即所得编辑）
        - pdf    -> PDF 渲染查看笔记（只读查看）
        """
        path_list, _ = QFileDialog.getOpenFileNames(
            self,
            "导入文档",
            str(Path.home()),
            "文档文件 (*.md *.txt *.docx *.pdf)",
        )
        if not path_list:
            return

        imported_ids: list[int] = []
        failed: list[str] = []
        for path_str in path_list:
            path = Path(path_str)
            extension = path.suffix.lower()
            if extension not in document_utils.SUPPORTED_IMPORT_EXTENSIONS:
                failed.append(path.name)
                continue
            try:
                if extension in (".md", ".txt"):
                    content_type = "md"
                    content = path.read_text(encoding="utf-8", errors="replace")
                    title = extract_title(content, default=path.stem)
                elif extension == ".docx":
                    content_type = "docx"
                    content = document_utils.docx_to_html(path)
                    title = path.stem
                else:  # .pdf
                    content_type = "pdf"
                    content = ""
                    title = path.stem
                library_path = document_utils.save_document_copy(path)
            except Exception:
                logger.exception("导入文档失败：%s", path)
                failed.append(path.name)
                continue
            try:
                note_id = self.db.create_note(
                    title,
                    content,
                    source_path=str(library_path),
                    source_type=extension.lstrip("."),
                    content_type=content_type,
                )
            except Exception:
                logger.exception("导入后创建笔记失败：%s", path)
                failed.append(path.name)
                continue
            imported_ids.append(note_id)

        if imported_ids:
            self.note_list.refresh()
            self.note_list.select_note(imported_ids[0])

        if failed:
            InfoBar.error(
                title="部分导入失败",
                content="、".join(failed),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000,
            )
        elif imported_ids:
            InfoBar.success(
                title="导入完成",
                content=f"成功导入 {len(imported_ids)} 个文档",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2500,
            )

    # ---------- 导出 ----------

    def _current_note(self) -> Optional[Note]:
        """取当前激活编辑器对应的笔记（无选中时提示并返回 None）。"""
        note_id = self._active_editor.current_note_id
        if note_id is None:
            InfoBar.warning(
                title="无法导出",
                content="请先选择一篇笔记",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2000,
            )
            return None
        try:
            return self.db.get_note(note_id)
        except Exception:
            logger.exception("导出前加载笔记失败：%s", note_id)
            return None

    def _show_export_menu(self) -> None:
        """工具栏导出按钮：按当前笔记类型弹出导出菜单。"""
        note = self._current_note()
        if note is None:
            return
        menu = RoundMenu(parent=self)
        if note.content_type == "pdf":
            menu.addAction(
                Action(
                    FluentIcon.SAVE,
                    "另存 PDF 原件",
                    triggered=lambda: self.export_note(note.id, "original"),
                )
            )
        elif note.content_type == "docx":
            menu.addAction(
                Action(
                    FluentIcon.SAVE,
                    "导出 Word (.docx)",
                    triggered=lambda: self.export_note(note.id, "docx"),
                )
            )
            if note.source_path:
                menu.addAction(
                    Action(
                        FluentIcon.FOLDER,
                        "另存原件副本",
                        triggered=lambda: self.export_note(
                            note.id, "original"
                        ),
                    )
                )
        else:
            menu.addAction(
                Action(
                    FluentIcon.DOWNLOAD,
                    "导出 Markdown (.md)",
                    triggered=lambda: self.export_note(note.id, "md"),
                )
            )
            menu.addAction(
                Action(
                    FluentIcon.SAVE,
                    "导出 Word (.docx)",
                    triggered=lambda: self.export_note(note.id, "docx"),
                )
            )
            if note.source_path:
                menu.addAction(
                    Action(
                        FluentIcon.FOLDER,
                        "另存原件副本",
                        triggered=lambda: self.export_note(
                            note.id, "original"
                        ),
                    )
                )
        menu.exec(self.export_btn.mapToGlobal(QPoint(0, self.export_btn.height())))

    def export_note(self, note_id: Optional[int], fmt: str = "md") -> None:
        """导出笔记：md（Markdown）/ docx（Word）/ original（原件副本）。"""
        note = self._current_note() if note_id is None else self._load_note(note_id)
        if note is None:
            return

        if fmt == "original":
            self._export_original(note)
            return

        if fmt == "docx":
            dialog_title, file_filter, suffix = (
                "导出 Word",
                "Word 文档 (*.docx)",
                "docx",
            )
        else:
            dialog_title, file_filter, suffix = (
                "导出 Markdown",
                "Markdown 文件 (*.md)",
                "md",
            )
        default_name = f"{note.title or '未命名笔记'}.{suffix}"
        path, _ = QFileDialog.getSaveFileName(
            self, dialog_title, default_name, file_filter
        )
        if not path:
            return
        try:
            if fmt == "docx":
                if note.content_type == "docx":
                    # 富文本笔记：HTML -> docx
                    data = document_utils.html_to_docx(
                        note.content or "", note.title or ""
                    )
                else:
                    # Markdown 笔记：md -> docx
                    data = document_utils.markdown_to_docx(
                        note.content or "", note.title or ""
                    )
                Path(path).write_bytes(data)
            else:
                Path(path).write_text(note.content or "", encoding="utf-8")
        except Exception:
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

    def _load_note(self, note_id: int) -> Optional[Note]:
        try:
            return self.db.get_note(note_id)
        except Exception:
            logger.exception("加载笔记失败：%s", note_id)
            return None

    def _export_original(self, note: Note) -> None:
        """另存导入文档的原件副本。"""
        if not note.source_path:
            InfoBar.warning(
                title="无原件",
                content="该笔记没有关联的导入原件",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=2500,
            )
            return
        source = Path(note.source_path)
        if not source.is_file():
            InfoBar.error(
                title="原件缺失",
                content="文档库中找不到该原件文件",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            return
        suffix = source.suffix or ".bin"
        default_name = f"{note.title or '未命名笔记'}{suffix}"
        path, _ = QFileDialog.getSaveFileName(
            self, "另存原件副本", default_name, f"原件文件 (*{suffix})"
        )
        if not path:
            return
        try:
            shutil.copy2(source, path)
        except OSError:
            logger.exception("另存原件失败：%s", path)
            InfoBar.error(
                title="另存失败",
                content=f"无法写入文件：{path}",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            return
        InfoBar.success(
            title="另存成功",
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
        if note.content_type == "pdf":
            menu.addAction(
                Action(
                    FluentIcon.SAVE,
                    "另存 PDF 原件",
                    triggered=lambda: self.export_note(note_id, "original"),
                )
            )
        elif note.content_type == "docx":
            menu.addAction(
                Action(
                    FluentIcon.SAVE,
                    "导出 Word (.docx)",
                    triggered=lambda: self.export_note(note_id, "docx"),
                )
            )
            if note.source_path:
                menu.addAction(
                    Action(
                        FluentIcon.FOLDER,
                        "另存原件副本",
                        triggered=lambda: self.export_note(
                            note_id, "original"
                        ),
                    )
                )
        else:
            menu.addAction(
                Action(
                    FluentIcon.DOWNLOAD,
                    "导出 Markdown (.md)",
                    triggered=lambda: self.export_note(note_id, "md"),
                )
            )
            menu.addAction(
                Action(
                    FluentIcon.SAVE,
                    "导出 Word (.docx)",
                    triggered=lambda: self.export_note(note_id, "docx"),
                )
            )
            if note.source_path:
                menu.addAction(
                    Action(
                        FluentIcon.FOLDER,
                        "另存原件副本",
                        triggered=lambda: self.export_note(
                            note_id, "original"
                        ),
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

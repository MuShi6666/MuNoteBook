"""Markdown 编辑器组件：编辑 / 预览 / 双栏 三模式 + 防抖自动保存 + 图片插入。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    FluentIcon,
    InfoBar,
    InfoBarPosition,
    LineEdit,
    SegmentedItem,
    TransparentToolButton,
)

from .. import config, image_utils
from ..markdown_utils import render_preview_html
from ..app_settings import settings

if TYPE_CHECKING:  # pragma: no cover
    from ..models import Note

logger = logging.getLogger(__name__)

_MODE_LABELS = (("编辑", "edit"), ("预览", "preview"), ("双栏", "split"))

_IMAGE_FILE_FILTER = "图片文件 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"


class MarkdownEditArea(QPlainTextEdit):
    """支持图片插入的 Markdown 编辑区。

    - 剪贴板粘贴图片（如截图工具复制的内容）自动存入图片库并插入引用
    - 拖放本地图片文件到编辑区同样自动入库并插入引用
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("editArea")
        self.setAcceptDrops(True)

    # ---------- 剪贴板图片 ----------

    def canInsertFromMimeData(self, source) -> bool:
        if source.hasImage():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:
        if source.hasImage():
            image = source.imageData()
            if isinstance(image, QImage) and not image.isNull():
                try:
                    lib_path = image_utils.save_qimage(image)
                except (OSError, ValueError):
                    logger.exception("保存剪贴板图片失败")
                else:
                    self.insertPlainText(
                        image_utils.image_markdown(lib_path, "粘贴的图片") + "\n"
                    )
                    return
        super().insertFromMimeData(source)

    # ---------- 拖放图片 ----------

    @staticmethod
    def _local_image_paths(mime) -> list[str]:
        """从拖拽数据中提取本地图片文件路径。"""
        paths: list[str] = []
        for url in mime.urls():
            local = url.toLocalFile()
            if local and Path(local).suffix.lower() in image_utils.SUPPORTED_EXTENSIONS:
                paths.append(local)
        return paths

    def dragEnterEvent(self, event) -> None:
        if self._local_image_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if self._local_image_paths(event.mimeData()):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        image_paths = self._local_image_paths(event.mimeData())
        if image_paths:
            for local in image_paths:
                try:
                    markdown = image_utils.import_image_markdown(local)
                except (OSError, FileNotFoundError):
                    logger.exception("导入拖入的图片失败：%s", local)
                    continue
                self.insertPlainText(markdown + "\n")
            event.acceptProposedAction()
            return
        super().dropEvent(event)


class MarkdownEditor(QWidget):
    """Markdown 编辑 + 预览组件。

    - 视图模式：``edit`` / ``preview`` / ``split``
    - 输入防抖（``config.PREVIEW_DEBOUNCE_MS``）后重新渲染预览
    - 输入防抖（``config.SAVE_DEBOUNCE_MS``）后通过 ``save_requested`` 请求保存
    - 切换笔记前调用方应先 ``flush()`` 落盘旧内容
    """

    MODE_EDIT = "edit"
    MODE_PREVIEW = "preview"
    MODE_SPLIT = "split"

    # 防抖后请求保存：(title, content)
    save_requested = Signal(str, str)
    # 视图模式变化
    mode_changed = Signal(str)
    # 收藏 / 置顶切换请求：(note_id, checked)
    favorite_toggled = Signal(int, bool)
    pinned_toggled = Signal(int, bool)
    # 加载了新笔记（None 表示空状态）
    note_loaded = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("markdownEditor")
        self.setMinimumWidth(360)

        self._note_id: Optional[int] = None
        self._loading = False
        self._auto_save = settings.auto_save
        self._mode = settings.editor_mode if settings.editor_mode in {
            self.MODE_EDIT, self.MODE_PREVIEW, self.MODE_SPLIT
        } else self.MODE_SPLIT
        self._segments: dict[str, SegmentedItem] = {}

        self._build_ui()
        self._build_timers()
        self._connect_signals()
        self._apply_mode(self._mode)

    # ---------- UI 构建 ----------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # 顶部工具栏：标题 + 收藏/置顶 + 视图模式切换
        top_bar = QHBoxLayout()
        top_bar.setSpacing(4)

        self.title_edit = LineEdit(self)
        self.title_edit.setObjectName("titleEdit")
        self.title_edit.setPlaceholderText("无标题")
        self.title_edit.setClearButtonEnabled(True)

        self.favorite_btn = TransparentToolButton(FluentIcon.HEART, self)
        self.favorite_btn.setToolTip("收藏")
        self.favorite_btn.setCheckable(True)

        self.pinned_btn = TransparentToolButton(FluentIcon.PIN, self)
        self.pinned_btn.setToolTip("置顶")
        self.pinned_btn.setCheckable(True)

        self.image_btn = TransparentToolButton(FluentIcon.PHOTO, self)
        self.image_btn.setToolTip("插入图片（也可直接粘贴截图或拖入图片文件）")

        for label, key in _MODE_LABELS:
            seg = SegmentedItem(self)
            seg.setText(label)
            seg.setProperty("modeKey", key)
            seg.setToolTip(f"{label}模式")
            seg.clicked.connect(
                lambda _=False, k=key: self._on_segment_clicked(k)
            )
            self._segments[key] = seg

        top_bar.addWidget(self.title_edit, 1)
        top_bar.addWidget(self.favorite_btn)
        top_bar.addWidget(self.pinned_btn)
        top_bar.addWidget(self.image_btn)
        top_bar.addSpacing(10)
        for key in ("edit", "preview", "split"):
            top_bar.addWidget(self._segments[key])
        layout.addLayout(top_bar)

        # 空状态提示
        self.empty_label = QLabel("在左侧选择一篇笔记，或点击「新建」开始记录", self)
        self.empty_label.setObjectName("emptyLabel")
        self.empty_label.setAlignment(Qt.AlignCenter)

        # 编辑区 + 预览区
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.splitter.setChildrenCollapsible(False)

        self.edit_area = MarkdownEditArea(self.splitter)
        self.edit_area.setPlaceholderText(
            "开始用 Markdown 记录吧…\n\n"
            "支持 # 标题、**加粗**、- 列表、> 引用、`代码`、表格等语法"
        )
        self.edit_area.setTabStopDistance(28)
        # 光标加粗为 2px（Win11 风格），保证在深浅主题下都清晰可见
        self.edit_area.setCursorWidth(2)

        self.preview_area = QTextBrowser(self.splitter)
        self.preview_area.setObjectName("previewArea")
        self.preview_area.setOpenExternalLinks(True)
        self.preview_area.setSearchPaths([str(config.APP_ROOT)])

        self.splitter.addWidget(self.edit_area)
        self.splitter.addWidget(self.preview_area)
        self.splitter.setSizes([1, 1])

        layout.addWidget(self.splitter, 1)
        layout.addWidget(self.empty_label, 1)
        self.splitter.setVisible(False)
        self.empty_label.setVisible(True)

    def _build_timers(self) -> None:
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(config.SAVE_DEBOUNCE_MS)
        self._save_timer.timeout.connect(self._on_save_timeout)

        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(config.PREVIEW_DEBOUNCE_MS)
        self._preview_timer.timeout.connect(self._render_preview)

    def _connect_signals(self) -> None:
        self.edit_area.textChanged.connect(self._on_text_changed)
        self.title_edit.textChanged.connect(self._on_title_changed)
        self.title_edit.returnPressed.connect(self._focus_edit_area)
        self.favorite_btn.clicked.connect(self._on_favorite_clicked)
        self.pinned_btn.clicked.connect(self._on_pinned_clicked)
        self.image_btn.clicked.connect(self._on_insert_image)

    def _focus_edit_area(self) -> None:
        """焦点转移到编辑区（标题输入完毕后立即可写正文）。"""
        self.edit_area.setFocus()

    # ---------- 模式切换 ----------

    def _on_segment_clicked(self, key: str) -> None:
        self._apply_mode(key)
        settings.editor_mode = self._mode

    def _apply_mode(self, mode: str) -> None:
        self._mode = mode
        for key, seg in self._segments.items():
            seg.setSelected(key == mode)
        if mode == self.MODE_EDIT:
            self.edit_area.setVisible(True)
            self.preview_area.setVisible(False)
        elif mode == self.MODE_PREVIEW:
            self.edit_area.setVisible(False)
            self.preview_area.setVisible(True)
        else:
            self.edit_area.setVisible(True)
            self.preview_area.setVisible(True)
            self.splitter.setSizes([1, 1])
        if mode != self.MODE_EDIT:
            self._render_preview()
        self.mode_changed.emit(mode)

    @property
    def mode(self) -> str:
        return self._mode

    # ---------- 内容变化与保存 ----------

    def _on_text_changed(self) -> None:
        if self._loading:
            return
        self._schedule_save()
        self._preview_timer.start()

    def _on_title_changed(self, _text: str) -> None:
        if self._loading:
            return
        self._schedule_save()

    def _schedule_save(self) -> None:
        if self._auto_save:
            self._save_timer.start()  # 重启防抖计时

    def _on_save_timeout(self) -> None:
        if self._note_id is None:
            return
        self.save_requested.emit(self.title_edit.text(), self.edit_area.toPlainText())

    def flush(self) -> None:
        """立即触发一次保存（切走当前笔记 / 退出前调用）。"""
        if self._save_timer.isActive():
            self._save_timer.stop()
            self._on_save_timeout()

    def has_unsaved_changes(self) -> bool:
        return self._save_timer.isActive()

    def set_auto_save(self, enabled: bool) -> None:
        self._auto_save = enabled
        if not enabled and self._save_timer.isActive():
            self._save_timer.stop()

    # ---------- 笔记加载 ----------

    def load_note(self, note: Optional["Note"]) -> None:
        """加载笔记；传入 None 进入空状态。"""
        self._loading = True
        try:
            if note is None:
                self._note_id = None
                self.title_edit.setText("")
                self.edit_area.setPlainText("")
                self.favorite_btn.setChecked(False)
                self.pinned_btn.setChecked(False)
                self.splitter.setVisible(False)
                self.empty_label.setVisible(True)
            else:
                self._note_id = note.id
                self.title_edit.setText(note.title or "")
                self.edit_area.setPlainText(note.content or "")
                self.favorite_btn.setChecked(note.is_favorite)
                self.pinned_btn.setChecked(note.is_pinned)
                self.splitter.setVisible(True)
                self.empty_label.setVisible(False)
                # splitter 由隐藏转为显示后，需要重新应用当前模式的
                # 可见性与分割比例，否则预览区可能被压成 0 宽度
                self._apply_mode(self._mode)
                # 加载后聚焦编辑区，使闪烁光标可见、可直接输入
                self.edit_area.setFocus()
        finally:
            self._loading = False
        self._render_preview()
        self.note_loaded.emit(self._note_id)

    @property
    def current_note_id(self) -> Optional[int]:
        return self._note_id

    def set_favorite(self, checked: bool) -> None:
        self.favorite_btn.setChecked(checked)

    def set_pinned(self, checked: bool) -> None:
        self.pinned_btn.setChecked(checked)

    # ---------- 收藏 / 置顶 ----------

    def _on_favorite_clicked(self) -> None:
        if self._note_id is not None:
            self.favorite_toggled.emit(self._note_id, self.favorite_btn.isChecked())

    def _on_pinned_clicked(self) -> None:
        if self._note_id is not None:
            self.pinned_toggled.emit(self._note_id, self.pinned_btn.isChecked())

    # ---------- 图片插入 ----------

    def _on_insert_image(self) -> None:
        """通过文件对话框选择图片，复制进图片库并插入 Markdown 引用。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择图片", str(Path.home()), _IMAGE_FILE_FILTER
        )
        if not path:
            return
        try:
            markdown = image_utils.import_image_markdown(path)
        except (OSError, FileNotFoundError):
            logger.exception("插入图片失败：%s", path)
            InfoBar.error(
                title="插入失败",
                content="无法读取或复制所选图片",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
            return
        self.edit_area.insertPlainText(markdown + "\n")

    # ---------- 预览渲染 ----------

    def _render_preview(self) -> None:
        # 预览区与编辑区一致采用常亮设计（白底深字），故 CSS 固定使用浅色配色
        html_text = render_preview_html(self.edit_area.toPlainText(), dark=False)
        # 设置资源基础 URL，使相对路径图片（images/xxx.png）可正常加载。
        # 注意：路径必须以 "/" 结尾，否则 QUrl 会把它当作文件而非目录，
        # 相对路径解析时会丢失最后一段目录名。
        self.preview_area.document().setBaseUrl(
            QUrl.fromLocalFile(str(config.storage_root()) + "/")
        )
        self.preview_area.setHtml(html_text)

    def refresh_theme(self) -> None:
        """主题变化后刷新预览（编辑区为常亮设计，配色由 QSS 控制）。"""
        self._render_preview()

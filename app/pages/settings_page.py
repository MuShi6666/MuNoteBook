"""设置页：主题模式、主题色、自动保存、存储位置、关于。"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from qfluentwidgets import (
    BodyLabel,
    ComboBox,
    InfoBar,
    InfoBarPosition,
    MessageBox,
    PushButton,
    ScrollArea,
    SubtitleLabel,
    SwitchButton,
)

from .. import __version__, config
from ..app_settings import settings

if TYPE_CHECKING:  # pragma: no cover
    from ..main_window import MainWindow

_THEME_MODES = (("跟随系统", "auto"), ("浅色", "light"), ("深色", "dark"))

_PRESET_COLORS = (
    ("默认蓝", "#0067C0"),
    ("学院紫", "#5B5FC7"),
    ("森林绿", "#0F7B0F"),
    ("砖红", "#C42B1C"),
    ("落日橙", "#9D5D00"),
    ("青蓝", "#0078D4"),
)


class SettingsPage(ScrollArea):
    """设置页面：外观 / 编辑器 / 关于。"""

    def __init__(
        self, parent: Optional[QWidget] = None, *, window: "MainWindow"
    ):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._window = window
        self._color_buttons: list[tuple[QPushButton, str]] = []

        self.view = QWidget()
        self.view.setObjectName("settingsView")
        layout = QVBoxLayout(self.view)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        layout.addWidget(self._build_appearance_group())
        layout.addWidget(self._build_editor_group())
        layout.addWidget(self._build_storage_group())
        layout.addWidget(self._build_about_group())
        layout.addStretch(1)

        self.setWidget(self.view)
        self.setWidgetResizable(True)

    # ---------- 构建 ----------

    def _make_group(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        group = QWidget()
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(8)
        group_layout.addWidget(SubtitleLabel(title))
        return group, group_layout

    def _make_card(self, title: str, content: str = "") -> tuple[QWidget, QHBoxLayout]:
        # 使用原生 QWidget + QSS 背景：CardWidget 的内部绘制会与 QSS 背景冲突，
        # 导致深色主题下背景不刷新；原生 widget 配合 WA_StyledBackground 完全可控。
        card = QWidget()
        card.setObjectName("settingCard")
        card.setAttribute(Qt.WA_StyledBackground, True)
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 12, 16, 12)
        row.setSpacing(12)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.addWidget(BodyLabel(title))
        if content:
            caption = BodyLabel(content)
            caption.setObjectName("captionLabel")
            text_col.addWidget(caption)
        row.addLayout(text_col, 1)
        return card, row

    def _build_appearance_group(self) -> QWidget:
        group, layout = self._make_group("外观")

        # 主题模式
        card, row = self._make_card("主题模式", "浅色、深色或跟随系统")
        self.theme_combo = ComboBox()
        self.theme_combo.addItems([label for label, _ in _THEME_MODES])
        self.theme_combo.setCurrentIndex(self._mode_index(settings.theme_mode))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_mode_changed)
        row.addWidget(self.theme_combo)
        layout.addWidget(card)

        # 主题色
        card, row = self._make_card("主题色", "点击色块即时应用")
        colors_row = QHBoxLayout()
        colors_row.setSpacing(8)
        for name, color in _PRESET_COLORS:
            button = QPushButton()
            button.setFixedSize(24, 24)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(f"{name}（{color}）")
            button.setStyleSheet(self._color_button_style(color))
            button.setProperty("selected", color == settings.theme_color)
            button.clicked.connect(
                lambda _=False, c=color: self._on_color_picked(c)
            )
            colors_row.addWidget(button)
            self._color_buttons.append((button, color))
        row.addLayout(colors_row)
        layout.addWidget(card)

        return group

    def _build_editor_group(self) -> QWidget:
        group, layout = self._make_group("编辑器")

        card, row = self._make_card("自动保存", "停止输入后自动保存到本地数据库")
        self.auto_save_switch = SwitchButton()
        self.auto_save_switch.setChecked(settings.auto_save)
        self.auto_save_switch.checkedChanged.connect(self._on_auto_save_changed)
        row.addWidget(self.auto_save_switch)
        layout.addWidget(card)

        return group

    def _build_storage_group(self) -> QWidget:
        group, layout = self._make_group("存储")

        card, row = self._make_card(
            "存储位置", "笔记数据库、图片库与文档库的存放目录"
        )
        self.storage_path_label = BodyLabel(str(config.storage_root()))
        self.storage_path_label.setObjectName("storagePathLabel")
        self.storage_path_label.setWordWrap(True)
        row.addWidget(self.storage_path_label, 1)
        self.storage_change_btn = PushButton("更改…", self)
        self.storage_change_btn.setToolTip("选择新的存储位置（自动迁移数据）")
        self.storage_change_btn.clicked.connect(self._on_change_storage)
        row.addWidget(self.storage_change_btn)
        layout.addWidget(card)

        card, _ = self._make_card(
            "说明",
            "更改后会把数据库、图片和导入的文档复制到新位置；\n"
            "旧位置的数据会保留，确认无误后可手动删除。",
        )
        layout.addWidget(card)

        return group

    def _on_change_storage(self) -> None:
        """选择新的存储位置并执行迁移。"""
        current = config.storage_root()
        chosen = QFileDialog.getExistingDirectory(
            self, "选择存储位置", str(current)
        )
        if not chosen:
            return
        new_path = Path(chosen).resolve()
        if new_path == current.resolve():
            return

        box = MessageBox(
            "更改存储位置",
            f"将把笔记数据库、图片库和文档库复制到：\n{new_path}\n\n"
            "旧位置的数据会保留，确认无误后可手动删除。\n是否继续？",
            self,
        )
        if not box.exec():
            return

        if self._window.change_storage_location(new_path):
            self.storage_path_label.setText(str(new_path))
            InfoBar.success(
                title="存储位置已更改",
                content=str(new_path),
                parent=self,
                position=InfoBarPosition.TOP,
                duration=3000,
            )
        else:
            InfoBar.error(
                title="更改失败",
                content="迁移过程中出错，已恢复原存储位置",
                parent=self,
                position=InfoBarPosition.TOP,
                duration=4000,
            )

    def _build_about_group(self) -> QWidget:
        group, layout = self._make_group("关于")
        card, _ = self._make_card(
            f"{config.APP_NAME} v{__version__}",
            "基于 PySide6 与 PySide6-Fluent-Widgets 的 Markdown 笔记应用\n"
            "数据存储于本地 SQLite，存储位置可在上方更改",
        )
        layout.addWidget(card)
        return group

    # ---------- 主题 ----------

    @staticmethod
    def _mode_index(mode: str) -> int:
        for index, (_, key) in enumerate(_THEME_MODES):
            if key == mode:
                return index
        return 0

    @staticmethod
    def _color_button_style(color: str) -> str:
        return (
            f"QPushButton {{ background-color: {color}; border-radius: 12px;"
            " border: 2px solid transparent; }"
            "QPushButton:hover { border: 2px solid rgba(128, 128, 128, 0.7); }"
            "QPushButton[selected=true] { border: 2px solid palette(text); }"
        )

    def _on_theme_mode_changed(self, index: int) -> None:
        mode = _THEME_MODES[index][1]
        settings.theme_mode = mode
        self._window.apply_theme(mode)

    def _on_color_picked(self, color: str) -> None:
        settings.theme_color = color
        self._window.apply_theme(settings.theme_mode, color)
        for button, button_color in self._color_buttons:
            button.setProperty("selected", button_color == color)
            button.setStyleSheet(self._color_button_style(button_color))

    # ---------- 编辑器 ----------

    def _on_auto_save_changed(self, checked: bool) -> None:
        settings.auto_save = checked
        self._window.set_auto_save(checked)

    # ---------- 主题联动 ----------

    def refresh_theme(self) -> None:
        """设置页样式由 qfluentwidgets 主题机制处理，无需额外刷新。"""

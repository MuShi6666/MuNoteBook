"""FluentWindow 主窗口：导航注册、页面路由、主题管理。"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication
from qfluentwidgets import (
    FluentIcon,
    FluentWindow,
    NavigationItemPosition,
    SystemThemeListener,
    Theme,
    isDarkTheme,
    setTheme,
    setThemeColor,
)

from . import config
from .database import Database
from .pages.favorites_page import FavoritesPage
from .pages.notes_page import NotesPage
from .pages.settings_page import SettingsPage
from .pages.trash_page import TrashPage
from .app_settings import settings

logger = logging.getLogger(__name__)

_THEME_MAP = {"light": Theme.LIGHT, "dark": Theme.DARK, "auto": Theme.AUTO}

# 主题配色覆盖块：qfluentwidgets 的主题切换不刷新原生/部分控件的背景色
# （如 CardWidget 背景、列表项文字），在此按主题显式补充。
_QSS_THEME_LIGHT = """
/* === 主题配色：浅色 === */
#settingCard { background-color: #ffffff; }
NoteItemWidget QLabel#titleLabel { color: #1a1a1a; }
NoteItemWidget QLabel#summaryLabel { color: #616161; }
NoteItemWidget QLabel#timeLabel { color: #8a8a8a; }
"""

_QSS_THEME_DARK = """
/* === 主题配色：深色 === */
#settingCard { background-color: #2b2b2b; }
NoteItemWidget QLabel#titleLabel { color: #e6e6e6; }
NoteItemWidget QLabel#summaryLabel { color: #a0a0a0; }
NoteItemWidget QLabel#timeLabel { color: #8a8a8a; }
"""


def build_app_qss() -> str:
    """构建应用级 QSS：静态样式 + 当前主题的配色覆盖块。"""
    static = ""
    if config.QSS_PATH.is_file():
        try:
            static = config.QSS_PATH.read_text(encoding="utf-8")
        except OSError:
            logger.exception("读取 QSS 失败：%s", config.QSS_PATH)
    return static + (_QSS_THEME_DARK if isDarkTheme() else _QSS_THEME_LIGHT)


class MainWindow(FluentWindow):
    """应用主窗口：左侧导航 + 右侧堆叠页面。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(config.APP_NAME)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.setMinimumSize(960, 640)

        # 数据层
        self.db = Database(config.DB_PATH)
        self.db.init_schema()

        self._build_pages()
        self._build_navigation()

        # 页面切换：离开笔记页前保存编辑器，并刷新目标页数据
        self.stackedWidget.currentChanged.connect(self._on_current_page_changed)

        # 系统主题变化监听（AUTO 模式下生效）
        self._theme_listener = SystemThemeListener(self)
        self._theme_listener.systemThemeChanged.connect(
            self._on_system_theme_changed
        )
        self._theme_listener.start()

        # 退出前关闭数据库连接
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._on_about_to_quit)

    # ---------- 构建 ----------

    def _build_pages(self) -> None:
        self.notes_page = NotesPage(self, db=self.db, favorite_only=False)
        self.favorites_page = FavoritesPage(self, db=self.db)
        self.trash_page = TrashPage(self, db=self.db)
        self.settings_page = SettingsPage(self, window=self)

    def _build_navigation(self) -> None:
        self.addSubInterface(self.notes_page, FluentIcon.EDIT, "所有笔记")
        self.addSubInterface(self.favorites_page, FluentIcon.HEART, "收藏")
        self.addSubInterface(self.trash_page, FluentIcon.HISTORY, "回收站")
        self.addSubInterface(
            self.settings_page,
            FluentIcon.SETTING,
            "设置",
            position=NavigationItemPosition.BOTTOM,
        )

    # ---------- 页面切换 ----------

    def _on_current_page_changed(self, index: int) -> None:
        # 离开笔记页前把编辑器内容落盘
        self.notes_page.flush_editor()
        widget = self.stackedWidget.widget(index)
        refresh = getattr(widget, "refresh", None)
        if callable(refresh):
            refresh()

    def refresh_all_pages(self) -> None:
        """供页面在数据变更后广播刷新。"""
        for page in (self.notes_page, self.favorites_page, self.trash_page):
            page.refresh()

    # ---------- 主题 ----------

    def apply_theme(self, mode: str, color: Optional[str] = None) -> None:
        """应用主题模式与主题色，并刷新依赖主题的界面元素。"""
        setTheme(_THEME_MAP.get(mode, Theme.AUTO))
        if color:
            try:
                setThemeColor(QColor(color))
            except Exception:
                logger.warning("无效的主题色：%s", color)
        self._refresh_theme_dependents()

    def _on_system_theme_changed(self, _dark: bool) -> None:
        self._refresh_theme_dependents()

    def _refresh_theme_dependents(self) -> None:
        # 重新构建并应用全局 QSS（静态样式 + 当前主题配色）
        app = QApplication.instance()
        if app is not None:
            try:
                app.setStyleSheet(build_app_qss())
            except OSError:
                logger.exception("QSS 应用失败")
        # 通知各页面刷新（编辑器预览样式等）
        for page in (
            self.notes_page,
            self.favorites_page,
            self.trash_page,
            self.settings_page,
        ):
            refresh = getattr(page, "refresh_theme", None)
            if callable(refresh):
                refresh()

    # ---------- 编辑器设置 ----------

    def set_auto_save(self, enabled: bool) -> None:
        """同步自动保存开关到所有编辑器实例。"""
        self.notes_page.editor.set_auto_save(enabled)
        self.favorites_page.editor.set_auto_save(enabled)

    # ---------- 生命周期 ----------

    def closeEvent(self, event) -> None:
        self.notes_page.flush_editor()
        self.favorites_page.flush_editor()
        super().closeEvent(event)

    def _on_about_to_quit(self) -> None:
        try:
            self.db.close()
        except Exception:
            logger.exception("关闭数据库连接失败")

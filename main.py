"""应用入口：初始化 QApplication、主题与 QSS，启动主窗口。"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication
from qfluentwidgets import Theme, setTheme, setThemeColor

from app import config
from app.app_settings import settings
from app.document_utils import SUPPORTED_IMPORT_EXTENSIONS
from app.main_window import MainWindow, build_app_qss

_THEME_MAP = {
    "light": Theme.LIGHT,
    "dark": Theme.DARK,
    "auto": Theme.AUTO,
}


def apply_theme_from_settings() -> None:
    """根据持久化配置应用主题模式与主题色。"""
    setTheme(_THEME_MAP.get(settings.theme_mode, Theme.AUTO))
    try:
        setThemeColor(QColor(settings.theme_color))
    except Exception:
        setThemeColor(QColor(config.DEFAULT_THEME_COLOR))


def load_app_qss(app: QApplication) -> None:
    """加载全局 QSS（静态样式 + 当前主题配色）。"""
    try:
        app.setStyleSheet(build_app_qss())
    except OSError:
        pass


def external_files(argv: list[str]) -> list[str]:
    """从命令行参数筛出存在且受支持的文档路径。

    用于右键「打开方式」把文件路径传给本程序：MuNoteBook.exe "C:\\a.md"
    """
    files: list[str] = []
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue
        path = Path(arg)
        if (
            path.is_file()
            and path.suffix.lower() in SUPPORTED_IMPORT_EXTENSIONS
        ):
            files.append(str(path.resolve()))
    return files


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    if config.LOGO_PATH.is_file():
        app.setWindowIcon(QIcon(str(config.LOGO_PATH)))

    apply_theme_from_settings()
    load_app_qss(app)

    # 主题变化时重新应用 QSS，保证深浅色下样式一致
    window = MainWindow()
    window.show()

    # 通过「打开方式」/ 拖到 exe 上启动时，导入这些文档并选中
    pending = external_files(sys.argv)
    if pending:
        QTimer.singleShot(0, lambda: window.open_document_paths(pending))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

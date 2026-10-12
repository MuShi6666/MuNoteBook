"""记事本 · 程序入口（与主项目 main.py 相互独立）"""
import sys

from PySide6.QtWidgets import QApplication

from qfluentwidgets import Theme, setTheme

from notepad.main_window import MainWindow
from notepad.theme import applyThemeQss, watchThemeChange


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("流畅记事本")

    setTheme(Theme.AUTO)      # 默认跟随系统浅色 / 深色
    applyThemeQss(app)        # 应用全局 QSS
    watchThemeChange(app)     # 主题切换后自动重载 QSS

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

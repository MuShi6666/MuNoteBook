"""主窗口"""
from qfluentwidgets import (
    FluentIcon as FIF,
    FluentWindow,
    NavigationItemPosition,
    Theme,
    isDarkTheme,
    setTheme,
)

from notepad.editor import EditorInterface
from notepad.settings import SettingsInterface


class MainWindow(FluentWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("记事本")
        self.setWindowIcon(FIF.QUICK_NOTE.icon())
        self.resize(1120, 720)
        self.setMinimumSize(760, 540)

        self.editorInterface = EditorInterface(self)
        self.settingsInterface = SettingsInterface(self.editorInterface, self)

        self.addSubInterface(self.editorInterface, FIF.QUICK_NOTE, "记事本")
        self.addSubInterface(
            self.settingsInterface, FIF.SETTING, "设置", NavigationItemPosition.BOTTOM
        )

        self.editorInterface.themeToggleRequested.connect(self._toggleTheme)
        self.settingsInterface.themeModeChanged.connect(self._onThemeModeChanged)
        self.settingsInterface.micaChanged.connect(self.setMicaEffectEnabled)

    def _toggleTheme(self):
        theme = Theme.DARK if isDarkTheme() else Theme.LIGHT
        setTheme(theme)
        self.settingsInterface.setThemeMode(theme)

    def _onThemeModeChanged(self, mode: str):
        setTheme(
            {"light": Theme.LIGHT, "dark": Theme.DARK, "auto": Theme.AUTO}[mode]
        )

    def closeEvent(self, event):
        """关闭前检查未保存的更改"""
        if self.editorInterface.confirmSave():
            super().closeEvent(event)
        else:
            event.ignore()

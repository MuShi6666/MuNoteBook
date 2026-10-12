"""全局 QSS 主题管理

读取 resource/style.qss 模板，按当前浅色 / 深色主题替换颜色占位符，
应用到 QApplication；主题切换时自动重新应用。
"""
from pathlib import Path

from PySide6.QtWidgets import QApplication

from qfluentwidgets import isDarkTheme
from qfluentwidgets.common.config import qconfig

QSS_FILE = Path(__file__).resolve().parent.parent / "resource" / "style.qss"

# 浅色主题配色
LIGHT_PALETTE = {
    "toolbarBg": "#ffffff",
    "findBarBg": "#f6f8fb",
    "editorBg": "#ffffff",
    "statusBarBg": "#f6f8fb",
    "cardBg": "#ffffff",
    "borderColor": "#e3e6ea",
    "hoverBg": "rgba(0, 0, 0, 0.06)",
    "pressedBg": "rgba(0, 0, 0, 0.10)",
    "selectionBg": "#cfe4fa",
    "textColor": "#1b1b1b",
    "secondaryText": "#5c5c5c",
}

# 深色主题配色
DARK_PALETTE = {
    "toolbarBg": "#2b2b2b",
    "findBarBg": "#333333",
    "editorBg": "#1f1f1f",
    "statusBarBg": "#2b2b2b",
    "cardBg": "#2b2b2b",
    "borderColor": "#454545",
    "hoverBg": "rgba(255, 255, 255, 0.08)",
    "pressedBg": "rgba(255, 255, 255, 0.14)",
    "selectionBg": "#3d5a80",
    "textColor": "#f2f2f2",
    "secondaryText": "#b3b3b3",
}


def _render(template: str, palette: dict) -> str:
    """把 @key@ 占位符替换为实际颜色"""
    qss = template
    for key, value in palette.items():
        qss = qss.replace(f"@{key}@", value)
    return qss


def applyThemeQss(app: QApplication) -> None:
    """按当前主题渲染 QSS 并应用到全局"""
    template = QSS_FILE.read_text(encoding="utf-8")
    palette = DARK_PALETTE if isDarkTheme() else LIGHT_PALETTE
    app.setStyleSheet(_render(template, palette))


def themeChangeSignal():
    """取主题变化信号（兼容不同版本）"""
    for name in ("themeChangedFinished", "themeChanged"):
        signal = getattr(qconfig, name, None)
        if signal is not None:
            return signal
    return qconfig.themeMode.valueChanged


def watchThemeChange(app: QApplication) -> None:
    """主题切换后自动重新应用 QSS"""
    themeChangeSignal().connect(lambda: applyThemeQss(app))

"""设置界面"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    ComboBox,
    RadioButton,
    ScrollArea,
    SpinBox,
    StrongBodyLabel,
    Theme,
)
from qfluentwidgets.common.config import qconfig


class SettingsInterface(ScrollArea):
    """设置页面：主题、Mica 背景、编辑器默认项、关于"""

    themeModeChanged = Signal(str)  # "light" / "dark" / "auto"
    micaChanged = Signal(bool)

    def __init__(self, editor, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsInterface")
        self.editor = editor

        self.scrollWidget = QWidget(self)
        layout = QVBoxLayout(self.scrollWidget)
        layout.setContentsMargins(28, 20, 28, 24)
        layout.setSpacing(14)

        layout.addWidget(self._buildAppearanceCard())
        layout.addWidget(self._buildEditorCard())
        layout.addWidget(self._buildAboutCard())
        layout.addStretch(1)

        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)

        self._syncFromEditor()

    # ----------------------------------------------------------
    # 卡片构建
    # ----------------------------------------------------------
    def _card(self, title: str):
        card = QFrame(self.scrollWidget)
        card.setObjectName("settingsCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(12)
        label = StrongBodyLabel(title, card)
        label.setObjectName("settingsCardTitle")
        box.addWidget(label)
        return card, box

    def _buildAppearanceCard(self):
        card, box = self._card("外观")

        row = QHBoxLayout()
        row.setSpacing(20)
        self.lightRadio = RadioButton("浅色", card)
        self.darkRadio = RadioButton("深色", card)
        self.autoRadio = RadioButton("跟随系统", card)
        row.addWidget(self.lightRadio)
        row.addWidget(self.darkRadio)
        row.addWidget(self.autoRadio)
        row.addStretch(1)
        box.addLayout(row)

        # 初始选中项与当前主题保持一致
        try:
            current = qconfig.themeMode.value
        except Exception:
            current = None
        if current == Theme.LIGHT:
            self.lightRadio.setChecked(True)
        elif current == Theme.DARK:
            self.darkRadio.setChecked(True)
        else:
            self.autoRadio.setChecked(True)

        self.lightRadio.clicked.connect(lambda: self.themeModeChanged.emit("light"))
        self.darkRadio.clicked.connect(lambda: self.themeModeChanged.emit("dark"))
        self.autoRadio.clicked.connect(lambda: self.themeModeChanged.emit("auto"))

        self.micaBox = CheckBox("启用 Mica 云母背景（Windows 11 生效）", card)
        window = self.window()
        if hasattr(window, "isMicaEffectEnabled"):
            self.micaBox.setChecked(window.isMicaEffectEnabled())
        self.micaBox.clicked.connect(lambda on: self.micaChanged.emit(on))
        box.addWidget(self.micaBox)
        return card

    def _buildEditorCard(self):
        card, box = self._card("编辑器")

        sizeRow = QHBoxLayout()
        sizeRow.addWidget(BodyLabel("字号", card))
        sizeRow.addStretch(1)
        self.sizeSpin = SpinBox(card)
        self.sizeSpin.setRange(6, 72)
        sizeRow.addWidget(self.sizeSpin)
        box.addLayout(sizeRow)

        fontRow = QHBoxLayout()
        fontRow.addWidget(BodyLabel("字体", card))
        fontRow.addStretch(1)
        self.fontCombo = ComboBox(card)
        self.fontCombo.setFixedWidth(180)
        self.fontCombo.addItems(self.editor.fontFamilies())
        fontRow.addWidget(self.fontCombo)
        box.addLayout(fontRow)

        self.wrapBox = CheckBox("自动换行", card)
        box.addWidget(self.wrapBox)

        # 设置页 -> 编辑器
        self.sizeSpin.valueChanged.connect(self.editor.setFontSize)
        self.fontCombo.currentTextChanged.connect(self.editor.setFontFamily)
        self.wrapBox.clicked.connect(self.editor.setWordWrap)

        # 编辑器（工具栏）改动 -> 同步回设置页
        self.editor.fontSizeChanged.connect(self.sizeSpin.setValue)
        self.editor.fontFamilyChanged.connect(self.fontCombo.setCurrentText)
        self.editor.wordWrapChanged.connect(self.wrapBox.setChecked)
        return card

    def _buildAboutCard(self):
        card, box = self._card("关于")
        box.addWidget(
            BodyLabel("记事本 —— 基于 PySide6 与 PyQt-Fluent-Widgets 构建", card)
        )
        box.addWidget(
            CaptionLabel(
                "支持新建 / 打开 / 保存 / 查找替换 / 字体与主题自定义，界面样式使用 QSS 编写",
                card,
            )
        )
        return card

    def _syncFromEditor(self):
        """把编辑器当前设置同步到设置页"""
        self.sizeSpin.setValue(self.editor.fontSize())
        self.fontCombo.setCurrentText(self.editor.fontFamily())
        self.wrapBox.setChecked(self.editor.wordWrapEnabled())

    def setThemeMode(self, theme: Theme):
        """供外部（如工具栏主题按钮）同步单选状态，不会触发信号"""
        radio = {
            Theme.LIGHT: self.lightRadio,
            Theme.DARK: self.darkRadio,
            Theme.AUTO: self.autoRadio,
        }.get(theme)
        if radio is not None:
            radio.setChecked(True)

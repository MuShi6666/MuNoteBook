"""查找 / 替换栏"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextDocument
from PySide6.QtWidgets import QFrame, QHBoxLayout

from qfluentwidgets import CheckBox, LineEdit, ToolButton, TransparentPushButton
from qfluentwidgets import FluentIcon as FIF


class FindReplaceBar(QFrame):
    """编辑器上方的查找 / 替换工具栏"""

    findNextRequested = Signal()
    findPrevRequested = Signal()
    replaceOneRequested = Signal()
    replaceAllRequested = Signal()
    criteriaChanged = Signal()
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("findBar")
        self.setFixedHeight(46)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(6)

        self.findEdit = LineEdit(self)
        self.findEdit.setPlaceholderText("查找内容")
        self.findEdit.setClearButtonEnabled(True)
        self.findEdit.setFixedWidth(200)

        self.prevBtn = ToolButton(FIF.UP, self)
        self.nextBtn = ToolButton(FIF.DOWN, self)

        self.replaceEdit = LineEdit(self)
        self.replaceEdit.setPlaceholderText("替换为")
        self.replaceEdit.setClearButtonEnabled(True)
        self.replaceEdit.setFixedWidth(200)

        self.replaceBtn = TransparentPushButton(FIF.EDIT, "替换", self)
        self.replaceAllBtn = TransparentPushButton(FIF.SAVE_COPY, "全部替换", self)
        self.caseBox = CheckBox("区分大小写", self)
        self.closeBtn = ToolButton(FIF.CLOSE, self)

        for btn, tip in (
            (self.prevBtn, "上一个 (Shift+F3)"),
            (self.nextBtn, "下一个 (F3)"),
            (self.closeBtn, "关闭 (Esc)"),
        ):
            btn.setToolTip(tip)
            btn.setFixedSize(30, 30)
        self.replaceBtn.setToolTip("替换当前匹配")
        self.replaceAllBtn.setToolTip("替换全部匹配")

        layout.addWidget(self.findEdit)
        layout.addWidget(self.prevBtn)
        layout.addWidget(self.nextBtn)
        layout.addSpacing(10)
        layout.addWidget(self.replaceEdit)
        layout.addWidget(self.replaceBtn)
        layout.addWidget(self.replaceAllBtn)
        layout.addStretch(1)
        layout.addWidget(self.caseBox)
        layout.addWidget(self.closeBtn)

        self.findEdit.returnPressed.connect(self.findNextRequested)
        self.replaceEdit.returnPressed.connect(self.replaceOneRequested)
        self.prevBtn.clicked.connect(self.findPrevRequested)
        self.nextBtn.clicked.connect(self.findNextRequested)
        self.replaceBtn.clicked.connect(self.replaceOneRequested)
        self.replaceAllBtn.clicked.connect(self.replaceAllRequested)
        self.caseBox.clicked.connect(self.criteriaChanged)
        self.findEdit.textChanged.connect(self.criteriaChanged)
        self.closeBtn.clicked.connect(self.closed)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.closed.emit()
        else:
            super().keyPressEvent(event)

    def findText(self) -> str:
        return self.findEdit.text()

    def replaceText(self) -> str:
        return self.replaceEdit.text()

    def findFlags(self) -> QTextDocument.FindFlags:
        """按“区分大小写”复选框生成查找参数"""
        flags = QTextDocument.FindFlags()
        if self.caseBox.isChecked():
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        return flags

"""底部状态栏"""
from PySide6.QtWidgets import QFrame, QHBoxLayout

from qfluentwidgets import CaptionLabel


class StatusBar(QFrame):
    """显示光标位置、行列数、字符 / 字数统计与文件编码"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBar")
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(4)

        self.posLabel = CaptionLabel("行 1，列 1", self)
        self.linesLabel = CaptionLabel("共 1 行", self)
        self.charsLabel = CaptionLabel("字符 0", self)
        self.wordsLabel = CaptionLabel("字数 0", self)
        self.encodingLabel = CaptionLabel("UTF-8", self)

        layout.addWidget(self.posLabel)
        layout.addWidget(self.linesLabel)
        layout.addWidget(self.charsLabel)
        layout.addWidget(self.wordsLabel)
        layout.addStretch(1)
        layout.addWidget(self.encodingLabel)

    def updatePosition(self, line: int, column: int):
        self.posLabel.setText(f"行 {line}，列 {column}")

    def updateStats(self, lines: int, chars: int, words: int):
        self.linesLabel.setText(f"共 {lines} 行")
        self.charsLabel.setText(f"字符 {chars}")
        self.wordsLabel.setText(f"字数 {words}")

    def setEncoding(self, encoding: str):
        self.encodingLabel.setText(encoding.upper())

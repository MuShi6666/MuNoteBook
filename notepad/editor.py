"""记事本编辑器界面：工具栏 + 查找替换栏 + 编辑区 + 状态栏"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTextCursor, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QKeySequence,
    QShortcut,
    QTextCharFormat,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from qfluentwidgets import (
    CheckBox,
    ComboBox,
    FluentIcon as FIF,
    InfoBar,
    InfoBarPosition,
    PlainTextEdit,
    SpinBox,
    ToolButton,
    TransparentPushButton,
    isDarkTheme,
)

from notepad.dialogs import SavePromptBox
from notepad.find_bar import FindReplaceBar
from notepad.status_bar import StatusBar
from notepad.theme import themeChangeSignal
from notepad.utils import displayName, readFile, writeText


class EditorInterface(QWidget):
    """记事本主界面"""

    fontFamilyChanged = Signal(str)
    fontSizeChanged = Signal(int)
    wordWrapChanged = Signal(bool)
    themeToggleRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("editorInterface")
        self.currentPath: str | None = None
        self.encoding = "utf-8"

        self._buildUi()
        self._connectSignals()
        self._initShortcuts()

        self._applyFont()
        self._toggleWrap(self.wrapBox.isChecked())
        self.updateWindowTitle()
        self._updateStats()
        self._updateCursorPos()

    # ----------------------------------------------------------
    # 界面构建
    # ----------------------------------------------------------
    def _buildUi(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._buildToolBar())

        self.findBar = FindReplaceBar(self)
        self.findBar.hide()
        root.addWidget(self.findBar)

        self.editor = PlainTextEdit(self)
        self.editor.setObjectName("noteEditor")
        self.editor.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.editor, 1)

        self.statusBar = StatusBar(self)
        root.addWidget(self.statusBar)

    def _buildToolBar(self) -> QFrame:
        bar = QFrame(self)
        bar.setObjectName("noteToolBar")
        bar.setFixedHeight(52)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        self.newBtn = ToolButton(FIF.ADD, bar)
        self.openBtn = ToolButton(FIF.FOLDER, bar)
        self.saveBtn = ToolButton(FIF.SAVE, bar)
        self.saveAsBtn = ToolButton(FIF.SAVE_AS, bar)
        for btn, tip in (
            (self.newBtn, "新建 (Ctrl+N)"),
            (self.openBtn, "打开 (Ctrl+O)"),
            (self.saveBtn, "保存 (Ctrl+S)"),
            (self.saveAsBtn, "另存为 (Ctrl+Shift+S)"),
        ):
            btn.setToolTip(tip)
            btn.setFixedSize(34, 34)

        self.themeBtn = ToolButton(FIF.PALETTE, bar)
        self.themeBtn.setToolTip("切换浅色 / 深色主题")
        self.themeBtn.setFixedSize(34, 34)

        self.findBtn = TransparentPushButton(FIF.SEARCH, "查找", bar)
        self.wrapBox = CheckBox("自动换行", bar)
        self.wrapBox.setChecked(True)

        self.fontCombo = ComboBox(bar)
        families = QFontDatabase.families()
        self.fontCombo.addItems(families)
        self.fontCombo.setFixedWidth(150)
        if "Microsoft YaHei" in families:
            self.fontCombo.setCurrentText("Microsoft YaHei")
        elif families:
            self.fontCombo.setCurrentText(families[0])

        self.sizeSpin = SpinBox(bar)
        self.sizeSpin.setRange(6, 72)
        self.sizeSpin.setValue(12)
        self.sizeSpin.setFixedWidth(72)

        layout.addWidget(self.newBtn)
        layout.addWidget(self.openBtn)
        layout.addWidget(self.saveBtn)
        layout.addWidget(self.saveAsBtn)
        layout.addSpacing(6)
        layout.addWidget(self.themeBtn)
        layout.addWidget(self.findBtn)
        layout.addSpacing(6)
        layout.addWidget(self.wrapBox)
        layout.addStretch(1)
        layout.addWidget(self.fontCombo)
        layout.addSpacing(6)
        layout.addWidget(self.sizeSpin)
        return bar

    # ----------------------------------------------------------
    # 信号与快捷键
    # ----------------------------------------------------------
    def _connectSignals(self):
        self.newBtn.clicked.connect(self.newFile)
        self.openBtn.clicked.connect(self.openFile)
        self.saveBtn.clicked.connect(self.saveFile)
        self.saveAsBtn.clicked.connect(self.saveFileAs)
        self.themeBtn.clicked.connect(self.themeToggleRequested)
        self.findBtn.clicked.connect(lambda: self.toggleFindBar())
        self.wrapBox.clicked.connect(self._toggleWrap)
        self.fontCombo.currentTextChanged.connect(self._applyFont)
        self.sizeSpin.valueChanged.connect(self._applyFont)

        self.editor.textChanged.connect(self._onTextChanged)
        self.editor.cursorPositionChanged.connect(self._updateCursorPos)

        self.findBar.findNextRequested.connect(self.findNext)
        self.findBar.findPrevRequested.connect(lambda: self.findNext(backward=True))
        self.findBar.replaceOneRequested.connect(self.replaceCurrent)
        self.findBar.replaceAllRequested.connect(self.replaceAll)
        self.findBar.criteriaChanged.connect(self._highlightMatches)
        self.findBar.closed.connect(lambda: self.toggleFindBar(False))

        # 主题切换后刷新匹配高亮颜色
        themeChangeSignal().connect(self._highlightMatches)

    def _initShortcuts(self):
        QShortcut(QKeySequence.StandardKey.New, self, self.newFile)
        QShortcut(QKeySequence.StandardKey.Open, self, self.openFile)
        QShortcut(QKeySequence.StandardKey.Save, self, self.saveFile)
        QShortcut(QKeySequence.StandardKey.SaveAs, self, self.saveFileAs)
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.toggleFindBar(True))
        QShortcut(QKeySequence("F3"), self, self.findNext)
        QShortcut(QKeySequence("Shift+F3"), self, lambda: self.findNext(backward=True))
        QShortcut(QKeySequence("Ctrl+H"), self, self.focusReplace)

    # ----------------------------------------------------------
    # 文件操作
    # ----------------------------------------------------------
    def isModified(self) -> bool:
        return self.editor.document().isModified()

    def newFile(self):
        if not self.confirmSave():
            return
        self.editor.setPlainText("")
        self.editor.document().setModified(False)
        self.currentPath = None
        self.encoding = "utf-8"
        self.statusBar.setEncoding(self.encoding)
        self.updateWindowTitle()
        self._updateStats()
        self.editor.setFocus()

    def openFile(self):
        if not self.confirmSave():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "", "文本文件 (*.txt);;Markdown (*.md);;所有文件 (*.*)"
        )
        if not path:
            return
        try:
            text, encoding = readFile(path)
        except OSError as e:
            self._showError("打开失败", f"{displayName(path)}：{e}")
            return

        self.editor.setPlainText(text)
        self.editor.document().setModified(False)
        self.currentPath = path
        self.encoding = encoding
        self.statusBar.setEncoding(encoding)
        self.updateWindowTitle()
        self._updateStats()
        self._showSuccess("已打开", displayName(path))

    def saveFile(self) -> bool:
        if self.currentPath is None:
            return self.saveFileAs()
        return self.writeFile(self.currentPath)

    def saveFileAs(self) -> bool:
        default = self.currentPath or str(Path.home() / "未命名.txt")
        path, _ = QFileDialog.getSaveFileName(
            self, "另存为", default, "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if not path:
            return False
        return self.writeFile(path)

    def writeFile(self, path: str) -> bool:
        try:
            writeText(path, self.editor.toPlainText())
        except OSError as e:
            self._showError("保存失败", f"{displayName(path)}：{e}")
            return False

        self.editor.document().setModified(False)
        self.currentPath = path
        self.encoding = "utf-8"
        self.statusBar.setEncoding(self.encoding)
        self.updateWindowTitle()
        self._showSuccess("已保存", displayName(path))
        return True

    def confirmSave(self) -> bool:
        """有未保存更改时弹窗确认，返回是否可以继续下一步操作"""
        if not self.isModified():
            return True
        box = SavePromptBox(displayName(self.currentPath), self.window())
        box.exec()
        if box.choice == SavePromptBox.SAVE:
            return self.saveFile()
        return box.choice == SavePromptBox.DISCARD

    def updateWindowTitle(self):
        name = displayName(self.currentPath)
        mark = "*" if self.isModified() else ""
        self.window().setWindowTitle(f"{mark}{name} - 记事本")

    # ----------------------------------------------------------
    # 查找 / 替换
    # ----------------------------------------------------------
    def toggleFindBar(self, show: bool | None = None):
        visible = self.findBar.isVisible() if show is None else show
        self.findBar.setVisible(visible)
        if visible:
            selected = self.editor.textCursor().selectedText()
            if selected and "\u2029" not in selected:
                self.findBar.findEdit.setText(selected)
            self.findBar.findEdit.setFocus()
            self.findBar.findEdit.selectAll()
            self._highlightMatches()
        else:
            self.editor.setExtraSelections([])
            self.editor.setFocus()

    def focusReplace(self):
        self.toggleFindBar(True)
        self.findBar.replaceEdit.setFocus()

    def _highlightMatches(self):
        """高亮所有匹配项"""
        if not self.findBar.isVisible():
            return
        text = self.findBar.findText()
        selections = []
        if text:
            color = QColor("#3d5a80") if isDarkTheme() else QColor("#cfe4fa")
            doc = self.editor.document()
            cursor = doc.find(text, QTextCursor(doc), self.findBar.findFlags())
            while not cursor.isNull():
                selection = QTextEdit.ExtraSelection()
                selection.cursor = cursor
                selection.format = QTextCharFormat()
                selection.format.setBackground(color)
                selections.append(selection)
                cursor = doc.find(text, cursor, self.findBar.findFlags())
        self.editor.setExtraSelections(selections)

    def findNext(self, backward: bool = False):
        text = self.findBar.findText()
        if not text:
            return

        flags = self.findBar.findFlags()
        if backward:
            flags |= QTextDocument.FindFlag.FindBackward

        # 从当前选中处之后（向前则从之前）开始找
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == text:
            start = cursor.selectionStart() if backward else cursor.selectionEnd()
        else:
            start = cursor.position()

        fromCursor = QTextCursor(self.editor.document())
        fromCursor.setPosition(start)
        found = self.editor.document().find(text, fromCursor, flags)

        if found.isNull():
            # 到头了循环到另一端继续找
            wrapCursor = QTextCursor(self.editor.document())
            if backward:
                wrapCursor.movePosition(QTextCursor.MoveOperation.End)
            found = self.editor.document().find(text, wrapCursor, flags)

        if found.isNull():
            self._showWarning("未找到", f"找不到 “{text}”")
            return
        self.editor.setTextCursor(found)
        self.editor.centerCursor()

    def replaceCurrent(self):
        text = self.findBar.findText()
        if not text:
            return
        cursor = self.editor.textCursor()
        if cursor.hasSelection() and cursor.selectedText() == text:
            cursor.insertText(self.findBar.replaceText())
        self.findNext()

    def replaceAll(self):
        text = self.findBar.findText()
        if not text:
            return
        replacement = self.findBar.replaceText()
        doc = self.editor.document()
        flags = self.findBar.findFlags()

        cursor = doc.find(text, QTextCursor(doc), flags)
        if cursor.isNull():
            self._showWarning("未找到", f"找不到 “{text}”")
            return

        count = 0
        editCursor = self.editor.textCursor()
        editCursor.beginEditBlock()
        while not cursor.isNull():
            cursor.insertText(replacement)
            count += 1
            cursor = doc.find(text, cursor, flags)
        editCursor.endEditBlock()

        self._highlightMatches()
        self._updateStats()
        self._showSuccess("替换完成", f"共替换 {count} 处")

    # ----------------------------------------------------------
    # 字体 / 换行
    # ----------------------------------------------------------
    def _applyFont(self):
        family = self.fontCombo.currentText()
        size = self.sizeSpin.value()
        if not family:
            return
        self.editor.setFont(QFont(family, size))
        self.fontFamilyChanged.emit(family)
        self.fontSizeChanged.emit(size)

    def _toggleWrap(self, on: bool):
        self.editor.setLineWrapMode(
            PlainTextEdit.WidgetWidth if on else PlainTextEdit.NoWrap
        )
        self.wordWrapChanged.emit(on)

    def fontFamilies(self) -> list[str]:
        return QFontDatabase.families()

    def fontSize(self) -> int:
        return self.sizeSpin.value()

    def fontFamily(self) -> str:
        return self.fontCombo.currentText()

    def wordWrapEnabled(self) -> bool:
        return self.wrapBox.isChecked()

    def setFontSize(self, size: int):
        self.sizeSpin.setValue(size)

    def setFontFamily(self, family: str):
        self.fontCombo.setCurrentText(family)

    def setWordWrap(self, on: bool):
        self.wrapBox.setChecked(on)
        self._toggleWrap(on)

    # ----------------------------------------------------------
    # 状态栏与提示
    # ----------------------------------------------------------
    def _onTextChanged(self):
        self.updateWindowTitle()
        self._updateStats()

    def _updateCursorPos(self):
        cursor = self.editor.textCursor()
        self.statusBar.updatePosition(cursor.blockNumber() + 1, cursor.columnNumber() + 1)

    def _updateStats(self):
        text = self.editor.toPlainText()
        self.statusBar.updateStats(
            lines=self.editor.document().blockCount(),
            chars=len(text),
            words=len(text.split()),
        )

    def _showSuccess(self, title: str, content: str):
        InfoBar.success(
            title, content,
            parent=self.window(), position=InfoBarPosition.TOP, duration=1500,
        )

    def _showError(self, title: str, content: str):
        InfoBar.error(
            title, content,
            parent=self.window(), position=InfoBarPosition.TOP, duration=3000,
        )

    def _showWarning(self, title: str, content: str):
        InfoBar.warning(
            title, content,
            parent=self.window(), position=InfoBarPosition.TOP, duration=1500,
        )

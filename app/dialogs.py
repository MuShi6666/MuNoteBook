"""自定义对话框"""
from qfluentwidgets import BodyLabel, MessageBoxBase, PushButton, TitleLabel


class SavePromptBox(MessageBoxBase):
    """新建 / 打开 / 关闭前的“未保存更改”确认框

    提供 保存 / 不保存 / 取消 三个选项，
    结果通过 self.choice 读取：SavePromptBox.SAVE / DISCARD / CANCEL。
    """

    SAVE = "save"
    DISCARD = "discard"
    CANCEL = "cancel"

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.choice = self.CANCEL

        self.titleLabel = TitleLabel("未保存的更改", self)
        self.contentLabel = BodyLabel(f"“{name}” 有尚未保存的更改，是否保存？", self)
        self.viewLayout.addWidget(self.titleLabel)
        self.viewLayout.addWidget(self.contentLabel)

        # 调整按钮顺序为：保存 / 不保存 / 取消
        self.buttonLayout.removeWidget(self.yesButton)
        self.buttonLayout.removeWidget(self.cancelButton)
        self.noButton = PushButton("不保存", self.buttonGroup)
        self.buttonLayout.addWidget(self.yesButton)
        self.buttonLayout.addWidget(self.noButton)
        self.buttonLayout.addWidget(self.cancelButton)

        self.yesButton.setText("保存")
        self.cancelButton.setText("取消")

        self.yesButton.clicked.connect(self._onSave)
        self.noButton.clicked.connect(self._onDiscard)
        self.cancelButton.clicked.connect(self._onCancel)

    def _onSave(self):
        self.choice = self.SAVE
        # 确定按钮默认会 accept() 关闭对话框

    def _onDiscard(self):
        self.choice = self.DISCARD
        self.reject()

    def _onCancel(self):
        self.choice = self.CANCEL
        # 取消按钮默认会 reject() 关闭对话框

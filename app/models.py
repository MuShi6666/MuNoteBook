"""数据模型定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Note:
    """笔记实体。

    ``content`` 仅在详情查询（get_note）时填充完整正文；
    列表查询只带回 ``summary``（正文截断摘要），以保证列表性能。
    """

    id: int
    title: str
    created_at: str
    updated_at: str
    is_pinned: bool = False
    is_favorite: bool = False
    is_deleted: bool = False
    summary: str = ""
    content: str | None = field(default=None, repr=False)
    # 导入文档的来源信息（可选）：库内原件路径与文档类型（md/txt/docx/pdf）
    source_path: str | None = None
    source_type: str | None = None
    # 内容类型：md（Markdown）/ docx（Word 富文本）/ pdf（渲染查看）
    content_type: str = "md"

    @property
    def updated_at_display(self) -> str:
        """友好显示修改时间：今天 HH:MM / 昨天 HH:MM / MM-DD / YYYY-MM-DD。"""
        try:
            dt = datetime.fromisoformat(self.updated_at)
        except (ValueError, TypeError):
            return self.updated_at or ""
        now = datetime.now()
        delta_days = (now.date() - dt.date()).days
        if delta_days == 0:
            return f"今天 {dt.strftime('%H:%M')}"
        if delta_days == 1:
            return f"昨天 {dt.strftime('%H:%M')}"
        if dt.year == now.year:
            return dt.strftime("%m-%d %H:%M")
        return dt.strftime("%Y-%m-%d")

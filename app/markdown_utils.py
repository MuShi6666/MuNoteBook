"""Markdown 渲染与文本处理工具。

- markdown_to_html / render_preview_html：Markdown -> HTML（含主题样式）
- extract_title：从正文提取标题（首个 Markdown 标题或首行文本）
- make_summary：生成列表摘要
"""

from __future__ import annotations

import html
import logging
import re

logger = logging.getLogger(__name__)

try:
    import markdown as _markdown
except ImportError:  # pragma: no cover - 依赖缺失时降级为纯文本
    _markdown = None
    logger.warning("未安装 markdown 库，预览将降级为纯文本显示")

_EXTENSIONS = ["tables", "fenced_code", "sane_lists", "nl2br"]

# 预览样式：颜色用占位符按主题替换（QTextBrowser 仅支持少量 CSS）
_BASE_CSS = """
body {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: 14px; color: __TEXT_COLOR__; line-height: 1.65; margin: 0;
}
h1, h2, h3, h4, h5, h6 { font-weight: 600; margin: 14px 0 6px; }
h1 { font-size: 22px; } h2 { font-size: 18px; } h3 { font-size: 16px; }
p { margin: 6px 0; }
a { color: #0067c0; text-decoration: none; }
code {
    font-family: Consolas, "Courier New", monospace; font-size: 13px;
    background: rgba(127, 127, 127, 0.16); border-radius: 4px; padding: 1px 5px;
}
pre { background: rgba(127, 127, 127, 0.12); border-radius: 8px; padding: 10px 12px; }
pre code { background: transparent; padding: 0; }
blockquote {
    margin: 8px 0; padding: 2px 12px; color: __QUOTE_COLOR__;
    border-left: 3px solid #0067c0; background: rgba(0, 103, 192, 0.07);
    border-radius: 0 6px 6px 0;
}
table { border-collapse: collapse; margin: 8px 0; }
th, td { border: 1px solid rgba(127, 127, 127, 0.35); padding: 5px 10px; }
th { background: rgba(127, 127, 127, 0.12); }
hr { border: none; border-top: 1px solid rgba(127, 127, 127, 0.3); margin: 12px 0; }
img { max-width: 100%; }
ul, ol { margin: 6px 0; padding-left: 24px; }
"""

_TITLE_PATTERN = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*$")
_LINK_PATTERN = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")


def preview_css(*, dark: bool) -> str:
    """按主题生成预览 CSS。"""
    text_color = "#d6d6d6" if dark else "#1a1a1a"
    quote_color = "#9a9a9a" if dark else "#616161"
    return (
        _BASE_CSS.replace("__TEXT_COLOR__", text_color)
        .replace("__QUOTE_COLOR__", quote_color)
    )


def markdown_to_html(text: str) -> str:
    """Markdown 文本转 HTML 片段；markdown 库缺失时降级为转义纯文本。"""
    if not text or not text.strip():
        return ""
    if _markdown is None:
        return html.escape(text).replace("\n", "<br>")
    try:
        return _markdown.markdown(text, extensions=_EXTENSIONS)
    except Exception:
        logger.exception("Markdown 渲染失败，降级为纯文本")
        return html.escape(text).replace("\n", "<br>")


def render_preview_html(text: str, *, dark: bool) -> str:
    """生成可直接喂给 QTextBrowser.setHtml 的完整 HTML 文档。"""
    body = markdown_to_html(text)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{preview_css(dark=dark)}</style></head>"
        f"<body>{body}</body></html>"
    )


def _clean_inline(text: str) -> str:
    """去掉行内 Markdown 标记，保留可读文本。"""
    text = _LINK_PATTERN.sub(r"\1", text)
    text = re.sub(r"[*_`]", "", text)
    return text.strip()


def extract_title(content: str, default: str = "未命名笔记", max_len: int = 80) -> str:
    """从正文提取标题：优先首个 Markdown 标题，否则首个非空行。"""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = _TITLE_PATTERN.match(line)
        if match:
            return _clean_inline(match.group(1))[:max_len] or default
        return _clean_inline(stripped)[:max_len] or default
    return default


def make_summary(content: str, max_len: int = 200) -> str:
    """生成列表摘要：去掉 Markdown 标记并压缩空白。"""
    text = _LINK_PATTERN.sub(" ", content)
    text = re.sub(r"[#>*`~_\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]

"""图片库管理：笔记图片的存储、Markdown 引用与清理。

图片统一复制到项目根目录 ``notes_images/`` 下，Markdown 中以相对路径
``images/<文件名>`` 引用。这样数据库文件可随意迁移，图片与数据分离。
"""

from __future__ import annotations

import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import Union

from PySide6.QtGui import QImage

from . import config

logger = logging.getLogger(__name__)

# 支持的图片扩展名（拖放/对话框过滤与剪贴板保存均以此为准）
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")

# Markdown 图片语法：![alt](images/xxx.png)
_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(\s*(images/[^)\s]+?)\s*\)")
# HTML 图片语法（富文本编辑器）：<img src="images/xxx.png" ...>
_HTML_IMAGE_PATTERN = re.compile(
    r"""<img[^>]+src=["'](images/[^"'\s>]+?)["']""", re.IGNORECASE
)


def ensure_images_dir() -> Path:
    """确保图片库目录存在并返回。"""
    config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    return config.IMAGES_DIR


def _unique_name(extension: str) -> str:
    ext = extension.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        ext = ".png"
    return f"{uuid.uuid4().hex}{ext}"


def save_image_file(src: Union[str, Path]) -> Path:
    """把外部图片文件复制进图片库，返回库内文件路径。"""
    src_path = Path(src)
    if not src_path.is_file():
        raise FileNotFoundError(f"图片不存在：{src}")
    ensure_images_dir()
    dest = config.IMAGES_DIR / _unique_name(src_path.suffix)
    shutil.copy2(src_path, dest)
    return dest


def save_qimage(image: QImage) -> Path:
    """把内存中的 QImage（如剪贴板截图）保存进图片库，返回库内路径。"""
    if image.isNull():
        raise ValueError("空图片，无法保存")
    ensure_images_dir()
    dest = config.IMAGES_DIR / _unique_name(".png")
    if not image.save(str(dest), "PNG"):
        raise OSError(f"图片保存失败：{dest}")
    return dest


def image_markdown(lib_path: Path, alt: str = "") -> str:
    """生成库内图片的 Markdown 引用（相对路径，如 ``images/abc.png``）。"""
    try:
        relative = Path(lib_path).resolve().relative_to(config.APP_ROOT.resolve())
        target = relative.as_posix()
    except ValueError:
        target = f"images/{Path(lib_path).name}"
    return f"![{alt}]({target})"


def import_image_markdown(src: Union[str, Path], alt: str = "") -> str:
    """复制外部图片到图片库并返回其 Markdown 引用。"""
    return image_markdown(save_image_file(src), alt)


def save_image_bytes(data: bytes, extension: str = ".png") -> Path:
    """把图片字节流（如 docx 内嵌图片）保存进图片库，返回库内路径。"""
    ensure_images_dir()
    dest = config.IMAGES_DIR / _unique_name(extension)
    dest.write_bytes(data)
    return dest


def library_relative_src(lib_path: Path) -> str:
    """库内图片相对存储根目录的 posix 路径（供 HTML img src 使用）。"""
    try:
        relative = Path(lib_path).resolve().relative_to(
            config.storage_root().resolve()
        )
        return relative.as_posix()
    except ValueError:
        return f"images/{Path(lib_path).name}"


def image_html(lib_path: Path, alt: str = "") -> str:
    """生成库内图片的 HTML img 标签（相对路径 src）。"""
    safe_alt = html.escape(alt or "", quote=True)
    return f'<img src="{library_relative_src(lib_path)}" alt="{safe_alt}" />'


def import_image_html(src: Union[str, Path], alt: str = "") -> str:
    """复制外部图片到图片库并返回其 HTML img 标签。"""
    return image_html(save_image_file(src), alt)


def extract_image_paths(content: str) -> list[Path]:
    """提取内容（Markdown 或 HTML）引用的库内图片绝对路径。

    仅返回位于图片库目录内的路径（带目录安全检查），
    外链图片与其他目录的本地图片不在清理范围。
    """
    paths: list[Path] = []
    if not content:
        return paths
    storage_root = config.storage_root().resolve()
    images_root = config.images_dir().resolve()
    for pattern in (_IMAGE_PATTERN, _HTML_IMAGE_PATTERN):
        for match in pattern.finditer(content):
            candidate = (storage_root / match.group(1)).resolve()
            try:
                candidate.relative_to(images_root)
            except ValueError:
                continue
            if candidate not in paths:
                paths.append(candidate)
    return paths


def remove_images_in_content(content: str) -> int:
    """删除一段内容（Markdown 或 HTML）引用的库内图片文件。"""
    removed = 0
    for path in extract_image_paths(content):
        try:
            path.unlink()
            removed += 1
        except OSError:
            logger.warning("删除图片失败：%s", path)
    return removed

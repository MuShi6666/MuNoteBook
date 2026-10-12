"""全局配置与常量。

存储位置（数据库/图片库/文档库）支持在设置中更改：
默认位于项目根目录，用户可切换到其他目录。
路径通过 ``storage_root()`` 动态解析，兼容旧引用
（``config.DB_PATH`` 等经模块级 ``__getattr__`` 转发）。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QStandardPaths

APP_NAME = "MuNoteBook"
APP_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
QSS_PATH = RESOURCES_DIR / "style.qss"
LOGO_PATH = RESOURCES_DIR / "logo.png"


def is_frozen() -> bool:
    """是否处于 PyInstaller 打包后的运行环境。"""
    return getattr(sys, "frozen", False)


def user_data_dir() -> Path:
    """打包运行时用户可写的数据目录（避免 Program Files 无写权限）。

    优先使用 AppData/Local 下的应用目录；取不到时回退到文档目录。
    """
    loc = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    if not loc:
        loc = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
    base = Path(loc) if loc else (APP_ROOT / "data")
    return base / APP_NAME

# 编辑器防抖间隔（毫秒）
SAVE_DEBOUNCE_MS = 400
PREVIEW_DEBOUNCE_MS = 250

# 笔记列表摘要截断长度
SUMMARY_LENGTH = 200

# 窗口与布局
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
LIST_WIDTH = 320
MIN_LIST_WIDTH = 280

# 主题默认值
DEFAULT_THEME_MODE = "auto"  # light / dark / auto
DEFAULT_THEME_COLOR = "#0067C0"

# 配置文件（JSON）。开发态固定在项目根目录；打包后改到用户数据目录
# （Program Files 下无写权限）。
CONFIG_PATH = (
    user_data_dir() / "app_config.json" if is_frozen() else APP_ROOT / "app_config.json"
)

# 数据目录名（位于存储根目录下）
DB_FILENAME = "notes.db"
IMAGES_DIRNAME = "images"
DOCUMENTS_DIRNAME = "documents"

# 当前存储根目录（None 表示未初始化，取用户设置或默认项目根目录）
_storage_root: Optional[Path] = None


def storage_root() -> Path:
    """当前数据存储根目录（默认项目根目录，可在设置中更改）。

    打包运行（已安装）时默认使用用户数据目录，避免写入 Program Files。
    """
    global _storage_root
    if _storage_root is None:
        from .app_settings import settings  # 延迟导入避免循环依赖

        custom = settings.storage_dir
        if custom:
            _storage_root = Path(custom).resolve()
        elif is_frozen():
            _storage_root = user_data_dir()
        else:
            _storage_root = APP_ROOT
        _storage_root.mkdir(parents=True, exist_ok=True)
    return _storage_root


def set_storage_root(path: Optional[Path | str]) -> None:
    """切换数据存储根目录（调用方负责数据迁移与界面刷新）。"""
    global _storage_root
    _storage_root = Path(path).resolve() if path else None


def db_path() -> Path:
    """数据库文件路径。"""
    return storage_root() / DB_FILENAME


def images_dir() -> Path:
    """图片库目录路径。"""
    return storage_root() / IMAGES_DIRNAME


def documents_dir() -> Path:
    """文档库目录路径。"""
    return storage_root() / DOCUMENTS_DIRNAME


def __getattr__(name: str):
    """兼容旧引用：config.DB_PATH / config.IMAGES_DIR / config.DOCUMENTS_DIR。"""
    if name == "DB_PATH":
        return db_path()
    if name == "IMAGES_DIR":
        return images_dir()
    if name == "DOCUMENTS_DIR":
        return documents_dir()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""全局配置与常量。"""

from __future__ import annotations

from pathlib import Path

APP_NAME = "Fluent 记事本"
APP_ROOT = Path(__file__).resolve().parent.parent
RESOURCES_DIR = Path(__file__).resolve().parent / "resources"
QSS_PATH = RESOURCES_DIR / "style.qss"
DB_PATH = APP_ROOT / "notes.db"

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

# 图片库：笔记引用的图片统一复制到此目录（Markdown 中以 images/ 相对路径引用，
# 与目录名保持一致，确保预览渲染与删除清理的路径链路正确）
IMAGES_DIR = APP_ROOT / "images"

# 配置文件（JSON）
CONFIG_PATH = APP_ROOT / "app_config.json"

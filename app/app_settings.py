"""应用设置管理：以 JSON 文件持久化用户配置（主题、自动保存等）。

注意：模块名为 ``app_settings`` 以避免与旧版实验文件 ``app/settings.py`` 冲突。
"""

from __future__ import annotations

import json
import threading

from . import config

_DEFAULTS = {
    "theme_mode": config.DEFAULT_THEME_MODE,      # light / dark / auto
    "theme_color": config.DEFAULT_THEME_COLOR,    # 主题色（十六进制）
    "auto_save": True,                            # 编辑器自动保存开关
    "editor_mode": "split",                       # 编辑器视图：edit / preview / split
}


class AppSettings:
    """单例设置管理器，所有读写均落在 JSON 文件中。"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> "AppSettings":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._data = dict(_DEFAULTS)
                    instance.load()
                    cls._instance = instance
        return cls._instance

    # ---------- 持久化 ----------

    @property
    def config_path(self):
        return config.CONFIG_PATH

    def load(self) -> None:
        path = self.config_path
        if not path.is_file():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if isinstance(data, dict):
            for key, value in data.items():
                if key in _DEFAULTS:
                    self._data[key] = value

    def save(self) -> None:
        try:
            self.config_path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass

    # ---------- 通用读写 ----------

    def get(self, key: str):
        return self._data.get(key, _DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        self._data[key] = value
        self.save()

    # ---------- 常用属性 ----------

    @property
    def theme_mode(self) -> str:
        return self.get("theme_mode")

    @theme_mode.setter
    def theme_mode(self, value: str) -> None:
        self.set("theme_mode", value)

    @property
    def theme_color(self) -> str:
        return self.get("theme_color")

    @theme_color.setter
    def theme_color(self, value: str) -> None:
        self.set("theme_color", value)

    @property
    def auto_save(self) -> bool:
        return bool(self.get("auto_save"))

    @auto_save.setter
    def auto_save(self, value: bool) -> None:
        self.set("auto_save", bool(value))

    @property
    def editor_mode(self) -> str:
        return self.get("editor_mode")

    @editor_mode.setter
    def editor_mode(self, value: str) -> None:
        self.set("editor_mode", value)


settings = AppSettings()

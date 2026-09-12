"""
配置管理器

使用 YAML 作为配置存储格式，支持：
- 默认配置与用户配置分层合并
- 运行时读写
- 配置变更通知
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from copy import deepcopy


class ConfigManager:
    """
    分层配置管理器。

    配置优先级：用户配置 > 默认配置

    使用方式:
        cm = ConfigManager()
        cm.load()
        theme = cm.get("appearance.theme")
        cm.set("appearance.theme", "dark")
        cm.save()
    """

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path.home() / ".aovow"
        self._config_dir = config_dir
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._user_config_path = self._config_dir / "settings.yaml"

        # 默认配置路径（框架内置）
        self._defaults_path = Path(__file__).parent / "defaults.yaml"

        # 配置数据
        self._data: Dict[str, Any] = {}
        self._defaults: Dict[str, Any] = {}

    def load(self):
        """加载配置（默认配置 + 用户配置合并）"""
        # 加载默认配置
        if self._defaults_path.exists():
            with open(self._defaults_path, 'r', encoding='utf-8') as f:
                self._defaults = yaml.safe_load(f) or {}

        # 加载用户配置
        user_config = {}
        if self._user_config_path.exists():
            with open(self._user_config_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f) or {}

        # 深度合并
        self._data = self._deep_merge(deepcopy(self._defaults), user_config)

    def save(self):
        """保存当前配置到用户配置文件"""
        with open(self._user_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._data, f, allow_unicode=True, default_flow_style=False)

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值，支持点号分隔的路径。

        Args:
            key: 配置路径，如 "appearance.theme"
            default: 默认返回值
        """
        keys = key.split('.')
        value = self._data
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, key: str, value: Any):
        """
        设置配置值，支持点号分隔的路径。

        Args:
            key: 配置路径，如 "appearance.theme"
            value: 配置值
        """
        keys = key.split('.')
        data = self._data
        for k in keys[:-1]:
            if k not in data or not isinstance(data[k], dict):
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value

    def get_all(self) -> Dict[str, Any]:
        """获取全部配置（只读副本）"""
        return deepcopy(self._data)

    def reset(self):
        """重置为默认配置"""
        self._data = deepcopy(self._defaults)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """深度合并两个字典"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                ConfigManager._deep_merge(base[key], value)
            else:
                base[key] = value
        return base

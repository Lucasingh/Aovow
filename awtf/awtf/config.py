"""
配置管理 —— 分层配置：默认值 < 配置文件 < 环境变量。

- 配置文件支持 JSON（标准库，零依赖）与 YAML（安装了 pyyaml 时）；
- 环境变量覆盖：``AWTF__SECTION__KEY=value`` 映射为嵌套字典；
- 工具可用 :class:`ToolConfig` 读取自己的配置段，带类型转换与默认值；
- 支持保存（写 JSON/YAML），便于工具回写用户偏好。
"""

from __future__ import annotations

import json
import os
import pathlib
from typing import Any, Dict, Optional

from .errors import ToolConfigError

# 环境变量前缀与嵌套分隔符
ENV_PREFIX = "AWTF__"
ENV_SEP = "__"


def load_config(
    path: Optional[str | pathlib.Path] = None,
    *,
    defaults: Optional[Dict[str, Any]] = None,
    env_prefix: str = ENV_PREFIX,
) -> Dict[str, Any]:
    """加载并合并配置。

    Args:
        path: 配置文件路径（.json/.yaml/.yml）；None 时仅用默认值 + 环境变量。
        defaults: 默认配置字典（最低优先级）。
        env_prefix: 环境变量前缀。

    Returns:
        合并后的配置字典。

    Raises:
        ToolConfigError: 文件格式不支持 / 解析失败。
    """
    config: Dict[str, Any] = {}
    if defaults:
        config = deep_merge(config, defaults)

    if path:
        file_data = _read_file(path)
        config = deep_merge(config, file_data)

    env_data = _read_env(env_prefix)
    if env_data:
        config = deep_merge(config, env_data)

    return config


def _read_file(path: str | pathlib.Path) -> Dict[str, Any]:
    p = pathlib.Path(path).expanduser()
    if not p.exists():
        raise ToolConfigError(f"配置文件不存在: {p}", details={"path": str(p)})
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as e:
        raise ToolConfigError(f"无法读取配置文件: {e}", details={"path": str(p)}) from e

    suffix = p.suffix.lower()
    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ToolConfigError(f"JSON 配置解析失败: {e}", details={"path": str(p)}) from e
    elif suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as e:
            raise ToolConfigError(
                "读取 YAML 配置需要 pyyaml，请安装：pip install pyyaml",
                details={"path": str(p)},
            ) from e
        try:
            data = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:  # pragma: no cover - 依赖外部库
            raise ToolConfigError(f"YAML 配置解析失败: {e}", details={"path": str(p)}) from e
    else:
        raise ToolConfigError(
            f"不支持的配置格式: {suffix}（支持 .json/.yaml/.yml）",
            details={"path": str(p)},
        )

    if not isinstance(data, dict):
        raise ToolConfigError("配置文件顶层必须是字典/对象", details={"path": str(p)})
    return data


def _read_env(prefix: str) -> Dict[str, Any]:
    """读取 ``PREFIX__A__B=v`` 形式的环境变量，转为嵌套字典。

    值会尝试按 JSON 解析（true/123/[1,2]），失败则保留字符串。
    """
    result: Dict[str, Any] = {}
    for key, raw in os.environ.items():
        if not key.startswith(prefix):
            continue
        parts = key[len(prefix):].lower().split(ENV_SEP)
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = _parse_env_value(raw)
    return result


def _parse_env_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def save_config(path: str | pathlib.Path, data: Dict[str, Any]) -> None:
    """保存配置到文件（按扩展名选择 JSON/YAML）。"""
    p = pathlib.Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    suffix = p.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
            p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                         encoding="utf-8")
            return
        except ImportError:
            # 无 pyyaml 时降级为 JSON（改后缀提示）
            p = p.with_suffix(".json")
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并两个字典（override 优先），返回新字典。"""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class ToolConfig:
    """工具配置视图：按工具名读取自己的配置段。

    用法::

        cfg = ToolConfig(raw_config, section="my_tool")
        api_key = cfg.get("api_key", required=True, secret=True)
        timeout = cfg.get_int("timeout", default=30)
    """

    def __init__(self, raw: Optional[Dict[str, Any]], *, section: Optional[str] = None) -> None:
        self._raw = raw or {}
        self._section = section
        self._data = self._raw.get(section, {}) if section else self._raw
        if not isinstance(self._data, dict):
            raise ToolConfigError(
                f"配置段 '{section}' 必须是字典", details={"section": section})

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    def get(self, key: str, default: Any = None, *,
            required: bool = False, secret: bool = False) -> Any:
        if key not in self._data or self._data[key] is None:
            if required:
                raise ToolConfigError(
                    f"缺少必需配置项: {key}",
                    details={"section": self._section, "key": key, "secret": secret},
                )
            return default
        return self._data[key]

    def get_str(self, key: str, default: str = "", **kw: Any) -> str:
        return str(self.get(key, default, **kw))

    def get_int(self, key: str, default: int = 0, **kw: Any) -> int:
        value = self.get(key, default, **kw)
        try:
            return int(value)
        except (TypeError, ValueError) as e:
            raise ToolConfigError(f"配置项 {key} 不是整数: {value!r}") from e

    def get_float(self, key: str, default: float = 0.0, **kw: Any) -> float:
        value = self.get(key, default, **kw)
        try:
            return float(value)
        except (TypeError, ValueError) as e:
            raise ToolConfigError(f"配置项 {key} 不是数字: {value!r}") from e

    def get_bool(self, key: str, default: bool = False, **kw: Any) -> bool:
        value = self.get(key, default, **kw)
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on", "是"}

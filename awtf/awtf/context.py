"""
执行上下文 —— 每次工具调用获得的运行环境。

:class:`ToolContext` 携带：
- 工具专属 logger；
- 配置视图（:class:`~awtf.config.ToolConfig`）；
- 运行元数据（调用来源、dry-run、请求 ID 等）；
- 便捷方法 ``get_config`` / ``info``。

工具函数首个参数约定为 ``ctx``，由运行器自动注入，用户不传。
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any, Dict, Optional

from .config import ToolConfig
from .logging_utils import get_tool_logger


@dataclasses.dataclass
class ToolContext:
    """单次工具调用的上下文。

    Attributes:
        tool_name: 工具名。
        logger: 工具专属 logger。
        config: 全局配置字典（原始）。
        metadata: 运行元数据，如 ``source="cli"``、``request_id``、``dry_run``。
    """

    tool_name: str
    logger: logging.Logger
    config: Dict[str, Any] = dataclasses.field(default_factory=dict)
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @classmethod
    def create(
        cls,
        tool_name: str,
        *,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "ToolContext":
        """构造上下文（自动创建工具 logger 与配置视图）。"""
        return cls(
            tool_name=tool_name,
            logger=get_tool_logger(tool_name),
            config=config or {},
            metadata=metadata or {},
        )

    def section_config(self, section: Optional[str] = None) -> ToolConfig:
        """获取某个配置段的视图；默认取与工具同名的段。"""
        return ToolConfig(self.config, section=section or self.tool_name)

    def get_config(self, key: str, default: Any = None, *, section: Optional[str] = None) -> Any:
        """从工具配置段读取一个配置项。"""
        return self.section_config(section).get(key, default)

    # ---------- 日志便捷方法 ----------

    def debug(self, msg: str, *args: Any) -> None:
        self.logger.debug(msg, *args)

    def info(self, msg: str, *args: Any) -> None:
        self.logger.info(msg, *args)

    def warning(self, msg: str, *args: Any) -> None:
        self.logger.warning(msg, *args)

    def error(self, msg: str, *args: Any) -> None:
        self.logger.error(msg, *args)

    @property
    def dry_run(self) -> bool:
        """是否为演练模式（工具应只输出将做什么，不产生副作用）。"""
        return bool(self.metadata.get("dry_run"))

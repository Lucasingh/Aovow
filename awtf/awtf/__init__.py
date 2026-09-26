"""
awtf —— 用 Python 代码快速构建自定义工具的库。

核心概念：
- **工具（Tool）**：一个带元数据与参数声明的可调用单元，三种形态：
  函数工具（@tool 装饰）、类工具（ToolBase 子类）、异步工具（async def）。
- **注册表（ToolRegistry）**：注册、发现、执行工具的中心，
  ``registry.run(name, params)`` 是唯一执行入口，返回标准化 ``ToolResult``。
- **参数系统（Parameter/ParameterSet）**：类型转换与约束校验的单一真源。
- **上下文（ToolContext）**：每次调用注入 logger / config / metadata。

快速上手::

    from awtf import tool, ToolRegistry

    @tool(name="greet", tags=["demo"])
    def greet(ctx, name: str, count: int = 1) -> str:
        \"\"\"向用户打招呼。

        Args:
            name: 用户名
            count: 重复次数
        \"\"\"
        ctx.info("greet %s x%s", name, count)
        return ("你好，" + name + "！") * count

    registry = ToolRegistry()
    registry.register(greet)
    result = registry.run("greet", {"name": "世界", "count": 2})
    print(result.ok, result.data)
"""

from __future__ import annotations

__version__ = "1.1.0"

# 参数系统
from .parameters import Parameter, ParameterSet, infer_parameters

# 上下文 / 结果
from .context import ToolContext
from .result import ToolResult

# 错误体系
from .errors import (
    ToolError,
    ToolNotFoundError,
    ToolValidationError,
    ToolExecutionError,
    ToolConfigError,
    ToolRegistrationError,
    ToolDiscoveryError,
)

# 工具抽象
from .base import ToolBase, FunctionTool, ToolMeta, tool

# 注册表
from .registry import ToolRegistry, get_default_registry

# 配置
from .config import ToolConfig, load_config, save_config, deep_merge

# 日志
from .logging_utils import setup_logging, get_tool_logger, LogCapture

# 脚手架
from .templates import scaffold, render_tool_file, render_readme

# 系统信息获取（sysinfo）
from . import sysinfo

# UI 设计组件库（ui）
from . import ui

__all__ = [
    # 版本
    "__version__",
    # 参数
    "Parameter",
    "ParameterSet",
    "infer_parameters",
    # 上下文与结果
    "ToolContext",
    "ToolResult",
    # 错误
    "ToolError",
    "ToolNotFoundError",
    "ToolValidationError",
    "ToolExecutionError",
    "ToolConfigError",
    "ToolRegistrationError",
    "ToolDiscoveryError",
    # 工具
    "ToolBase",
    "FunctionTool",
    "ToolMeta",
    "tool",
    # 注册表
    "ToolRegistry",
    "get_default_registry",
    # 配置
    "ToolConfig",
    "load_config",
    "save_config",
    "deep_merge",
    # 日志
    "setup_logging",
    "get_tool_logger",
    "LogCapture",
    # 脚手架
    "scaffold",
    "render_tool_file",
    "render_readme",
    # 扩展模块
    "sysinfo",
    "ui",
]

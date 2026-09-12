"""
pytest 公共夹具 —— 统一的注册表工厂与示例工具。

按经验约定：所有集成测试通过 ``create_registry()`` 工厂获得注册表，
不在各测试点临时构造，保证注册行为一致、结果可比。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

# 确保未安装时也能导入
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from awtf import (  # noqa: E402
    Parameter,
    ParameterSet,
    ToolBase,
    ToolContext,
    ToolRegistry,
    tool,
)


# ---------- 示例工具（模块级，便于发现测试使用） ----------

@tool(name="add", tags=["math"], version="1.2.0")
def add_tool(ctx: ToolContext, a: int, b: int = 1) -> int:
    """两数相加。

    Args:
        a: 加数 a
        b: 加数 b
    """
    ctx.info("add: %s + %s", a, b)
    return a + b


@tool(name="greet", tags=["text"])
def greet_tool(ctx: ToolContext, name: str, excited: bool = False) -> str:
    """打招呼。

    Args:
        name: 用户名
        excited: 是否感叹
    """
    punctuation = "！" if excited else "。"
    return f"你好，{name}{punctuation}"


@tool(name="boom", tags=["error"])
def boom_tool(ctx: ToolContext) -> dict:
    """总是抛出运行时异常（测试错误包装）。"""
    raise RuntimeError("故意炸了")


@tool(name="async_echo", tags=["async"])
async def async_echo_tool(ctx: ToolContext, message: str) -> dict:
    """异步工具：回显消息。

    Args:
        message: 消息内容
    """
    import asyncio
    await asyncio.sleep(0.01)
    return {"echo": message, "async": True}


class MultiplyTool(ToolBase):
    """类工具示例：乘法。"""

    name = "multiply"
    description = "两数相乘"
    tags = ("math",)
    parameters = ParameterSet([
        Parameter("a", int, description="乘数 a"),
        Parameter("b", int, default=2, description="乘数 b"),
    ])

    def run(self, ctx: ToolContext, a: int, b: int = 2) -> dict:
        return {"product": a * b, "a": a, "b": b}


# ---------- 工厂与夹具 ----------

def create_registry() -> ToolRegistry:
    """统一工厂：创建注册表并注册全部示例工具。"""
    reg = ToolRegistry(name="test")
    reg.register(add_tool)
    reg.register(greet_tool)
    reg.register(boom_tool)
    reg.register(async_echo_tool)
    reg.register(MultiplyTool)
    return reg


@pytest.fixture
def registry() -> ToolRegistry:
    return create_registry()


@pytest.fixture
def empty_registry() -> ToolRegistry:
    return ToolRegistry(name="empty")

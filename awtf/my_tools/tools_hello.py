"""工具：hello

用途：
    在这里描述工具用途

参数：
    text   (str)  输入文本
    repeat (int)  重复次数（1-10）

返回：
    dict，包含 input / output / repeat 字段

示例：
    # Python 调用
    from awtf import ToolRegistry
    registry = ToolRegistry()
    registry.discover_path(__file__)
    result = registry.run("hello", {"text": "你好", "repeat": 3})

    # 命令行调用
    python -m awtf run hello --text "你好" --repeat 3 --discover .

错误：
    VALIDATION_ERROR —— 参数缺失或类型不符
    EXECUTION_ERROR  —— 运行时异常（自动包装，含 traceback）
"""

from __future__ import annotations

from awtf import Parameter, ToolContext, tool


@tool(
    name="hello",
    version="0.1.0",
    tags=["custom"],
    author="",
    parameters=[
        Parameter("text", str, description="输入文本", min_length=1),
        Parameter("repeat", int, default=1, min=1, max=10, description="重复次数"),
    ],
)
def hello(ctx: ToolContext, text: str, repeat: int = 1) -> dict:
    """在这里描述工具用途"""
    ctx.info("执行 hello: text=%s repeat=%s", text, repeat)

    if ctx.dry_run:
        return {"would_do": f"把 {text!r} 重复 {repeat} 次"}

    return {
        "tool": "hello",
        "input": text,
        "output": (text + " ") * repeat,
        "repeat": repeat,
    }

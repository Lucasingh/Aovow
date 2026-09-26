"""自动生成的工具：问候工具（由 Aovow 工具设计器创建）"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_AWTF_ROOT = _Path(__file__).resolve().parent.parent.parent / "awtf"
if _AWTF_ROOT.is_dir() and str(_AWTF_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_AWTF_ROOT))

from awtf import Parameter, ToolContext, tool

from workstation.tools.designer_base import DesignerToolBase


@tool(
    name="greet",
    description='对名字打招呼',
    tags=["designer"],
    category='测试',
    parameters=[
        Parameter("name", str, default='世界', description='名字'),
        Parameter("repeat", int, default=1, description='次数'),
    ],
)
def greet(ctx: ToolContext, name: str = '世界', repeat: int = 1):
    """对名字打招呼"""
    for i in range(repeat):
        ctx.info(f"第 {i + 1} 次问候 {name}")
    return {"greeting": f"你好，{name}！", "repeat": repeat}


class GreetTool(DesignerToolBase):
    tool_id = "greet"
    name = '问候工具'
    icon = '👋'
    category = '测试'
    description = '对名字打招呼'
    _func = greet

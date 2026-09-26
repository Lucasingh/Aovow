"""自动生成的工具：test3（由 Aovow 工具设计器创建）"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_AWTF_ROOT = _Path(__file__).resolve().parent.parent.parent / "awtf"
if _AWTF_ROOT.is_dir() and str(_AWTF_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_AWTF_ROOT))

from awtf import Parameter, ToolContext, tool

from workstation.tools.designer_base import DesignerToolBase


@tool(
    name="test3",
    description='test03',
    tags=["designer"],
    category='通用',
    parameters=[
        Parameter("repeat", int, default=2, description='none'),
        Parameter("name", str, default='world', description='none'),
    ],
)
def test3(ctx: ToolContext, repeat: int = 2, name: str = 'world'):
    """test03"""
    for i in range(repeat):
        ctx.info(f"第 {i + 1} 次问候")
    greeting = f"你好，{name}！这是第 {repeat} 次见面。"
    return {"greeting": greeting, "repeat": repeat}


class Test3Tool(DesignerToolBase):
    tool_id = "test3"
    name = 'test3'
    icon = '🧩'
    category = '通用'
    description = 'test03'
    _func = test3

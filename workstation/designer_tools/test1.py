"""自动生成的工具：test1（由 Aovow 工具设计器创建）"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_AWTF_ROOT = _Path(__file__).resolve().parent.parent.parent / "awtf"
if _AWTF_ROOT.is_dir() and str(_AWTF_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_AWTF_ROOT))

from awtf import Parameter, ToolContext, tool

from workstation.tools.designer_base import DesignerToolBase


@tool(
    name="test1",
    description='test1 工具',
    tags=["designer"],
    category='通用',
    parameters=[
        # 无参数
    ],
)
def test1(ctx: ToolContext):
    """test1 工具"""
    # 在这里写你的工具逻辑
    ctx.info("工具运行")
    return {"result": "你好，世界！"}


class Test1Tool(DesignerToolBase):
    tool_id = "test1"
    name = 'test1'
    icon = '🧩'
    category = '通用'
    description = 'test1 工具'
    _func = test1

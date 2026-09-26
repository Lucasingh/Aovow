"""自动生成的工具：testhello（由 Aovow 工具设计器创建）"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_AWTF_ROOT = _Path(__file__).resolve().parent.parent.parent / "awtf"
if _AWTF_ROOT.is_dir() and str(_AWTF_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_AWTF_ROOT))

from awtf import Parameter, ToolContext, tool

from workstation.tools.designer_base import DesignerToolBase


@tool(
    name="testhello",
    description='testhello',
    tags=["designer"],
    category='hello',
    parameters=[
        Parameter("name", str, default='Aovow', description=''),
    ],
)
def testhello(ctx: ToolContext, name: str = 'Aovow'):
    """testhello"""
    return {"message": f"Hello, {name}!"}


class TesthelloTool(DesignerToolBase):
    tool_id = "testhello"
    name = 'testhello'
    icon = '🧩'
    category = 'hello'
    description = 'testhello'
    _func = testhello

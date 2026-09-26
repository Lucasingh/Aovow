"""
HelloWorld 工具 —— 用 AWTF 写一个最简单的工作站工具

展示点：
1. 同时提供 AWTF 函数工具（@tool 装饰器）和工作站 GUI 工具（BaseTool 子类）
2. AWTF 工具可命令行运行：python -m awtf run hello_world --discover workstation/tools/hello_world_tool.py
3. GUI 工具在工作站侧边栏显示，界面居中展示 "HELLOWORLD"

运行（开发环境）:
    C:\\Users\\lshen\\anaconda3\\python.exe -m awtf run hello_world
"""

from __future__ import annotations

# ========== AWTF 函数工具 ==========
# 让这个文件同时也是 AWTF 的工具模块，可以被 python -m awtf run 发现
import sys as _sys
from pathlib import Path as _Path

# 让 awtf 可被导入（开发环境 & 打包后都能找到）
_awtf_root = _Path(__file__).resolve().parent.parent.parent / "awtf"
if str(_awtf_root) not in _sys.path:
    _sys.path.insert(0, str(_awtf_root))

from awtf import Parameter, ToolContext, tool  # type: ignore


@tool(
    name="hello_world",
    description="HelloWorld —— 最简单的 AWTF 示例工具",
    tags=["demo"],
    parameters=[
        Parameter("name", str, default="World", description="向谁打招呼"),
        Parameter("repeat", int, default=1, min=1, max=10,
                  description="重复次数"),
    ],
)
def hello_world(ctx: ToolContext, name: str = "World", repeat: int = 1) -> dict:
    """Hello World！

    Args:
        name: 打招呼的对象
        repeat: 重复说几次
    """
    ctx.info("hello_world: name=%s, repeat=%d", name, repeat)
    message = "HELLO, " + name.upper() + "! "
    messages = [message.rstrip() for _ in range(repeat)]
    return {
        "greeting": messages[0],
        "messages": messages,
        "count": repeat,
    }


# ========== 工作站 GUI 工具 ==========
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt

from workstation.tools.base_tool import BaseTool


class HelloWorldTool(BaseTool):
    """HelloWorld GUI 工具"""

    tool_id = "hello_world"
    name = "HelloWorld"
    icon = "👋"
    category = "测试"
    description = "AWTF + 工作站集成示例工具"

    def __init__(self):
        self._widget: QWidget | None = None

    @property
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._build_ui()
        return self._widget

    def _build_ui(self) -> QWidget:
        """居中展示 'HELLOWORLD' 的极简界面"""
        from workstation.ui.responsive import get_responsive_engine
        r = get_responsive_engine()

        panel = QWidget()
        panel.setStyleSheet("QWidget { background: transparent; }")

        v = QVBoxLayout(panel)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addStretch()

        hello = QLabel("HELLOWORLD")
        hello.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hello.setStyleSheet(
            f"""
            font-size: {r.font_size(64)}px;
            font-weight: 900;
            color: #a78bfa;
            letter-spacing: 8px;
            background: transparent;
            border: none;
            padding: 20px 0;
            """
        )
        v.addWidget(hello)

        sub = QLabel("👋 欢迎来到 Aovow Workstation —— 你用 AWTF 写的第一个工具！")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"font-size: {r.font_size(14)}px; color: #7a7a9e; "
            f"background: transparent; border: none; margin-top: 8px;")
        sub.setWordWrap(True)
        v.addWidget(sub)

        v.addStretch()
        return panel

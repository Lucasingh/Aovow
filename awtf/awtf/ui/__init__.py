"""
UI 设计组件库（awtf.ui）。

组件 = 纯数据描述 + 验证逻辑（core/widgets/containers/dialogs/feedback），
渲染由后端完成（默认 tkinter，零第三方依赖、跨平台）。

快速上手::

    from awtf.ui import (
        App, LabelSpec, ButtonSpec, InputSpec, InputField,
        CardSpec, RowSpec, TableSpec, show_message,
    )

    app = App(
        title="示例",
        children=[
            LabelSpec("欢迎使用 AWTF UI", bold=True, size=16),
            InputSpec(InputField("username", label="用户名", required=True)),
            InputSpec(InputField("age", label="年龄", kind="number", min=0, max=150)),
            ButtonSpec("确定", on_click="on_ok"),
        ],
    )
    # render_app 进入事件循环；对话框用 show_confirm/show_message/show_input
"""

from __future__ import annotations

# 核心
from .core import (
    DEFAULT_THEME,
    INPUT_KINDS,
    InputField,
    Callbacks,
    make_theme,
    validate_fields,
)

# 基础控件
from .widgets import (
    ButtonSpec,
    DividerSpec,
    IconSpec,
    InputSpec,
    LabelSpec,
    RowSpec,
    TextAreaSpec,
)

# 容器
from .containers import CardSpec, ListSpec, TableSpec

# 对话框与反馈
from .dialogs import ConfirmDialog, InputDialog, MessageDialog
from .feedback import ProgressBar, Spinner, Toast

# tkinter 渲染后端
from .tk_backend import App, AppWindow, render_app, show_confirm, show_input, show_message, show_toast

__all__ = [
    # 主题/输入
    "DEFAULT_THEME",
    "INPUT_KINDS",
    "InputField",
    "Callbacks",
    "make_theme",
    "validate_fields",
    # 基础控件
    "ButtonSpec",
    "DividerSpec",
    "IconSpec",
    "InputSpec",
    "LabelSpec",
    "RowSpec",
    "TextAreaSpec",
    # 容器
    "CardSpec",
    "ListSpec",
    "TableSpec",
    # 对话框与反馈
    "ConfirmDialog",
    "InputDialog",
    "MessageDialog",
    "ProgressBar",
    "Spinner",
    "Toast",
    # 后端
    "App",
    "AppWindow",
    "render_app",
    "show_confirm",
    "show_input",
    "show_message",
    "show_toast",
]

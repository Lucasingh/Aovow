"""
基础控件：按钮、输入框、标签、图标。

每个组件都是纯数据 dataclass（可序列化、可测），由渲染后端绘制。
按钮支持多种样式与禁用状态；输入框复用 core.InputField 的验证逻辑。
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, Sequence, Union

from .core import InputField

# 按钮样式
BUTTON_STYLES = ("primary", "secondary", "success", "danger", "ghost")
BUTTON_SIZES = ("small", "medium", "large")


@dataclasses.dataclass
class ButtonSpec:
    """按钮。

    Attributes:
        text: 显示文字。
        style: primary / secondary / success / danger / ghost。
        disabled: 是否禁用。
        size: small / medium / large。
        icon: 前置 emoji 图标。
        on_click: 回调名（Callbacks 中注册）。
        tooltip: 悬停提示。
    """

    text: str
    style: str = "primary"
    disabled: bool = False
    size: str = "medium"
    icon: str = ""
    on_click: Optional[str] = None
    tooltip: str = ""

    def __post_init__(self) -> None:
        if self.style not in BUTTON_STYLES:
            raise ValueError(f"按钮样式 {self.style!r} 不在 {BUTTON_STYLES}")
        if self.size not in BUTTON_SIZES:
            raise ValueError(f"按钮尺寸 {self.size!r} 不在 {BUTTON_SIZES}")


@dataclasses.dataclass
class LabelSpec:
    """文本标签。"""

    text: str
    color: Optional[str] = None
    size: Optional[int] = None
    bold: bool = False
    align: str = "left"  # left / center / right
    wrap: bool = False


@dataclasses.dataclass
class IconSpec:
    """图标（跨平台用 Unicode emoji 文本渲染）。"""

    icon: str
    size: int = 20
    color: Optional[str] = None


@dataclasses.dataclass
class InputSpec:
    """输入框：包装 InputField + 事件。"""

    field: InputField
    on_change: Optional[str] = None
    on_submit: Optional[str] = None

    @property
    def name(self) -> str:
        return self.field.name

    def to_field_dict(self) -> Dict[str, Any]:
        return self.field.to_dict()


@dataclasses.dataclass
class TextAreaSpec:
    """多行文本区（聊天记录/日志展示/备注编辑）。

    Attributes:
        name: 唯一名（AppWindow.text_areas 索引，用于追加文本）。
        text: 初始内容。
        readonly: 只读（聊天记录区用 True）。
        height: 可见行数。
        on_change: 编辑回调名（readonly=False 时生效）。
    """

    name: str
    text: str = ""
    readonly: bool = True
    height: int = 16
    on_change: Optional[str] = None


# 组件联合类型：任意控件/容器
Component = Union[ButtonSpec, LabelSpec, IconSpec, InputSpec, TextAreaSpec,
                  "CardSpec", "ListSpec", "TableSpec", "RowSpec", "DividerSpec"]


@dataclasses.dataclass
class RowSpec:
    """横向排列容器。"""

    children: List[Component]
    spacing: int = 8


@dataclasses.dataclass
class DividerSpec:
    """分隔线。"""

    thickness: int = 1

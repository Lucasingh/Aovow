"""
反馈组件：加载指示器（Spinner）、进度条（ProgressBar）、消息提示（Toast）。

- Spinner：无限旋转加载动画（indeterminate）。
- ProgressBar：确定进度（0~100）或不确定进度（marquee）。
- Toast：右下角短暂自动消失的消息气泡。

数据层只描述"要展示什么"，动画由渲染后端驱动。
"""

from __future__ import annotations

import dataclasses
from typing import Optional


@dataclasses.dataclass
class Spinner:
    """加载指示器。"""

    size: int = 24
    color: str = "#4f6ef7"
    text: str = "加载中..."


@dataclasses.dataclass
class ProgressBar:
    """进度条。

    Attributes:
        value: 当前进度（0~100）；None 表示不确定（动画模式）。
        width: 宽度（像素）。
        height: 高度（像素）。
        color: 前景色。
        show_text: 是否显示百分比文字。
    """

    value: Optional[float] = 0
    width: int = 280
    height: int = 10
    color: str = "#4f6ef7"
    show_text: bool = True

    def __post_init__(self) -> None:
        if self.value is not None:
            self.value = max(0.0, min(100.0, float(self.value)))


@dataclasses.dataclass
class Toast:
    """消息提示（自动消失）。"""

    message: str
    level: str = "info"  # info / success / warning / error
    duration_ms: int = 2500

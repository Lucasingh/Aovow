"""
对话框组件：确认框、提示框、输入对话框。

- ConfirmDialog：确认/取消二选一。
- MessageDialog：信息/警告/错误提示。
- InputDialog：支持多个输入字段，**复用 core.InputField 的验证/格式化逻辑**，
  提交时批量验证，错误逐字段显示。

结果约定（由后端 show_* 返回）：
- 确认/提示框：用户确认返回 True，取消/关闭返回 False。
- 输入对话框：确认返回 {字段名: 值}，取消返回 None。
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, Sequence

from .core import InputField, validate_fields

# 提示级别
MESSAGE_LEVELS = ("info", "success", "warning", "error")


@dataclasses.dataclass
class ConfirmDialog:
    """确认对话框。"""

    title: str
    message: str
    confirm_text: str = "确定"
    cancel_text: str = "取消"
    danger: bool = False


@dataclasses.dataclass
class MessageDialog:
    """提示对话框。"""

    title: str
    message: str
    level: str = "info"
    button_text: str = "确定"

    def __post_init__(self) -> None:
        if self.level not in MESSAGE_LEVELS:
            raise ValueError(f"提示级别 {self.level!r} 不在 {MESSAGE_LEVELS}")


@dataclasses.dataclass
class InputDialog:
    """输入对话框（可含多个字段）。"""

    title: str
    message: str = ""
    fields: List[InputField] = dataclasses.field(default_factory=list)
    confirm_text: str = "确定"
    cancel_text: str = "取消"

    def validate(self, raw: Dict[str, Any]) -> tuple[bool, Dict[str, Any], Dict[str, str]]:
        """批量验证输入。"""
        return validate_fields(self.fields, raw)

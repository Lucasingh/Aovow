"""
UI 核心：主题（颜色/字体/尺寸 token）、输入字段定义与验证、回调注册。

设计原则：
- 组件都是**纯数据**（dataclass），不依赖任何渲染后端 → 可序列化、可单元测试。
- 输入验证/格式化逻辑独立于后端，`InputField.validate` 是唯一真源。
- 渲染由独立后端完成（默认 tkinter），本模块只定义"界面是什么"。
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any, Callable, Dict, List, Optional, Sequence

# ============================================================
# 主题
# ============================================================

DEFAULT_THEME = {
    # 颜色
    "primary": "#4f6ef7",
    "primary_hover": "#3d5ae0",
    "success": "#2ecc71",
    "danger": "#e74c3c",
    "warning": "#f39c12",
    "secondary": "#6c757d",
    "bg": "#f5f6fa",
    "bg_card": "#ffffff",
    "text": "#2d3436",
    "text_secondary": "#7a7a9e",
    "border": "#dcdde1",
    "disabled_bg": "#e9ecef",
    "disabled_text": "#a0a8b0",
    "focus": "#9db2ff",
    "error_bg": "#fdecea",
    "error_text": "#c0392b",
    # 字体
    "font_family": ("Segoe UI", "Microsoft YaHei", "PingFang SC", "sans-serif"),
    "font_size": 12,
    "font_size_small": 10,
    "font_size_title": 18,
    # 尺寸
    "radius": 6,
    "padding": 10,
    "spacing": 8,
    "control_height": 30,
}


def make_theme(**overrides: Any) -> Dict[str, Any]:
    """基于默认主题生成自定义主题（浅拷贝）。"""
    theme = dict(DEFAULT_THEME)
    theme.update(overrides)
    return theme


# ============================================================
# 输入字段定义与验证
# ============================================================

# 输入类型：text 文本 / number 数字（整数） / float 小数 / password 密码 /
#           email 邮箱 / phone 手机号
INPUT_KINDS = ("text", "number", "float", "password", "email", "phone")

# 常见验证模式
_EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


@dataclasses.dataclass
class InputField:
    """输入字段：声明 + 验证 + 格式化，渲染后端不参与逻辑。

    Attributes:
        name: 字段名（结果字典的键）。
        label: 界面显示的标签。
        kind: text / number / float / password / email / phone。
        required: 是否必填。
        default: 默认值。
        placeholder: 占位提示。
        min / max: number/float 的取值范围。
        min_length / max_length: 文本长度限制。
        pattern: 文本正则（re.search）。
        choices: 枚举值（可选项）。
        hint: 字段下方的帮助文字。
        secret: 回显/日志是否脱敏。
    """

    name: str
    label: str = ""
    kind: str = "text"
    required: bool = False
    default: Any = None
    placeholder: str = ""
    min: Optional[float] = None
    max: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    choices: Optional[Sequence[str]] = None
    hint: str = ""
    secret: bool = False

    def __post_init__(self) -> None:
        if self.kind not in INPUT_KINDS:
            raise ValueError(f"不支持的输入类型 {self.kind!r}，可选 {INPUT_KINDS}")
        if not self.label:
            self.label = self.name
        self._pattern_re = re.compile(self.pattern) if self.pattern else None

    # ---------- 验证 ----------

    def validate(self, raw: Any) -> tuple[bool, Any, str]:
        """验证并转换原始输入。

        Returns:
            (ok, value, error)。ok 为 False 时 value 为 None，error 为原因；
            ok 为 True 时 value 为转换后的值，error 为空串。
        """
        # 空值处理
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            if self.required:
                return False, None, f"{self.label}为必填项"
            return True, self.default, ""

        value = raw

        # 类型转换 + 值域
        if self.kind in ("number", "float"):
            try:
                value = int(str(raw).strip()) if self.kind == "number" else float(str(raw).strip())
            except (TypeError, ValueError):
                kind_name = "整数" if self.kind == "number" else "数字"
                return False, None, f"{self.label}必须是{kind_name}"
            if self.min is not None and value < self.min:
                return False, None, f"{self.label}不能小于 {self.min}"
            if self.max is not None and value > self.max:
                return False, None, f"{self.label}不能大于 {self.max}"

        if self.kind in ("text", "password", "email", "phone"):
            value = str(value)
            length = len(value)
            if self.min_length is not None and length < self.min_length:
                return False, None, f"{self.label}长度不能少于 {self.min_length}"
            if self.max_length is not None and length > self.max_length:
                return False, None, f"{self.label}长度不能超过 {self.max_length}"

        if self.kind == "email" and not _EMAIL_RE.match(str(value)):
            return False, None, f"{self.label}不是有效的邮箱地址"
        if self.kind == "phone" and not _PHONE_RE.match(str(value)):
            return False, None, f"{self.label}不是有效的手机号"

        if self._pattern_re is not None and not self._pattern_re.search(str(value)):
            return False, None, f"{self.label}格式不正确（{self.pattern}）"

        if self.choices is not None and str(value) not in self.choices:
            return False, None, f"{self.label}必须是 {list(self.choices)} 之一"

        return True, value, ""

    def format_display(self, value: Any) -> str:
        """格式化显示值（用于输入框回显 / 结果展示）。"""
        if value is None:
            return ""
        if self.secret:
            return "***"
        return str(value)

    # ---------- 元信息 ----------

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def validate_fields(fields: Sequence[InputField], raw: Dict[str, Any]) -> tuple[bool, Dict[str, Any], Dict[str, str]]:
    """批量验证一组字段。

    Args:
        fields: 字段定义列表。
        raw: 原始输入 {name: value}。

    Returns:
        (ok, cleaned, errors)。cleaned 含默认值；errors 为 {name: 原因}。
    """
    cleaned: Dict[str, Any] = {}
    errors: Dict[str, str] = {}
    unknown = set(raw.keys()) - {f.name for f in fields}
    if unknown:
        errors["__unknown__"] = f"未知字段: {', '.join(sorted(unknown))}"

    for field in fields:
        ok, value, error = field.validate(raw.get(field.name))
        if ok:
            cleaned[field.name] = value
        else:
            errors[field.name] = error
    return (not errors), cleaned, errors


# ============================================================
# 回调注册
# ============================================================

EventCallback = Callable[[Any], None]


class Callbacks:
    """事件回调注册表：后端把界面事件映射到这里的处理器。

    用法::

        cbs = Callbacks({"on_login": handler})
        cbs.get("on_login")  # -> handler 或 None
    """

    def __init__(self, handlers: Optional[Dict[str, EventCallback]] = None) -> None:
        self._handlers: Dict[str, EventCallback] = dict(handlers or {})

    def register(self, name: str, handler: EventCallback) -> None:
        self._handlers[name] = handler

    def get(self, name: str) -> Optional[EventCallback]:
        return self._handlers.get(name)

    def has(self, name: str) -> bool:
        return name in self._handlers

    def call(self, name: str, payload: Any = None) -> None:
        handler = self._handlers.get(name)
        if handler is not None:
            handler(payload)

    def __contains__(self, name: str) -> bool:
        return name in self._handlers

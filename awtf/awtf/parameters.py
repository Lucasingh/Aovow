"""
参数声明与校验 —— 工具输入的单一真源（single source of truth）。

- :class:`Parameter` 描述一个输入参数：类型、必填、默认值、取值范围、
  枚举 choices、正则、是否敏感（日志脱敏）等；
- :class:`ParameterSet` 聚合并执行校验/类型转换，**一次收集所有字段错误**
  （抛 :class:`~awtf.errors.ToolValidationError`）；
- :func:`infer_parameters` 从函数签名与类型注解自动推断参数列表，
  让 ``@tool`` 装饰器零配置可用。

支持类型：str / int / float / bool / list / dict / Path，以及通过
``choices`` 表达的枚举。CLI 字符串与 JSON 输入均可被正确转换。
"""

from __future__ import annotations

import dataclasses
import inspect
import pathlib
import re
import typing
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from .errors import ToolValidationError

# 支持的基础类型（注解形式 -> 内部类型名）
_PRIMITIVE_TYPES: Dict[Any, str] = {
    str: "str",
    int: "int",
    float: "float",
    bool: "bool",
    list: "list",
    dict: "dict",
    pathlib.Path: "path",
}

# bool 解析：CLI/JSON 传入的字符串需要明确规则
_BOOL_TRUE = {"1", "true", "yes", "y", "on", "是"}
_BOOL_FALSE = {"0", "false", "no", "n", "off", "否"}

# 未显式提供默认值的哨兵
_UNSET = object()


@dataclasses.dataclass
class Parameter:
    """单个工具参数的声明。

    Attributes:
        name: 参数名。
        type: 类型，接受 ``str/int/float/bool/list/dict/pathlib.Path`` 或
            字符串形式 ``"str"`` 等；默认 ``str``。
        required: 是否必填。
        default: 默认值（required 为 False 时生效）。
        description: 人类可读说明，用于自动文档与 CLI help。
        choices: 枚举值列表，传入值必须在其中。
        min / max: 数值范围（含边界）。
        min_length / max_length: 字符串/列表长度限制。
        pattern: 字符串正则（re.search 匹配）。
        secret: 为 True 时在日志/错误回显中脱敏。
    """

    name: str
    type: Any = str
    default: Any = _UNSET
    required: Optional[bool] = None
    description: str = ""
    choices: Optional[Sequence[Any]] = None
    min: Optional[float] = None
    max: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    secret: bool = False

    def __post_init__(self) -> None:
        # required 未显式指定时：有默认值 → 可选；无默认值 → 必填
        if self.required is None:
            self.required = self.default is _UNSET
        if self.default is _UNSET:
            self.default = None
        self.type_name = self._resolve_type_name(self.type)
        self._pattern_re = re.compile(self.pattern) if self.pattern else None

    @staticmethod
    def _resolve_type_name(t: Any) -> str:
        if isinstance(t, str):
            return t
        if t in _PRIMITIVE_TYPES:
            return _PRIMITIVE_TYPES[t]
        # 泛型：List[X] / Dict[K,V] / Optional[X] / X | None
        origin = typing.get_origin(t)
        if origin in (list, dict):
            return _PRIMITIVE_TYPES.get(origin, "str")
        if origin is Union:
            args = [a for a in typing.get_args(t) if a is not type(None)]
            if len(args) == 1:
                return Parameter._resolve_type_name(args[0])
        raise ValueError(f"不支持的参数类型: {t!r}（支持 str/int/float/bool/list/dict/Path）")

    # ---------- 元信息 ----------

    @property
    def type_display(self) -> str:
        """文档/CLI 展示用类型名。"""
        return self.type_name

    def mask(self, value: Any) -> Any:
        """敏感值脱敏（日志用）。"""
        if not self.secret or value is None:
            return value
        return "***"

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 安全字典（自动文档 / schema 导出）。"""
        return {
            "name": self.name,
            "type": self.type_name,
            "required": self.required,
            "default": None if self.required else self.default,
            "description": self.description,
            "choices": list(self.choices) if self.choices else None,
            "min": self.min,
            "max": self.max,
            "min_length": self.min_length,
            "max_length": self.max_length,
            "pattern": self.pattern,
            "secret": self.secret,
        }

    # ---------- 转换与校验 ----------

    def coerce(self, value: Any) -> Any:
        """把外部输入（CLI 字符串 / JSON 标量）转换为目标类型。

        Raises:
            ValueError: 无法转换时，消息为人类可读原因。
        """
        # None 处理
        if value is None:
            if self.required:
                raise ValueError("必填参数不能为 null")
            return self.default

        tn = self.type_name

        if tn == "str":
            return str(value)
        if tn == "int":
            if isinstance(value, bool):
                raise ValueError("需要整数，收到布尔值")
            try:
                return int(value) if not isinstance(value, str) else int(value.strip())
            except (TypeError, ValueError):
                raise ValueError(f"无法转换为整数: {value!r}")
        if tn == "float":
            if isinstance(value, bool):
                raise ValueError("需要数字，收到布尔值")
            try:
                return float(value)
            except (TypeError, ValueError):
                raise ValueError(f"无法转换为数字: {value!r}")
        if tn == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return bool(value)
            s = str(value).strip().lower()
            if s in _BOOL_TRUE:
                return True
            if s in _BOOL_FALSE:
                return False
            raise ValueError(f"无法解析为布尔值: {value!r}（可用 true/false）")
        if tn == "list":
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                # CLI 逗号分隔
                return [item.strip() for item in value.split(",") if item.strip()]
            raise ValueError(f"需要列表，收到 {type(value).__name__}")
        if tn == "dict":
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                import json
                try:
                    return json.loads(value)
                except json.JSONDecodeError as e:
                    raise ValueError(f"无法解析为 JSON 对象: {e}")
            raise ValueError(f"需要字典，收到 {type(value).__name__}")
        if tn == "path":
            return pathlib.Path(str(value)).expanduser()

        raise ValueError(f"未知类型 {tn}")  # pragma: no cover

    def validate(self, value: Any) -> None:
        """对已转换的值做约束校验。

        Raises:
            ValueError: 违反约束时。
        """
        if value is None:
            return

        if self.choices is not None and value not in self.choices:
            raise ValueError(f"取值必须是 {list(self.choices)} 之一，收到 {value!r}")

        tn = self.type_name
        if tn in ("int", "float"):
            if self.min is not None and value < self.min:
                raise ValueError(f"数值 {value} 小于最小值 {self.min}")
            if self.max is not None and value > self.max:
                raise ValueError(f"数值 {value} 大于最大值 {self.max}")

        if tn in ("str", "list", "path"):
            length = len(str(value) if tn == "path" else value)
            if self.min_length is not None and length < self.min_length:
                raise ValueError(f"长度 {length} 小于最小长度 {self.min_length}")
            if self.max_length is not None and length > self.max_length:
                raise ValueError(f"长度 {length} 超过最大长度 {self.max_length}")

        if tn == "str" and self._pattern_re is not None:
            if not self._pattern_re.search(value):
                raise ValueError(f"字符串不匹配模式 {self.pattern!r}")


class ParameterSet:
    """参数集合：负责聚合校验与转换。"""

    def __init__(self, parameters: Optional[Sequence[Parameter]] = None) -> None:
        self._params: Dict[str, Parameter] = {}
        for p in parameters or []:
            self.add(p)

    def add(self, p: Parameter) -> None:
        if p.name in self._params:
            raise ValueError(f"参数重复声明: {p.name}")
        self._params[p.name] = p

    def get(self, name: str) -> Optional[Parameter]:
        return self._params.get(name)

    def __iter__(self):
        return iter(self._params.values())

    def __len__(self) -> int:
        return len(self._params)

    def names(self) -> List[str]:
        return list(self._params.keys())

    def to_list(self) -> List[Dict[str, Any]]:
        """schema 导出（自动文档 / CLI / JSON-RPC）。"""
        return [p.to_dict() for p in self._params.values()]

    def validate(self, raw: Dict[str, Any], *, tool: Optional[str] = None) -> Dict[str, Any]:
        """校验并转换原始输入。

        Args:
            raw: 外部传入的 ``{参数名: 值}``。
            tool: 工具名，用于错误信息。

        Returns:
            转换后的完整参数字典（含默认值）。

        Raises:
            ToolValidationError: 聚合所有字段错误。
        """
        errors: Dict[str, str] = {}
        cleaned: Dict[str, Any] = {}
        unknown = set(raw.keys()) - set(self._params.keys())
        if unknown:
            errors["__unknown__"] = f"未知参数: {', '.join(sorted(unknown))}"

        for name, p in self._params.items():
            if name not in raw or raw[name] is None:
                if p.required:
                    errors[name] = "缺少必填参数"
                else:
                    cleaned[name] = p.default
                continue
            try:
                value = p.coerce(raw[name])
                p.validate(value)
                cleaned[name] = value
            except ValueError as e:
                errors[name] = str(e)

        if errors:
            raise ToolValidationError(errors, tool=tool)
        return cleaned


# ============================================================
# 从函数签名自动推断
# ============================================================

def infer_parameters(func: Callable) -> ParameterSet:
    """从函数签名与类型注解推断 :class:`ParameterSet`。

    规则：
    - 跳过首个参数（约定为 ``ctx: ToolContext``，运行器注入）；
    - 有默认值 → 可选；无默认值 → 必填；
    - 类型注解映射到支持的基础类型，无法识别则按 ``str``；
    - 文档字符串中 ``:param name: 说明`` / Args 段会被提取为 description。
    """
    sig = inspect.signature(func)
    doc_descriptions = _parse_docstring_params(func)
    # 解析字符串注解（兼容 from __future__ import annotations）
    hints = {}
    try:
        hints = typing.get_type_hints(func)
    except Exception:
        # 降级：用函数所在模块全局名字空间尝试 eval 字符串注解
        for _name, _param in sig.parameters.items():
            ann = _param.annotation
            if isinstance(ann, str):
                try:
                    hints[_name] = eval(ann, vars(typing), getattr(func, "__globals__", {}))  # noqa: S307
                except Exception:
                    pass
    params: List[Parameter] = []

    args = list(sig.parameters.values())
    # 跳过前导的 self/ctx/context（函数工具通常是 ctx；直接推断方法时可能有 self+ctx）
    start = 0
    while start < len(args) and args[start].name in ("ctx", "context", "self"):
        start += 1

    for p in list(args)[start:]:
        if p.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        ann = hints.get(p.name, p.annotation)
        if ann is inspect.Parameter.empty:
            ann = str
        required = p.default is inspect.Parameter.empty
        try:
            Parameter._resolve_type_name(ann)
            ann_type = ann
        except ValueError:
            ann_type = str
        params.append(
            Parameter(
                name=p.name,
                type=ann_type,
                required=required,
                default=None if required else p.default,
                description=doc_descriptions.get(p.name, ""),
            )
        )
    return ParameterSet(params)


def _parse_docstring_params(func: Callable) -> Dict[str, str]:
    """从 docstring 提取参数说明（支持 Sphinx ``:param:`` 与 Google 风格 Args:）。"""
    doc = inspect.getdoc(func) or ""
    result: Dict[str, str] = {}

    # Sphinx 风格：:param name: description
    for m in re.finditer(r":param\s+(\w+)\s*:\s*(.+)", doc):
        result[m.group(1)] = m.group(2).strip()

    # Google 风格：Args: 段
    args_match = re.search(r"Args?:\s*\n((?:\s+.+\n?)+)", doc)
    if args_match:
        for line in args_match.group(1).splitlines():
            line = line.strip()
            m = re.match(r"(\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)", line)
            if m:
                result.setdefault(m.group(1), m.group(2).strip())
    return result

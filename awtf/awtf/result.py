"""
执行结果 —— 工具调用的标准化回传结构。

:class:`ToolResult` 统一表达成功/失败，携带：
- 数据（data）与错误（error，JSON 安全字典）；
- 耗时、起止时间；
- 运行元数据（metadata，如调用来源、dry-run）；
- 日志片段（可选，便于上层在结果中展示）。

设计要点：**工具不抛业务异常给调用方**——运行器把异常包装为
``ok=False`` 的结果，调用方只需判断 ``result.ok``。
"""

from __future__ import annotations

import dataclasses
import pathlib
import time
import traceback
from typing import Any, Dict, Optional

from .errors import ToolError


@dataclasses.dataclass
class ToolResult:
    """一次工具调用的结果。

    Attributes:
        tool: 工具名。
        ok: 是否成功。
        data: 工具返回的数据（成功时）。
        error: 错误信息字典（失败时，来自 ``ToolError.to_dict()``）。
        started_at / finished_at: Unix 时间戳。
        duration_ms: 执行耗时（毫秒）。
        metadata: 运行元数据（调用来源、参数脱敏回显等）。
        logs: 执行期间捕获的日志行（若启用了日志捕获）。
    """

    tool: str
    ok: bool = True
    data: Any = None
    error: Optional[Dict[str, Any]] = None
    started_at: float = 0.0
    finished_at: float = 0.0
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)
    logs: list = dataclasses.field(default_factory=list)

    # ---------- 构造便捷方法 ----------

    @classmethod
    def success(cls, tool: str, data: Any, *, started_at: float,
                metadata: Optional[Dict[str, Any]] = None,
                logs: Optional[list] = None) -> "ToolResult":
        finished = time.time()
        return cls(
            tool=tool,
            ok=True,
            data=data,
            started_at=started_at,
            finished_at=finished,
            duration_ms=round((finished - started_at) * 1000, 2),
            metadata=metadata or {},
            logs=logs or [],
        )

    @classmethod
    def failure(cls, tool: str, error: ToolError, *, started_at: float,
                metadata: Optional[Dict[str, Any]] = None,
                logs: Optional[list] = None) -> "ToolResult":
        finished = time.time()
        return cls(
            tool=tool,
            ok=False,
            error=error.to_dict(),
            started_at=started_at,
            finished_at=finished,
            duration_ms=round((finished - started_at) * 1000, 2),
            metadata=metadata or {},
            logs=logs or [],
        )

    # ---------- 使用 ----------

    def raise_for_status(self) -> "ToolResult":
        """失败时抛出对应 :class:`ToolError`，成功时返回自身。

        适用于希望用异常流程处理错误的调用方。
        """
        if self.ok:
            return self
        err = self.error or {}
        raise ToolError(
            err.get("message", "工具执行失败"),
            tool=self.tool,
            details=err.get("details", {}),
        )

    def get(self, key: str, default: Any = None) -> Any:
        """当 ``data`` 为字典时按键取值（便捷访问）。"""
        if isinstance(self.data, dict):
            return self.data.get(key, default)
        return default

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 安全字典（CLI/IPC/日志回传）。"""
        return {
            "tool": self.tool,
            "ok": self.ok,
            "data": _json_safe(self.data),
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": _json_safe(self.metadata),
            "logs": self.logs,
        }


def _json_safe(value: Any) -> Any:
    """把常见 Python 对象转为 JSON 可序列化形式。"""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, pathlib.Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _json_safe(dataclasses.asdict(value))
    return repr(value)


def format_traceback(exc: BaseException) -> str:
    """格式化异常 traceback 为字符串（执行错误详情用）。"""
    return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

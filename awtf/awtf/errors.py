"""
错误体系 —— awtf 所有可预期异常的统一基类与分类。

设计原则：
- 工具执行链路中的错误一律用 ToolError 子类表达，便于调用方按类型捕获；
- 校验错误聚合所有字段问题（field_errors），而非一次只报一个；
- 执行错误保留原始异常链（__cause__）与 traceback，方便排查；
- 每个错误都带 machine-readable ``code``，供 CLI 退出码 / 上层路由判断。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ToolError(Exception):
    """所有 awtf 异常的基类。

    Attributes:
        code: 机器可读错误码，如 ``"TOOL_NOT_FOUND"``。
        tool: 相关工具名（可能为空，例如注册阶段还未确定工具）。
        details: 附加结构化信息，会进入 ``ToolResult.error``。
    """

    code: str = "TOOL_ERROR"

    def __init__(
        self,
        message: str,
        *,
        tool: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.tool = tool
        self.details: Dict[str, Any] = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """序列化为 JSON 安全字典（用于结果回传 / 日志）。"""
        return {
            "code": self.code,
            "message": self.message,
            "tool": self.tool,
            "details": self.details,
        }

    def __str__(self) -> str:  # pragma: no cover - 调试用
        prefix = f"[{self.code}]"
        if self.tool:
            prefix += f" {self.tool}:"
        return f"{prefix} {self.message}"


class ToolNotFoundError(ToolError):
    """请求的工具未在注册表中找到。"""

    code = "TOOL_NOT_FOUND"

    def __init__(self, name: str, *, available: Optional[list] = None) -> None:
        super().__init__(
            f"工具 '{name}' 未注册",
            tool=name,
            details={"available": available or []},
        )


class ToolValidationError(ToolError):
    """输入参数校验失败（可能包含多个字段的错误）。

    Attributes:
        field_errors: ``{字段名: 错误消息}``，一次收集所有问题。
    """

    code = "VALIDATION_ERROR"

    def __init__(self, field_errors: Dict[str, str], *, tool: Optional[str] = None) -> None:
        self.field_errors = dict(field_errors)
        n = len(self.field_errors)
        detail = "；".join(f"{k}: {v}" for k, v in self.field_errors.items())
        super().__init__(
            f"参数校验失败（{n} 处）：{detail}",
            tool=tool,
            details={"field_errors": self.field_errors},
        )


class ToolExecutionError(ToolError):
    """工具运行过程中抛出了未处理的异常。

    原始异常通过 ``__cause__`` 保留；traceback 文本存入 details。
    """

    code = "EXECUTION_ERROR"

    def __init__(self, tool: str, original: BaseException, traceback_text: str) -> None:
        self.original = original
        self.traceback_text = traceback_text
        super().__init__(
            f"工具 '{tool}' 执行失败：{type(original).__name__}: {original}",
            tool=tool,
            details={
                "exception_type": type(original).__name__,
                "exception_message": str(original),
                "traceback": traceback_text,
            },
        )


class ToolConfigError(ToolError):
    """配置缺失、格式错误或无法加载。"""

    code = "CONFIG_ERROR"


class ToolRegistrationError(ToolError):
    """注册失败：名称冲突、缺少元数据、工具对象不合法等。"""

    code = "REGISTRATION_ERROR"


class ToolDiscoveryError(ToolError):
    """模块发现 / 导入失败（路径不存在、import 错误等）。"""

    code = "DISCOVERY_ERROR"

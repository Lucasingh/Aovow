"""错误体系与结果对象测试。"""

from __future__ import annotations

import pytest

from awtf import (
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistrationError,
    ToolValidationError,
)
from conftest import create_registry


class TestErrorHierarchy:
    def test_all_are_tool_errors(self):
        for exc_cls in (ToolNotFoundError, ToolValidationError,
                        ToolExecutionError, ToolRegistrationError):
            assert issubclass(exc_cls, ToolError)

    def test_not_found_to_dict(self):
        e = ToolNotFoundError("ghost", available=["a", "b"])
        d = e.to_dict()
        assert d["code"] == "TOOL_NOT_FOUND"
        assert d["tool"] == "ghost"
        assert d["details"]["available"] == ["a", "b"]

    def test_validation_aggregates_fields(self):
        e = ToolValidationError({"a": "缺少必填", "b": "类型错误"}, tool="t")
        assert len(e.field_errors) == 2
        d = e.to_dict()
        assert d["details"]["field_errors"]["a"] == "缺少必填"

    def test_execution_error_preserves_cause(self):
        original = ValueError("坏值")
        try:
            raise original
        except ValueError:
            import traceback as tb
            tb_text = "".join(tb.format_exc())
            e = ToolExecutionError("my_tool", original, tb_text)

        assert e.original is original
        d = e.to_dict()
        assert d["details"]["exception_type"] == "ValueError"
        assert "Traceback" in d["details"]["traceback"]

    def test_str_includes_code(self):
        e = ToolNotFoundError("x")
        assert "TOOL_NOT_FOUND" in str(e)


class TestResultFailure:
    def test_failure_result_serializable(self):
        reg = create_registry()
        result = reg.run("boom", {})
        import json
        d = result.to_dict()
        json.dumps(d)  # 不抛异常
        assert d["ok"] is False
        assert d["error"]["code"] == "EXECUTION_ERROR"

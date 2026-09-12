"""执行链路测试：成功/校验失败/异常包装/异步/日志/元数据/计时。"""

from __future__ import annotations

import time

import pytest

from awtf import (
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
    tool,
)
from conftest import create_registry


class TestSuccess:
    def test_basic_run(self, registry):
        result = registry.run("add", {"a": 1, "b": 2})
        assert result.ok
        assert result.data == 3
        assert result.error is None
        assert result.tool == "add"

    def test_string_coercion(self, registry):
        # CLI 传来的字符串应被转为 int
        result = registry.run("add", {"a": "10", "b": "5"})
        assert result.ok
        assert result.data == 15

    def test_defaults_applied(self, registry):
        result = registry.run("add", {"a": 1})  # b 默认 1
        assert result.data == 2

    def test_duration_recorded(self, registry):
        result = registry.run("add", {"a": 1, "b": 2})
        assert result.duration_ms >= 0
        assert result.finished_at >= result.started_at

    def test_class_tool(self, registry):
        result = registry.run("multiply", {"a": 3})  # b 默认 2
        assert result.ok
        assert result.data == {"product": 6, "a": 3, "b": 2}


class TestFailures:
    def test_tool_not_found(self, registry):
        result = registry.run("ghost", {})
        assert not result.ok
        assert result.error["code"] == "TOOL_NOT_FOUND"

    def test_not_found_raises_when_asked(self, registry):
        with pytest.raises(ToolNotFoundError):
            registry.run("ghost", {}, raise_on_error=True)

    def test_validation_error_structure(self, registry):
        result = registry.run("add", {"b": 2})  # 缺 a
        assert not result.ok
        assert result.error["code"] == "VALIDATION_ERROR"
        assert "a" in result.error["details"]["field_errors"]

    def test_validation_raises_when_asked(self, registry):
        with pytest.raises(ToolValidationError):
            registry.run("add", {"b": 2}, raise_on_error=True)

    def test_execution_error_wrapped(self, registry):
        result = registry.run("boom", {})
        assert not result.ok
        assert result.error["code"] == "EXECUTION_ERROR"
        details = result.error["details"]
        assert details["exception_type"] == "RuntimeError"
        assert "故意炸了" in details["exception_message"]
        assert "Traceback" in details["traceback"]

    def test_execution_error_raises_when_asked(self, registry):
        with pytest.raises(ToolExecutionError):
            registry.run("boom", {}, raise_on_error=True)

    def test_tool_error_from_inside_preserved(self, empty_registry):
        @tool(name="check")
        def check(ctx, value: int):
            if value < 0:
                raise ToolError("值不能为负", tool="check")
            return value

        empty_registry.register(check)
        result = empty_registry.run("check", {"value": -1})
        assert not result.ok
        assert result.error["code"] == "TOOL_ERROR"
        assert "不能为负" in result.error["message"]


class TestAsync:
    def test_async_tool_runs(self, registry):
        result = registry.run("async_echo", {"message": "hello"})
        assert result.ok
        assert result.data == {"echo": "hello", "async": True}


class TestMetadataAndContext:
    def test_metadata_passed(self, registry):
        result = registry.run("add", {"a": 1, "b": 2},
                              metadata={"source": "test", "request_id": "req-1"})
        assert result.metadata["source"] == "test"
        assert result.metadata["request_id"] == "req-1"

    def test_dry_run_metadata(self, empty_registry):
        @tool(name="side_effect")
        def side_effect(ctx):
            if ctx.dry_run:
                return {"would": True}
            return {"would": False}

        empty_registry.register(side_effect)
        result = empty_registry.run("side_effect", {}, metadata={"dry_run": True})
        assert result.data == {"would": True}
        assert result.metadata["dry_run"] is True


class TestConfig:
    def test_config_visible_to_tool(self, empty_registry):
        @tool(name="cfg")
        def cfg(ctx, key: str):
            return {"value": ctx.get_config(key, "default")}

        empty_registry.register(cfg)
        result = empty_registry.run(
            "cfg", {"key": "greeting"},
            config={"cfg": {"greeting": "你好"}},
        )
        assert result.data == {"value": "你好"}

    def test_config_default(self, empty_registry):
        @tool(name="cfg2")
        def cfg2(ctx):
            return ctx.get_config("missing", "fallback")

        empty_registry.register(cfg2)
        assert empty_registry.run("cfg2", {}).data == "fallback"


class TestLogCapture:
    def test_logs_captured(self, registry):
        result = registry.run("add", {"a": 1, "b": 2}, capture_logs=True)
        assert result.ok
        assert any("add" in line for line in result.logs)

    def test_logs_not_captured_by_default(self, registry):
        result = registry.run("add", {"a": 1, "b": 2})
        assert result.logs == []


class TestResultHelpers:
    def test_to_dict_json_safe(self, registry):
        result = registry.run("add", {"a": 1, "b": 2})
        d = result.to_dict()
        import json
        json.dumps(d, ensure_ascii=False)  # 不抛异常即可
        assert d["ok"] is True

    def test_raise_for_status(self, registry):
        ok = registry.run("add", {"a": 1})
        assert ok.raise_for_status() is ok
        fail = registry.run("boom", {})
        with pytest.raises(ToolError):
            fail.raise_for_status()

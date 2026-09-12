"""注册表测试：注册/冲突/覆盖/查询/发现。"""

from __future__ import annotations

import pathlib

import pytest

from conftest import MultiplyTool, add_tool, create_registry  # noqa: F401
from awtf import (
    FunctionTool,
    ToolContext,
    ToolNotFoundError,
    ToolRegistrationError,
    ToolRegistry,
    tool,
)

EXAMPLES_DIR = pathlib.Path(__file__).resolve().parent.parent / "examples"


class TestRegistration:
    def test_register_and_names(self, registry):
        assert set(registry.names()) == {"add", "greet", "boom", "async_echo", "multiply"}

    def test_name_conflict_raises(self, empty_registry):
        empty_registry.register(add_tool)
        with pytest.raises(ToolRegistrationError, match="已存在"):
            empty_registry.register(add_tool)

    def test_override(self, empty_registry):
        empty_registry.register(add_tool)
        empty_registry.register(add_tool, override=True)
        assert empty_registry.has("add")

    def test_unregister(self, registry):
        assert registry.unregister("add") is True
        assert registry.unregister("add") is False
        assert not registry.has("add")

    def test_get_missing(self, registry):
        with pytest.raises(ToolNotFoundError) as exc:
            registry.get("nope")
        assert "add" in exc.value.details["available"]

    def test_register_unwrapped_function_rejected(self, empty_registry):
        def plain(ctx, x: int):
            return x

        with pytest.raises(ToolRegistrationError, match="@tool"):
            empty_registry.register(plain)

    def test_register_class(self, empty_registry):
        empty_registry.register(MultiplyTool)
        assert empty_registry.has("multiply")


class TestDecorator:
    def test_registry_tool_decorator(self):
        reg = ToolRegistry()

        @reg.tool(name="double", tags=["math"])
        def double(ctx, x: int) -> int:
            """翻倍。"""
            return x * 2

        assert isinstance(double, FunctionTool)
        assert reg.has("double")
        result = reg.run("double", {"x": 21})
        assert result.data == 42

    def test_bare_tool_decorator_callable(self):
        @tool(name="triple")
        def triple(ctx, x: int) -> int:
            return x * 3

        # 装饰后仍可像函数直接调用
        ctx = ToolContext.create("triple")
        assert triple(ctx, x=2) == 6


class TestListAndFilter:
    def test_list_all(self, registry):
        tools = registry.list_tools()
        assert len(tools) == 5
        assert all("parameters" in t for t in tools)

    def test_filter_by_tag(self, registry):
        math_tools = registry.list_tools(tag="math")
        names = {t["name"] for t in math_tools}
        assert names == {"add", "multiply"}

    def test_describe_schema(self, registry):
        d = registry.describe("add")
        assert d["name"] == "add"
        assert d["version"] == "1.2.0"
        param_names = [p["name"] for p in d["parameters"]]
        assert param_names == ["a", "b"]
        assert d["kind"] == "function"


class TestDiscovery:
    def test_discover_path(self):
        reg = ToolRegistry()
        found = reg.discover_path(EXAMPLES_DIR)
        assert "word_count" in found
        assert "organize_dir" in found
        assert "sleep_sort" in found

    def test_discover_single_file(self):
        reg = ToolRegistry()
        found = reg.discover_path(EXAMPLES_DIR / "text_tools.py")
        assert set(found) == {"word_count", "text_case", "find_all"}

    def test_discover_nonexistent_raises(self):
        reg = ToolRegistry()
        with pytest.raises(Exception):
            reg.discover_path(EXAMPLES_DIR / "no_such_dir")

    def test_discovered_tool_runs(self):
        reg = ToolRegistry()
        reg.discover_path(EXAMPLES_DIR / "text_tools.py")
        result = reg.run("word_count", {"text": "a b c d"})
        assert result.ok
        assert result.data["words"] == 4

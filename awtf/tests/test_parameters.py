"""参数系统测试：类型转换、约束校验、必填/默认、签名推断。"""

from __future__ import annotations

import pathlib

import pytest

from awtf import Parameter, ParameterSet, ToolValidationError, infer_parameters


# ---------- 类型转换 ----------

class TestCoerce:
    def test_int_from_string(self):
        p = Parameter("n", int)
        assert p.coerce("42") == 42
        assert p.coerce(42) == 42

    def test_int_invalid(self):
        p = Parameter("n", int)
        with pytest.raises(ValueError, match="整数"):
            p.coerce("abc")

    def test_bool_variants(self):
        p = Parameter("flag", bool)
        assert p.coerce("true") is True
        assert p.coerce("YES") is True
        assert p.coerce("0") is False
        assert p.coerce("否") is False
        assert p.coerce(True) is True

    def test_bool_invalid(self):
        p = Parameter("flag", bool)
        with pytest.raises(ValueError, match="布尔"):
            p.coerce("maybe")

    def test_float(self):
        p = Parameter("x", float)
        assert p.coerce("3.14") == pytest.approx(3.14)

    def test_list_from_csv(self):
        p = Parameter("items", list)
        assert p.coerce("a, b ,c") == ["a", "b", "c"]
        assert p.coerce([1, 2]) == [1, 2]

    def test_dict_from_json_string(self):
        p = Parameter("data", dict)
        assert p.coerce('{"k": 1}') == {"k": 1}
        with pytest.raises(ValueError, match="JSON"):
            p.coerce("{bad json}")

    def test_path(self):
        p = Parameter("f", "path")
        result = p.coerce("~/test.txt")
        assert isinstance(result, pathlib.Path)


# ---------- 约束校验 ----------

class TestConstraints:
    def test_choices(self):
        p = Parameter("mode", str, choices=["a", "b"])
        p.validate("a")
        with pytest.raises(ValueError, match="取值"):
            p.validate("c")

    def test_numeric_range(self):
        p = Parameter("age", int, min=0, max=120)
        p.validate(50)
        with pytest.raises(ValueError, match="最小值"):
            p.validate(-1)
        with pytest.raises(ValueError, match="最大值"):
            p.validate(200)

    def test_string_length(self):
        p = Parameter("name", str, min_length=2, max_length=5)
        p.validate("abc")
        with pytest.raises(ValueError, match="最小长度"):
            p.validate("a")
        with pytest.raises(ValueError, match="最大长度"):
            p.validate("abcdef")

    def test_pattern(self):
        p = Parameter("code", str, pattern=r"^\d{4}$")
        p.validate("1234")
        with pytest.raises(ValueError, match="模式"):
            p.validate("12ab")


# ---------- 必填 / 默认值 ----------

class TestRequired:
    def test_required_missing(self):
        ps = ParameterSet([Parameter("x", int)])
        with pytest.raises(ToolValidationError) as exc:
            ps.validate({})
        assert "x" in exc.value.field_errors

    def test_optional_with_default(self):
        ps = ParameterSet([Parameter("x", int, default=10)])
        cleaned = ps.validate({})
        assert cleaned == {"x": 10}

    def test_required_auto_from_default(self):
        # 给了默认值 → 自动可选
        p = Parameter("x", int, default=5)
        assert p.required is False
        # 不给默认值 → 必填
        assert Parameter("y", int).required is True
        # 显式 required 优先
        assert Parameter("z", int, default=1, required=True).required is True

    def test_unknown_param_collected(self):
        ps = ParameterSet([Parameter("x", int)])
        with pytest.raises(ToolValidationError) as exc:
            ps.validate({"x": 1, "y": 2})
        assert "__unknown__" in exc.value.field_errors

    def test_multiple_errors_aggregated(self):
        ps = ParameterSet([
            Parameter("a", int),
            Parameter("b", int, min=0),
        ])
        with pytest.raises(ToolValidationError) as exc:
            ps.validate({"b": -5})
        # a 缺失 + b 越界，两个错误同时收集
        assert "a" in exc.value.field_errors
        assert "b" in exc.value.field_errors


# ---------- 签名推断 ----------

class TestInference:
    def test_infer_basic(self):
        def my_tool(ctx, name: str, count: int = 3, flag: bool = False):
            return name

        ps = infer_parameters(my_tool)
        names = ps.names()
        assert names == ["name", "count", "flag"]

        name_p = ps.get("name")
        assert name_p.type_name == "str" and name_p.required is True
        count_p = ps.get("count")
        assert count_p.type_name == "int" and count_p.required is False and count_p.default == 3
        flag_p = ps.get("flag")
        assert flag_p.type_name == "bool"

    def test_infer_skips_ctx_and_self(self):
        class T:
            def run(self, ctx, x: int):
                return x

        ps = infer_parameters(T.run)
        assert ps.names() == ["x"]

    def test_infer_docstring_description(self):
        def my_tool(ctx, value: str):
            """做某事。

            Args:
                value: 这是值
            """
            return value

        ps = infer_parameters(my_tool)
        assert ps.get("value").description == "这是值"

    def test_infer_optional_annotation(self):
        from typing import Optional

        def my_tool(ctx, note: Optional[str] = None):
            return note

        ps = infer_parameters(my_tool)
        assert ps.get("note").type_name == "str"

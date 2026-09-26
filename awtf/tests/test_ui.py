"""ui 组件库数据层单元测试（不依赖显示环境）。"""

import pytest

from awtf.ui import (
    ButtonSpec,
    Callbacks,
    CardSpec,
    ConfirmDialog,
    InputDialog,
    InputField,
    InputSpec,
    LabelSpec,
    MessageDialog,
    ProgressBar,
    TableSpec,
    TextAreaSpec,
    make_theme,
    validate_fields,
)


class TestInputField:
    def test_required(self):
        f = InputField("name", label="姓名", required=True)
        ok, value, err = f.validate("")
        assert not ok and err == "姓名为必填项"
        ok, value, err = f.validate("张三")
        assert ok and value == "张三"

    def test_optional_default(self):
        f = InputField("age", default=18)
        ok, value, err = f.validate("")
        assert ok and value == 18

    def test_number(self):
        f = InputField("n", kind="number", min=0, max=10)
        assert f.validate("5")[0]
        assert f.validate("15") == (False, None, "n不能大于 10")
        assert f.validate("abc") == (False, None, "n必须是整数")

    def test_float(self):
        f = InputField("x", kind="float", min=0.0, max=1.0)
        ok, value, err = f.validate("0.5")
        assert ok and value == 0.5
        assert not f.validate("-1")[0]

    def test_email(self):
        f = InputField("e", kind="email")
        assert f.validate("a@b.com")[0]
        assert f.validate("not-an-email") == (
            False, None, "e不是有效的邮箱地址")

    def test_phone(self):
        f = InputField("p", kind="phone")
        assert f.validate("13800138000")[0]
        assert not f.validate("12345")[0]

    def test_password_kind(self):
        f = InputField("pw", kind="password", required=True)
        ok, value, err = f.validate("secret")
        assert ok and value == "secret"

    def test_pattern(self):
        f = InputField("code", pattern=r"^[A-Z]{3}$")
        assert f.validate("ABC")[0]
        assert not f.validate("abc")[0]

    def test_choices(self):
        f = InputField("level", choices=["low", "high"])
        assert f.validate("high")[0]
        assert not f.validate("mid")[0]

    def test_length(self):
        f = InputField("s", min_length=2, max_length=5)
        assert f.validate("ab")[0]
        assert not f.validate("a")[0]
        assert not f.validate("abcdef")[0]

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            InputField("x", kind="color")

    def test_format_display_secret(self):
        f = InputField("pw", kind="password", secret=True)
        assert f.format_display("secret") == "***"


class TestValidateFields:
    def test_aggregate_errors(self):
        fields = [
            InputField("name", required=True),
            InputField("age", kind="number", min=0, max=100),
        ]
        ok, cleaned, errors = validate_fields(fields, {"name": "", "age": "200"})
        assert not ok
        assert "name" in errors and "age" in errors

    def test_unknown_field(self):
        fields = [InputField("a")]
        ok, cleaned, errors = validate_fields(fields, {"a": "1", "zzz": "x"})
        assert not ok
        assert "__unknown__" in errors

    def test_clean(self):
        fields = [InputField("a", default="d")]
        ok, cleaned, errors = validate_fields(fields, {})
        assert ok and cleaned == {"a": "d"}


class TestComponents:
    def test_button_style_validation(self):
        ButtonSpec("确定", style="danger")
        with pytest.raises(ValueError):
            ButtonSpec("确定", style="rainbow")

    def test_button_size_validation(self):
        ButtonSpec("确定", size="small")
        with pytest.raises(ValueError):
            ButtonSpec("确定", size="huge")

    def test_message_dialog_level(self):
        MessageDialog("t", "m", level="error")
        with pytest.raises(ValueError):
            MessageDialog("t", "m", level="fatal")

    def test_table_row_length(self):
        TableSpec(columns=["a", "b"], rows=[["1", "2"]])
        with pytest.raises(ValueError):
            TableSpec(columns=["a", "b"], rows=[["1"]])

    def test_table_row_dict(self):
        t = TableSpec(columns=["name", "value"], rows=[["CPU", 50]])
        assert t.row_dict(0) == {"name": "CPU", "value": 50}

    def test_table_sort(self):
        t = TableSpec(columns=["name", "value"], rows=[
            ["b", 1], ["a", 3], ["c", 2],
        ])
        t.sort_rows(1)
        assert [r[0] for r in t.rows] == ["b", "c", "a"]

    def test_card_children(self):
        card = CardSpec(title="t", children=[LabelSpec("x"), ButtonSpec("b")])
        assert len(card.children) == 2

    def test_input_spec_wraps_field(self):
        spec = InputSpec(InputField("u"))
        assert spec.name == "u"
        assert spec.to_field_dict()["name"] == "u"

    def test_progress_clamp(self):
        assert ProgressBar(value=150).value == 100.0
        assert ProgressBar(value=-5).value == 0.0
        assert ProgressBar(value=None).value is None

    def test_make_theme_override(self):
        theme = make_theme(primary="#123456")
        assert theme["primary"] == "#123456"
        assert theme["danger"] == "#e74c3c"  # 未覆盖项保留默认

    def test_textarea_spec(self):
        ta = TextAreaSpec("chat", text="hi", readonly=True, height=20)
        assert ta.name == "chat" and ta.text == "hi"
        assert ta.readonly is True and ta.height == 20


class TestCallbacks:
    def test_register_and_call(self):
        seen = []
        cbs = Callbacks({"on_x": lambda p: seen.append(p)})
        cbs.call("on_x", "payload")
        assert seen == ["payload"]

    def test_register_after_init(self):
        cbs = Callbacks()
        cbs.register("on_y", lambda p: None)
        assert cbs.has("on_y")
        assert not cbs.has("missing")

    def test_call_missing_is_safe(self):
        Callbacks().call("nothing")

    def test_contains(self):
        cbs = Callbacks({"a": lambda p: None})
        assert "a" in cbs


class TestInputDialog:
    def test_validate(self):
        dlg = InputDialog("t", fields=[
            InputField("name", required=True),
            InputField("age", kind="number", min=0),
        ])
        ok, cleaned, errors = dlg.validate({"name": "x", "age": "abc"})
        assert not ok and "age" in errors
        ok, cleaned, errors = dlg.validate({"name": "x", "age": "30"})
        assert ok and cleaned == {"name": "x", "age": 30}

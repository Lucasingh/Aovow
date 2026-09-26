"""tkinter 渲染后端集成测试。

需要图形环境；无显示时（CI 无头环境）自动跳过。
用 after + update 驱动事件循环，不做真实 mainloop。
"""

import tkinter as tk

import pytest

from awtf.ui import (
    App,
    ButtonSpec,
    CardSpec,
    ConfirmDialog,
    DividerSpec,
    IconSpec,
    InputDialog,
    InputField,
    InputSpec,
    LabelSpec,
    ListSpec,
    MessageDialog,
    ProgressBar,
    RowSpec,
    Spinner,
    TableSpec,
    TextAreaSpec,
)
from awtf.ui.tk_backend import AppWindow, show_confirm, show_input, show_message

try:
    tk.Tk()
    _TK_AVAILABLE = True
    tk.Tk().destroy()
except tk.TclError:
    _TK_AVAILABLE = False

needs_display = pytest.mark.skipif(not _TK_AVAILABLE, reason="无图形环境")


def _build_app() -> App:
    return App(
        title="测试",
        width=480,
        height=520,
        children=[
            LabelSpec("标题", bold=True, size=16),
            CardSpec(title="卡片", children=[
                InputSpec(InputField("username", label="用户名",
                                     required=True, placeholder="占位")),
                InputSpec(InputField("password", label="密码",
                                     kind="password")),
                RowSpec([ButtonSpec("确定", on_click="ok"),
                         ButtonSpec("取消", style="ghost")]),
            ]),
            DividerSpec(),
            TableSpec(columns=["a", "b"], rows=[["1", "2"]],
                      selectable=True, on_select="row"),
            ListSpec(items=["x", "y"], height=3, on_select="sel"),
            RowSpec([Spinner(text="加载中"), ProgressBar(value=30)]),
            IconSpec("🎉"),
            TextAreaSpec("chat", height=6, readonly=True, text="hello\n"),
        ],
    )


@needs_display
class TestAppWindow:
    def test_render_all_components(self):
        window = AppWindow(_build_app(), {"ok": lambda p: None})
        window.root.update()
        assert window.root.title() == "测试"
        assert window.root.winfo_width() > 0

    def test_get_values(self):
        window = AppWindow(_build_app())
        window.root.update()
        values = window.get_values()
        assert "username" in values and "password" in values

    def test_textarea_append(self):
        window = AppWindow(_build_app())
        window.root.update()
        window.append_text("chat", "world")
        content = window.text_areas["chat"].get("1.0", "end")
        assert "hello" in content and "world" in content
        window.root.destroy()

    def test_callback_fires(self):
        seen = []
        window = AppWindow(_build_app(), {"ok": lambda p: seen.append(p)})
        window.root.update()
        window.cbs.call("ok")
        assert len(seen) == 1
        window.root.destroy()


@needs_display
class TestDialogs:
    def test_show_message_returns(self):
        root = tk.Tk()
        root.withdraw()
        root.after(250, _close_toplevels, root)
        show_message(root, MessageDialog("提示", "完成", level="success"))
        root.destroy()

    def test_show_confirm_closed_false(self):
        root = tk.Tk()
        root.withdraw()
        root.after(250, _close_toplevels, root)
        result = show_confirm(root, ConfirmDialog("确认", "继续？"))
        assert result is False
        root.destroy()

    def test_show_input_closed_none(self):
        dlg = InputDialog("输入", fields=[
            InputField("name", required=True),
            InputField("age", kind="number", min=0),
        ])
        root = tk.Tk()
        root.withdraw()
        root.after(250, _close_toplevels, root)
        result = show_input(root, dlg)
        assert result is None
        root.destroy()


def _close_toplevels(root: tk.Tk):
    for w in root.winfo_children():
        if isinstance(w, tk.Toplevel):
            w.destroy()
    root.after(30, root.destroy)

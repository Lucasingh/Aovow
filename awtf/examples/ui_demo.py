"""
UI 组件库示例：跑一个完整的登录表单 + 系统信息表格。

运行（需要图形界面；Linux 需 python3-tk）：
    python examples/ui_demo.py
"""

import sys

sys.path.insert(0, ".")

from awtf.sysinfo import collect_system_info  # noqa: E402
from awtf.ui import (  # noqa: E402
    App,
    ButtonSpec,
    CardSpec,
    DividerSpec,
    IconSpec,
    InputField,
    InputSpec,
    LabelSpec,
    RowSpec,
    TableSpec,
    render_app,
    show_confirm,
    show_message,
    show_toast,
)
from awtf.ui.tk_backend import AppWindow  # noqa: E402


def on_login(_payload=None):
    values = window.get_values()
    if not values.get("username"):
        show_message(window.root, __import__("awtf.ui").MessageDialog(
            "提示", "请输入用户名", level="warning"))
        return
    ok = show_confirm(window.root, __import__("awtf.ui").ConfirmDialog(
        "确认", f"以 {values['username']} 登录？"))
    if ok:
        show_message(window.root, __import__("awtf.ui").MessageDialog(
            "成功", "登录成功（演示）", level="success"))


def on_row(payload=None):
    show_toast(window.root, __import__("awtf.ui").Toast(
        f"选中: {payload}", level="info"))


def build_app() -> App:
    info = collect_system_info()
    hw = info["hardware"]
    rows = [
        ["CPU 型号", hw["cpu"]["model"]],
        ["CPU 使用率", f"{hw['cpu']['usage_percent']}%"],
        ["内存", f"{hw['memory']['total']} / {hw['memory']['usage_percent']}%"],
        ["系统", f"{info['os']['system']} {info['os']['release']}"],
        ["本机 IP", str(info["network"]["ip"])],
    ]
    return App(
        title="AWTF UI 组件示例",
        width=560, height=640,
        children=[
            RowSpec([
                IconSpec("🧰", size=24),
                LabelSpec("AWTF UI 组件库示例", bold=True, size=16),
            ]),
            CardSpec(title="登录", children=[
                InputSpec(InputField("username", label="用户名",
                                     required=True, placeholder="请输入用户名")),
                InputSpec(InputField("password", label="密码",
                                     kind="password", required=True)),
                RowSpec([
                    ButtonSpec("登录", on_click="on_login"),
                    ButtonSpec("清空", style="ghost", on_click="on_login"),
                ]),
            ]),
            DividerSpec(),
            LabelSpec("系统信息（来自 awtf.sysinfo）", bold=True),
            TableSpec(columns=["指标", "值"], rows=rows,
                      selectable=True, on_select="on_row"),
            DividerSpec(),
            RowSpec([
                ButtonSpec("📊 刷新信息", style="success", on_click="on_login"),
                ButtonSpec("退出", style="danger"),
            ]),
        ],
    )


if __name__ == "__main__":
    app = build_app()
    # 用 AppWindow 以便保留窗口引用（on_login 里读取输入值）
    from awtf.ui.tk_backend import AppWindow as _AW
    window = _AW(app, {"on_login": on_login, "on_row": on_row})
    window.root.mainloop()

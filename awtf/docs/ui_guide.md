# ui —— 跨平台 UI 设计组件库

> 版本 1.1.0 新增。用**纯 Python 代码**搭建桌面界面，组件 = 数据描述 + 验证逻辑，
> 渲染由后端完成（默认 tkinter，**零第三方依赖、三平台一致**）。
>
> 无图形环境（服务器/CI）下不影响库的其他模块——只有调用 UI 渲染时才需要显示。

---

## 设计哲学

```
组件描述（ButtonSpec / InputField / CardSpec / TableSpec ...）
   ├─ 纯数据：可序列化、可单测、可跨进程传递
   ├─ 验证逻辑：InputField.validate / validate_fields（不依赖显示）
   └─ 渲染后端：tkinter（默认）
```

好处：

- **可测试**：验证/格式化/排序等逻辑不碰显示器，单测秒过；
- **可组合**：`CardSpec` 里放任意组件，`RowSpec` 横向排列；
- **跨平台**：Windows / macOS / Linux 表现一致（tk 控件统一配色，`ttk.Treeview` 仅表格用）。

## 30 秒上手

```python
from awtf.ui import (
    App, LabelSpec, InputField, InputSpec, ButtonSpec, render_app,
)

def on_login(payload=None):
    print("登录", payload)

app = App(
    title="登录",
    width=420, height=300,
    children=[
        LabelSpec("欢迎登录", bold=True, size=16),
        InputSpec(InputField("username", label="用户名", required=True,
                             placeholder="请输入用户名")),
        InputSpec(InputField("password", label="密码", kind="password")),
        ButtonSpec("登录", on_click="on_login"),
    ],
)

render_app(app, callbacks={"on_login": on_login})   # 进入事件循环
```

## 组件总览

### 基础控件（`awtf.ui.widgets`）

| 组件 | 说明 |
|------|------|
| `ButtonSpec(text, style, disabled, size, icon, on_click, tooltip)` | 按钮。`style`: `primary/secondary/success/danger/ghost`；`size`: `small/medium/large`；`disabled` 禁用态 |
| `InputSpec(field, on_change, on_submit)` | 输入框，包装 `InputField`；`on_submit` 绑定回车提交 |
| `TextAreaSpec(name, text, readonly, height, on_change)` | 多行文本区（聊天记录/日志）。只读时用 `AppWindow.append_text(name, chunk)` 追加并自动滚底 |
| `LabelSpec(text, color, size, bold, align, wrap)` | 文本标签 |
| `IconSpec(icon, size, color)` | 图标（跨平台用 Unicode emoji 渲染） |
| `RowSpec(children, spacing)` | 横向排列容器 |
| `DividerSpec(thickness)` | 分隔线 |

### 容器（`awtf.ui.containers`）

| 组件 | 说明 |
|------|------|
| `CardSpec(title, children, padding, border, elevated)` | 卡片容器 |
| `ListSpec(items, multi_select, height, on_select, selected)` | 列表。选择回调 payload 为**索引列表** |
| `TableSpec(columns, rows, height, selectable, on_select)` | 表格（行数据长度与列数校验；`row_dict(i)` 转 `{列名: 值}`；`sort_rows(col, reverse)` 排序）。选择回调 payload 为**整行 dict** |

### 输入字段与验证（`awtf.ui.core`）

`InputField(name, label, kind, required, default, placeholder, min, max,
min_length, max_length, pattern, choices, hint, secret)`

| `kind` | 验证/转换 |
|--------|-----------|
| `text` | 长度限制 + 可选正则 `pattern` |
| `number` | 转整数 + `min`/`max` 范围 |
| `float` | 转小数 + `min`/`max` 范围 |
| `password` | 输入掩码显示 |
| `email` | 邮箱格式校验 |
| `phone` | 大陆手机号校验 |

核心方法 `field.validate(raw) -> (ok, value, error)`，批量为
`validate_fields(fields, raw) -> (ok, cleaned, errors)`——**一次收集所有字段错误**。

```python
from awtf.ui import InputField, validate_fields

age = InputField("age", kind="number", min=0, max=150)
age.validate("200")          # -> (False, None, "age不能大于 150")

ok, cleaned, errors = validate_fields(
    [InputField("name", required=True)], {"name": ""})
# ok=False, errors={"name": "姓名为必填项"}
```

### 对话框与反馈

| 组件 | 使用 |
|------|------|
| `show_message(parent, MessageDialog(title, message, level))` | 模态提示（`level`: info/success/warning/error） |
| `show_confirm(parent, ConfirmDialog(title, message, danger))` | 模态确认，返回 `True/False` |
| `show_input(parent, InputDialog(title, message, fields))` | 模态输入对话框：**多字段 + 逐字段验证 + 错误红字提示**，确认返回 `{字段名: 值}`，取消返回 `None` |
| `show_toast(parent, Toast(message, level, duration_ms))` | 右下角自动消失气泡 |
| `Spinner(size, color, text)` | 加载指示器（无限旋转动画） |
| `ProgressBar(value, width, height, color, show_text)` | 进度条；`value=None` 为不确定进度（滚动动画） |

```python
from awtf.ui import InputDialog, InputField, show_input, show_message, MessageDialog

dlg = InputDialog("新建任务", "请填写任务信息", fields=[
    InputField("title", label="标题", required=True, max_length=20),
    InputField("priority", label="优先级", choices=["低", "中", "高"]),
    InputField("due_days", label="期限(天)", kind="number", min=1, max=365),
])
values = show_input(parent_window, dlg)     # 确认 -> dict；取消 -> None
if values:
    show_message(parent_window, MessageDialog("完成", "已创建", level="success"))
```

## 主题

```python
from awtf.ui import make_theme, App

app = App("标题", theme=make_theme(primary="#e67e22", bg="#fdf6ec"))
```

`make_theme(**overrides)` 基于默认主题浅拷贝覆盖：
`primary/success/danger/warning/secondary/bg/bg_card/text/text_secondary/border/
focus/error_bg/error_text/font_family/font_size/font_size_small/font_size_title/
radius/padding/spacing/control_height`。

## 渲染后端

```python
from awtf.ui.tk_backend import AppWindow   # 不想阻塞时用 AppWindow 手动驱动

window = AppWindow(app, callbacks)
window.root.update()       # 刷新一次（测试/嵌入用）
window.root.mainloop()     # 进入事件循环
```

`render_app(app, callbacks)` 等价于 `AppWindow(...) + mainloop()`。

## 跨平台注意

- **Windows / macOS**：tkinter 随 Python 自带，开箱即用。
- **Linux**：需 `apt install python3-tk`（Debian/Ubuntu）等对应包。
- 无显示环境（`DISPLAY` 未设置）下构造 `Tk()` 会抛 `TclError`——
  请用 `try/except` 包住渲染代码，或让库在无显示时走 CLI 路径。

## 完整示例

- [`examples/ui_demo.py`](../examples/ui_demo.py)：登录表单 + 系统信息表格 + 确认框 + Toast。
- [`examples/deepseek_chat_demo.py`](../examples/deepseek_chat_demo.py)：填写 DeepSeek API Key 的
  **流式对话**页面——后台线程读 SSE → 队列 → `AppWindow.append_text` 增量渲染，零第三方依赖。

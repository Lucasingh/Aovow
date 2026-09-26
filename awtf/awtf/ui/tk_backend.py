"""
tkinter 渲染后端：把 ui 组件描述渲染为可运行的桌面界面。

- 仅使用标准库 ``tkinter``，三平台（Windows / macOS / Linux）零依赖。
- 组件绘制统一用 ``tk`` 控件（完全控制颜色，跨平台一致）；表格用 ``ttk.Treeview``。
- 对话框/输入对话框为模态阻塞调用，返回用户结果，适合工具直接使用。

快速上手::

    from awtf.ui import App, LabelSpec, ButtonSpec, InputSpec, InputField
    from awtf.ui.tk_backend import render_app

    app = App(
        title="登录",
        children=[
            InputSpec(InputField("username", label="用户名")),
            InputSpec(InputField("password", kind="password", label="密码")),
            ButtonSpec("登录", on_click="on_login"),
        ],
    )
    render_app(app, callbacks={"on_login": handler})

注意：Linux 需安装 ``python3-tk``；无显示环境（CI/服务器）下会抛 TclError，
请捕获或跳过 UI 渲染（不影响库的其他模块）。
"""

from __future__ import annotations

import dataclasses
import math
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .core import Callbacks, DEFAULT_THEME, InputField
from .containers import CardSpec, ListSpec, TableSpec
from .dialogs import ConfirmDialog, InputDialog, MessageDialog
from .feedback import ProgressBar, Spinner, Toast
from .widgets import (
    ButtonSpec, Component, DividerSpec, IconSpec, InputSpec, LabelSpec, RowSpec,
    TextAreaSpec,
)


@dataclasses.dataclass
class App:
    """顶层窗口描述。"""

    title: str
    width: int = 480
    height: int = 360
    children: List[Component] = dataclasses.field(default_factory=list)
    on_close: Optional[str] = None
    theme: Dict[str, Any] = dataclasses.field(default_factory=lambda: dict(DEFAULT_THEME))


# 按钮样式 -> (背景, 前景, 悬停背景)
_BUTTON_COLORS = {
    "primary": ("#4f6ef7", "#ffffff", "#3d5ae0"),
    "secondary": ("#6c757d", "#ffffff", "#5a6268"),
    "success": ("#2ecc71", "#ffffff", "#27ae60"),
    "danger": ("#e74c3c", "#ffffff", "#c0392b"),
    "ghost": ("#ffffff", "#2d3436", "#eef0f6"),
}

_LEVEL_COLORS = {
    "info": "#4f6ef7",
    "success": "#2ecc71",
    "warning": "#f39c12",
    "error": "#e74c3c",
}


def render_app(app: App, callbacks: Optional[Dict[str, EventCallback]] = None) -> "AppWindow":
    """创建窗口并进入事件循环（阻塞）。"""
    window = AppWindow(app, callbacks)
    window.root.mainloop()
    return window


EventCallback = Callable[[Any], None]


class AppWindow:
    """窗口 + 递归渲染器。"""

    def __init__(self, app: App, callbacks: Optional[Dict[str, EventCallback]] = None) -> None:
        self.app = app
        self.cbs = Callbacks(callbacks)
        self.theme = app.theme

        self.root = tk.Tk()
        self.root.title(app.title)
        self.root.geometry(f"{app.width}x{app.height}")
        self.root.minsize(320, 200)
        self.root.configure(bg=self.theme["bg"])
        self._configure_styles()

        if app.on_close:
            self.cbs.register(app.on_close, self.cbs.get(app.on_close) or (lambda _: None))
            self.root.protocol("WM_DELETE_WINDOW",
                               lambda: (self.cbs.call(app.on_close), self.root.destroy()))
        else:
            self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)

        self._body = tk.Frame(self.root, bg=self.theme["bg"])
        self._body.pack(fill="both", expand=True, padx=16, pady=14)

        # 子组件记录的输入框 / 多行文本区引用
        self._inputs: Dict[str, tk.Widget] = {}
        self.text_areas: Dict[str, tk.Text] = {}

        for child in app.children:
            self._render(self._body, child)

    # ---------- 样式 ----------

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "awtf.Treeview",
            background=self.theme["bg_card"],
            foreground=self.theme["text"],
            fieldbackground=self.theme["bg_card"],
            rowheight=24,
            bordercolor=self.theme["border"],
        )
        style.configure(
            "awtf.Treeview.Heading",
            background=self.theme["border"],
            foreground=self.theme["text"],
            font=(self.theme["font_family"][0], self.theme["font_size_small"], "bold"),
        )

    # ---------- 渲染 ----------

    def _render(self, parent: tk.Widget, comp: Component) -> None:
        if isinstance(comp, RowSpec):
            self._render_row(parent, comp)
        elif isinstance(comp, CardSpec):
            self._render_card(parent, comp)
        elif isinstance(comp, LabelSpec):
            self._render_label(parent, comp)
        elif isinstance(comp, ButtonSpec):
            self._render_button(parent, comp)
        elif isinstance(comp, IconSpec):
            self._render_icon(parent, comp)
        elif isinstance(comp, InputSpec):
            self._render_input(parent, comp)
        elif isinstance(comp, TextAreaSpec):
            self._render_textarea(parent, comp)
        elif isinstance(comp, ListSpec):
            self._render_list(parent, comp)
        elif isinstance(comp, TableSpec):
            self._render_table(parent, comp)
        elif isinstance(comp, DividerSpec):
            self._render_divider(parent, comp)
        elif isinstance(comp, Spinner):
            self._render_spinner(parent, comp)
        elif isinstance(comp, ProgressBar):
            self._render_progress(parent, comp)
        else:
            raise TypeError(f"未知组件: {type(comp).__name__}")

    def _render_row(self, parent: tk.Widget, spec: RowSpec) -> None:
        frame = tk.Frame(parent, bg=self.theme["bg"])
        frame.pack(fill="x", pady=(0, self.theme["spacing"]))
        for child in spec.children:
            sub = tk.Frame(frame, bg=self.theme["bg"])
            sub.pack(side="left", padx=(0, spec.spacing))
            self._render(sub, child)

    def _render_card(self, parent: tk.Widget, spec: CardSpec) -> None:
        card = tk.Frame(
            parent,
            bg=self.theme["bg_card"],
            highlightbackground=self.theme["border"] if spec.border else self.theme["bg_card"],
            highlightthickness=1,
        )
        card.pack(fill="x", pady=(0, self.theme["spacing"]))
        body = tk.Frame(card, bg=self.theme["bg_card"])
        body.pack(fill="x", padx=spec.padding, pady=spec.padding)
        if spec.title:
            tk.Label(
                body, text=spec.title,
                bg=self.theme["bg_card"], fg=self.theme["text"],
                font=(self.theme["font_family"][0], self.theme["font_size"], "bold"),
            ).pack(anchor="w", pady=(0, 6))
        for child in spec.children:
            self._render(body, child)

    def _render_label(self, parent: tk.Widget, spec: LabelSpec) -> None:
        tk.Label(
            parent,
            text=spec.text,
            bg=parent["bg"],
            fg=spec.color or self.theme["text_secondary"],
            font=(self.theme["font_family"][0],
                  spec.size or self.theme["font_size_small"],
                  "bold" if spec.bold else "normal"),
            anchor={"left": "w", "center": "center", "right": "e"}[spec.align],
            justify="left",
            wraplength=480 if spec.wrap else 0,
        ).pack(fill="x", pady=(0, 4))

    def _render_icon(self, parent: tk.Widget, spec: IconSpec) -> None:
        tk.Label(
            parent, text=spec.icon,
            bg=parent["bg"], fg=spec.color or self.theme["text"],
            font=(self.theme["font_family"][0], spec.size),
        ).pack(pady=(0, 4))

    def _render_button(self, parent: tk.Widget, spec: ButtonSpec) -> None:
        bg, fg, hover = _BUTTON_COLORS[spec.style]
        if spec.disabled:
            bg, fg = self.theme["disabled_bg"], self.theme["disabled_text"]
        btn = tk.Button(
            parent,
            text=(f"{spec.icon} {spec.text}" if spec.icon else spec.text),
            bg=bg, fg=fg, activebackground=hover, activeforeground=fg,
            relief="flat", bd=0, cursor="hand2",
            font=(self.theme["font_family"][0], self.theme["font_size"]),
            padx=18 if spec.size == "medium" else (10 if spec.size == "small" else 28),
            pady=4,
            state="disabled" if spec.disabled else "normal",
            command=lambda s=spec: self.cbs.call(s.on_click) if s.on_click else None,
        )
        if spec.tooltip and not spec.disabled:
            btn.bind("<Enter>", lambda e: self._show_tooltip(btn, spec.tooltip))
            btn.bind("<Leave>", lambda e: self._hide_tooltip(btn))
        btn.pack(anchor="w", pady=(0, self.theme["spacing"]))

    # ---------- 输入 ----------

    def _render_input(self, parent: tk.Widget, spec: InputSpec) -> None:
        field = spec.field
        wrap = tk.Frame(parent, bg=parent["bg"])
        wrap.pack(fill="x", pady=(0, self.theme["spacing"]))

        if field.label:
            tk.Label(
                wrap, text=field.label,
                bg=wrap["bg"], fg=self.theme["text"],
                font=(self.theme["font_family"][0], self.theme["font_size_small"], "bold"),
            ).pack(anchor="w")

        entry = tk.Entry(
            wrap,
            bg=self.theme["bg_card"], fg=self.theme["text"],
            insertbackground=self.theme["text"],
            relief="solid", bd=1, highlightthickness=1,
            highlightbackground=self.theme["border"],
            highlightcolor=self.theme["focus"],
            font=(self.theme["font_family"][0], self.theme["font_size"]),
            show="*" if field.kind == "password" else "",
        )
        if field.default is not None:
            entry.insert(0, field.format_display(field.default))
        if field.placeholder:
            _apply_placeholder(entry, field.placeholder, self.theme)
        entry.pack(fill="x", ipady=4)

        self._inputs[field.name] = entry

        if field.hint:
            tk.Label(
                wrap, text=field.hint,
                bg=wrap["bg"], fg=self.theme["text_secondary"],
                font=(self.theme["font_family"][0], self.theme["font_size_small"]),
            ).pack(anchor="w")

        if spec.on_submit:
            entry.bind("<Return>", lambda e, s=spec: self._submit_input(s))
        if spec.on_change:
            entry.bind("<KeyRelease>", lambda e, s=spec: self._change_input(s))

    def _render_textarea(self, parent: tk.Widget, spec: TextAreaSpec) -> None:
        wrap = tk.Frame(parent, bg=parent["bg"])
        wrap.pack(fill="both", expand=True, pady=(0, self.theme["spacing"]))

        scroll = tk.Scrollbar(wrap)
        scroll.pack(side="right", fill="y")

        text = tk.Text(
            wrap,
            height=spec.height,
            yscrollcommand=scroll.set,
            bg=self.theme["bg_card"], fg=self.theme["text"],
            insertbackground=self.theme["text"],
            relief="solid", bd=1, highlightthickness=1,
            highlightbackground=self.theme["border"],
            highlightcolor=self.theme["focus"],
            font=("Microsoft YaHei", self.theme["font_size_small"]),
            state="normal",  # 先可编辑以便写入初始文本，之后按需锁定
            wrap="word",
        )
        scroll.config(command=text.yview)
        if spec.text:
            text.insert("1.0", spec.text)
        if spec.readonly:
            text.configure(state="disabled")
        text.pack(side="left", fill="both", expand=True)

        self.text_areas[spec.name] = text

        if not spec.readonly and spec.on_change:
            def _on_change(_e=None, t=text, s=spec):
                self.cbs.call(s.on_change, {"text": t.get("1.0", "end-1c")})
            text.bind("<KeyRelease>", _on_change)

    def append_text(self, name: str, chunk: str) -> None:
        """向多行文本区追加文本并自动滚动到底部（主线程安全）。"""
        text = self.text_areas.get(name)
        if text is None:
            return
        text.configure(state="normal")
        text.insert("end", chunk)
        text.configure(state="disabled")
        text.see("end")

    def _submit_input(self, spec: InputSpec) -> None:
        value = self._inputs[spec.name].get()
        self.cbs.call(spec.on_submit, {spec.name: value})

    def _change_input(self, spec: InputSpec) -> None:
        value = self._inputs[spec.name].get()
        self.cbs.call(spec.on_change, {spec.name: value})

    def get_values(self) -> Dict[str, Any]:
        """收集所有输入框当前值。"""
        return {name: widget.get() for name, widget in self._inputs.items()}

    # ---------- 列表 / 表格 ----------

    def _render_list(self, parent: tk.Widget, spec: ListSpec) -> None:
        frame = tk.Frame(parent, bg=parent["bg"])
        frame.pack(fill="x", pady=(0, self.theme["spacing"]))

        scroll = tk.Scrollbar(frame)
        scroll.pack(side="right", fill="y")

        listbox = tk.Listbox(
            frame,
            height=spec.height,
            selectmode="multiple" if spec.multi_select else "single",
            yscrollcommand=scroll.set,
            bg=self.theme["bg_card"], fg=self.theme["text"],
            selectbackground=self.theme["primary"], selectforeground="#ffffff",
            relief="solid", bd=1, highlightthickness=0,
            font=(self.theme["font_family"][0], self.theme["font_size_small"]),
        )
        scroll.config(command=listbox.yview)
        for item in spec.items:
            listbox.insert("end", item)
        for idx in spec.selected:
            listbox.selection_set(idx)

        if spec.on_select:
            def _on_select(_e=None, lb=listbox, s=spec):
                indices = list(lb.curselection())
                self.cbs.call(s.on_select, indices)
            listbox.bind("<<ListboxSelect>>", _on_select)

        listbox.pack(fill="x")

    def _render_table(self, parent: tk.Widget, spec: TableSpec) -> None:
        frame = tk.Frame(parent, bg=parent["bg"])
        frame.pack(fill="x", pady=(0, self.theme["spacing"]))

        scroll_y = tk.Scrollbar(frame, orient="vertical")
        scroll_x = tk.Scrollbar(frame, orient="horizontal")
        tree = ttk.Treeview(
            frame,
            columns=list(range(len(spec.columns))),
            show="headings",
            height=spec.height,
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            style="awtf.Treeview",
        )
        for i, col in enumerate(spec.columns):
            tree.heading(i, text=col)
            tree.column(i, width=120, anchor="w")
        for row in spec.rows:
            tree.insert("", "end", values=[str(v) if v is not None else "" for v in row])

        if spec.selectable and spec.on_select:
            def _on_select(_e=None, t=tree, s=spec):
                sel = t.selection()
                if not sel:
                    return
                index = t.index(sel[0])
                self.cbs.call(s.on_select, s.row_dict(index))
            tree.bind("<<TreeviewSelect>>", _on_select)

        scroll_y.config(command=tree.yview)
        scroll_x.config(command=tree.xview)
        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        tree.pack(fill="x")

    def _render_divider(self, parent: tk.Widget, spec: DividerSpec) -> None:
        tk.Frame(
            parent, bg=self.theme["border"], height=spec.thickness,
        ).pack(fill="x", pady=(0, self.theme["spacing"]))

    # ---------- 反馈 ----------

    def _render_spinner(self, parent: tk.Widget, spec: Spinner) -> None:
        wrap = tk.Frame(parent, bg=parent["bg"])
        wrap.pack(pady=(0, self.theme["spacing"]))
        canvas = tk.Canvas(
            wrap, width=spec.size + 8, height=spec.size + 8,
            bg=parent["bg"], highlightthickness=0,
        )
        canvas.pack(side="left")
        if spec.text:
            tk.Label(
                wrap, text=spec.text, bg=wrap["bg"], fg=self.theme["text_secondary"],
                font=(self.theme["font_family"][0], self.theme["font_size_small"]),
            ).pack(side="left", padx=(8, 0))

        start = 0
        extents = self.theme.get("spinner_extents", 60)
        step = 18

        def _spin():
            nonlocal start
            start = (start + step) % 360
            canvas.delete("all")
            canvas.create_arc(
                4, 4, spec.size + 4, spec.size + 4,
                start=start, extent=extents,
                style="arc", outline=spec.color, width=3,
            )
            canvas.after(80, _spin)

        _spin()

    def _render_progress(self, parent: tk.Widget, spec: ProgressBar) -> None:
        wrap = tk.Frame(parent, bg=parent["bg"])
        wrap.pack(pady=(0, self.theme["spacing"]))
        canvas = tk.Canvas(
            wrap, width=spec.width, height=spec.height + 4,
            bg=parent["bg"], highlightthickness=0,
        )
        canvas.pack(side="left")
        text_var = tk.StringVar()
        label = tk.Label(
            wrap, textvariable=text_var, bg=wrap["bg"], fg=self.theme["text_secondary"],
            font=(self.theme["font_family"][0], self.theme["font_size_small"]),
        )
        if spec.show_text:
            label.pack(side="left", padx=(8, 0))

        def _redraw(value: Optional[float]):
            canvas.delete("all")
            canvas.create_rectangle(
                0, 2, spec.width, spec.height + 2,
                fill=self.theme["bg_card"], outline=self.theme["border"],
            )
            if value is None:
                # 不确定进度：往返滚动条
                return
            fill_w = max(2, int(spec.width * value / 100.0))
            canvas.create_rectangle(
                0, 2, fill_w, spec.height + 2,
                fill=spec.color, outline="",
            )
            text_var.set(f"{value:.0f}%")

        _redraw(spec.value)

        if spec.value is None:
            pos = [0]
            bar_len = max(30, int(spec.width * 0.3))

            def _marquee():
                pos[0] = (pos[0] + 6) % (spec.width + bar_len)
                x0 = pos[0] - bar_len
                canvas.delete("track")
                canvas.create_rectangle(
                    x0, 2, x0 + bar_len, spec.height + 2,
                    fill=spec.color, outline="", tags="track",
                )
                canvas.after(40, _marquee)

            _marquee()

    # ---------- 提示 ----------

    def _show_tooltip(self, widget: tk.Widget, text: str) -> None:
        self._tip = tk.Toplevel(self.root)
        self._tip.overrideredirect(True)
        self._tip.attributes("-topmost", True)
        tk.Label(
            self._tip, text=text, bg="#2d3436", fg="#ffffff",
            font=(self.theme["font_family"][0], self.theme["font_size_small"]),
            padx=8, pady=4,
        ).pack()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() - 28
        self._tip.wm_geometry(f"+{x}+{y}")

    def _hide_tooltip(self, _widget) -> None:
        tip = getattr(self, "_tip", None)
        if tip is not None:
            tip.destroy()
            self._tip = None


# ============================================================
# 占位提示
# ============================================================

def _apply_placeholder(entry: tk.Entry, placeholder: str, theme: Dict[str, Any]) -> None:
    """用灰色占位文本模拟 placeholder（tk.Entry 无原生支持）。"""
    holder_color = theme["text_secondary"]
    normal_color = theme["text"]
    entry.insert(0, placeholder)
    entry.config(fg=holder_color)
    entry._placeholder = placeholder  # type: ignore[attr-defined]

    def _on_focus_in(_e):
        if entry.get() == placeholder:
            entry.delete(0, "end")
            entry.config(fg=normal_color)

    def _on_focus_out(_e):
        if not entry.get():
            entry.insert(0, placeholder)
            entry.config(fg=holder_color)

    entry.bind("<FocusIn>", _on_focus_in)
    entry.bind("<FocusOut>", _on_focus_out)


# ============================================================
# 对话框（模态）
# ============================================================

def show_confirm(parent: Optional[tk.Misc], dialog: ConfirmDialog) -> bool:
    """模态确认框，返回用户是否确认。"""
    result = {"ok": False}
    top = _make_toplevel(parent, dialog.title)
    body = _dialog_body(top)

    tk.Label(
        body, text=dialog.message, bg=body["bg"], fg=top.theme["text"],
        font=(top.theme["font_family"][0], top.theme["font_size"]),
        wraplength=360, justify="left",
    ).pack(pady=(6, 14))

    row = tk.Frame(body, bg=body["bg"])
    row.pack()
    color = top.theme["danger"] if dialog.danger else top.theme["primary"]
    tk.Button(
        row, text=dialog.confirm_text, bg=color, fg="#ffffff",
        activebackground=color, relief="flat", padx=18, pady=4,
        command=lambda: (_set(result, True), top.destroy()),
    ).pack(side="left", padx=6)
    tk.Button(
        row, text=dialog.cancel_text, bg=top.theme["border"], fg=top.theme["text"],
        activebackground=top.theme["border"], relief="flat", padx=18, pady=4,
        command=top.destroy,
    ).pack(side="left", padx=6)

    _center_and_wait(top)
    return result["ok"]


def show_message(parent: Optional[tk.Misc], dialog: MessageDialog) -> None:
    """模态提示框。"""
    top = _make_toplevel(parent, dialog.title)
    body = _dialog_body(top)
    color = _LEVEL_COLORS[dialog.level]

    tk.Label(
        body, text="✓" if dialog.level == "success"
        else ("!" if dialog.level == "warning" else "i"),
        bg=body["bg"], fg=color,
        font=(top.theme["font_family"][0], 28, "bold"),
    ).pack(pady=(6, 4))
    tk.Label(
        body, text=dialog.message, bg=body["bg"], fg=top.theme["text"],
        font=(top.theme["font_family"][0], top.theme["font_size"]),
        wraplength=360, justify="left",
    ).pack(pady=(4, 14))
    tk.Button(
        body, text=dialog.button_text, bg=color, fg="#ffffff",
        activebackground=color, relief="flat", padx=18, pady=4,
        command=top.destroy,
    ).pack()

    _center_and_wait(top)


def show_input(parent: Optional[tk.Misc], dialog: InputDialog) -> Optional[Dict[str, Any]]:
    """模态输入对话框：多字段 + 验证 + 逐字段错误提示。

    Returns:
        确认返回 {字段名: 值}；取消/关闭返回 None。
    """
    result = {"value": None}
    top = _make_toplevel(parent, dialog.title)
    body = _dialog_body(top)

    if dialog.message:
        tk.Label(
            body, text=dialog.message, bg=body["bg"], fg=top.theme["text"],
            font=(top.theme["font_family"][0], top.theme["font_size"]),
            wraplength=380, justify="left",
        ).pack(pady=(4, 10))

    entries: Dict[str, tk.Entry] = {}
    error_labels: Dict[str, tk.Label] = {}
    error_vars: Dict[str, tk.StringVar] = {}

    for field in dialog.fields:
        wrap = tk.Frame(body, bg=body["bg"])
        wrap.pack(fill="x", pady=(0, 8))
        tk.Label(
            wrap, text=field.label, bg=wrap["bg"], fg=top.theme["text"],
            font=(top.theme["font_family"][0], top.theme["font_size_small"], "bold"),
        ).pack(anchor="w")
        entry = tk.Entry(
            wrap,
            bg=top.theme["bg_card"], fg=top.theme["text"],
            insertbackground=top.theme["text"],
            relief="solid", bd=1, highlightthickness=1,
            highlightbackground=top.theme["border"], highlightcolor=top.theme["focus"],
            font=(top.theme["font_family"][0], top.theme["font_size"]),
            show="*" if field.kind == "password" else "",
        )
        if field.default is not None:
            entry.insert(0, field.format_display(field.default))
        entry.pack(fill="x", ipady=4)
        entries[field.name] = entry

        var = tk.StringVar()
        error_vars[field.name] = var
        err = tk.Label(
            wrap, textvariable=var, bg=wrap["bg"], fg=top.theme["error_text"],
            font=(top.theme["font_family"][0], top.theme["font_size_small"]),
            anchor="w", justify="left",
        )
        err.pack(anchor="w")
        error_labels[field.name] = err
        var.set("")

    def _submit():
        raw = {name: e.get() for name, e in entries.items()}
        ok, cleaned, errors = dialog.validate(raw)
        if ok:
            result["value"] = cleaned
            top.destroy()
            return
        for name, var in error_vars.items():
            var.set(errors.get(name, ""))

    for field in dialog.fields:
        if field.kind == "password":
            entries[field.name].bind("<Return>", lambda _e: _submit())

    row = tk.Frame(body, bg=body["bg"])
    row.pack(pady=(10, 0))
    tk.Button(
        row, text=dialog.confirm_text, bg=top.theme["primary"], fg="#ffffff",
        activebackground=top.theme["primary_hover"], relief="flat", padx=18, pady=4,
        command=_submit,
    ).pack(side="left", padx=6)
    tk.Button(
        row, text=dialog.cancel_text, bg=top.theme["border"], fg=top.theme["text"],
        activebackground=top.theme["border"], relief="flat", padx=18, pady=4,
        command=top.destroy,
    ).pack(side="left", padx=6)

    _center_and_wait(top)
    return result["value"]


def show_toast(parent: Optional[tk.Misc], toast: Toast) -> None:
    """右下角自动消失的消息提示。"""
    base = parent if isinstance(parent, tk.Misc) else None
    root = base.winfo_toplevel() if base is not None else tk._default_root  # type: ignore[attr-defined]
    if root is None:  # pragma: no cover
        return
    top = tk.Toplevel(root)
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    color = _LEVEL_COLORS[toast.level]
    tk.Label(
        top, text=toast.message, bg="#2d3436", fg=color,
        font=("Microsoft YaHei", 11),
        padx=14, pady=8,
    ).pack()
    top.update_idletasks()
    x = root.winfo_screenwidth() - top.winfo_width() - 20
    y = root.winfo_screenheight() - top.winfo_height() - 60
    top.wm_geometry(f"+{x}+{y}")
    top.after(toast.duration_ms, top.destroy)


# ============================================================
# 对话框工具
# ============================================================

def _make_toplevel(parent: Optional[tk.Misc], title: str) -> tk.Toplevel:
    root = parent if isinstance(parent, tk.Tk) else (parent.winfo_toplevel() if parent else None)
    top = tk.Toplevel(root)
    top.title(title)
    top.configure(bg=DEFAULT_THEME["bg"])
    top.resizable(False, False)
    top.transient(root)
    top.grab_set()
    top.theme = DEFAULT_THEME  # type: ignore[attr-defined]
    return top


def _dialog_body(top: tk.Toplevel) -> tk.Frame:
    body = tk.Frame(top, bg=top.theme["bg"], padx=20, pady=16)  # type: ignore[attr-defined]
    body.pack()
    return body


def _set(d: Dict[str, Any], key: str, value: Any) -> None:
    d[key] = value


def _center_and_wait(top: tk.Toplevel) -> None:
    top.update_idletasks()
    w = top.winfo_reqwidth()
    h = top.winfo_reqheight()
    sw = top.winfo_screenwidth()
    sh = top.winfo_screenheight()
    top.geometry(f"+{(sw - w) // 2}+{(sh - h) // 2}")
    top.wait_window()

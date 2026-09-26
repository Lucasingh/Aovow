"""
工具设计器 —— 通用运行器基类

由「工具设计器」生成的工具继承本类：
- 无 `ui_layout` 时：按 AWTF @tool 的参数元数据自动渲染输入表单（默认界面）
- 有 `ui_layout` 时：按用户自定义的界面布局渲染（标题/说明/分组/输入控件/按钮/结果区）

`render_layout(owner, layout)` 是「设计器实时预览」与「生成工具运行时」共用的渲染函数。
"""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import Qt, QDate, QUrl
from PySide6.QtGui import QColor, QPixmap, QDesktopServices
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QTextBrowser,
    QScrollArea, QComboBox, QPlainTextEdit, QFrame, QSlider, QRadioButton,
    QDateEdit, QProgressBar, QColorDialog, QFileDialog,
)

from awtf import ToolContext

from workstation.tools.base_tool import BaseTool
from workstation.ui.styles import COLORS

_BTN = (f"QPushButton{{background:{COLORS['accent']};color:#fff;border:none;"
        f"border-radius:8px;padding:8px 20px;font-weight:600;}}"
        f"QPushButton:disabled{{background:{COLORS['border']};}}")

_ALIGN_MAP = {
    "left": Qt.AlignmentFlag.AlignLeft,
    "center": Qt.AlignmentFlag.AlignCenter,
    "right": Qt.AlignmentFlag.AlignRight,
}

_FIELD_STYLE = (
    f"QLineEdit,QSpinBox,QDoubleSpinBox,QPlainTextEdit{{background:"
    f"{COLORS['bg_secondary']};color:{COLORS['fg_primary']};"
    f"border:1px solid {COLORS['border']};border-radius:6px;padding:4px 8px;}}"
    f"QComboBox{{background:{COLORS['bg_secondary']};color:{COLORS['fg_primary']};"
    f"border:1px solid {COLORS['border']};border-radius:6px;padding:4px 8px;}}"
)


def _btn_qss(accent: str) -> str:
    """按主题色生成运行按钮样式。"""
    return (f"QPushButton{{background:{accent};color:#fff;border:none;"
            f"border-radius:8px;padding:8px 20px;font-weight:600;}}"
            f"QPushButton:hover{{background:{COLORS['accent_hover']};}}"
            f"QPushButton:pressed{{background:{COLORS['accent_pressed']};}}"
            f"QPushButton:disabled{{background:{COLORS['border']};}}")


def _accent_of(layout: dict | None) -> str:
    token = ((layout or {}).get("theme") or {}).get("accent") or "accent"
    return COLORS.get(token, COLORS["accent"])


def _split_options(text: str) -> list:
    return [s.strip() for s in (text or "").split(",") if s.strip()]


class _RadioGroup(QWidget):
    """单选组：options 逐项生成 QRadioButton，value() 返回选中项。"""

    def __init__(self, options: list, checked: str = "", parent=None):
        super().__init__(parent)
        self.radios: list[QRadioButton] = []
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        for o in options or [checked or "选项"]:
            rb = QRadioButton(o)
            rb.setChecked(o == checked)
            rb.setStyleSheet(f"color:{COLORS['fg_primary']};")
            self.radios.append(rb)
            v.addWidget(rb)
        v.addStretch(1)

    def value(self) -> str:
        for rb in self.radios:
            if rb.isChecked():
                return rb.text()
        return self.radios[0].text() if self.radios else ""


class _ColorEdit(QWidget):
    """颜色选择：色块预览 + 输入框 + 🎨 取色按钮（系统颜色对话框）。"""

    def __init__(self, default: str = "", parent=None):
        super().__init__(parent)
        self._edit = QLineEdit(default or "#5c6ff0")
        self._edit.setStyleSheet(_FIELD_STYLE)
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        self._swatch = QLabel()
        self._swatch.setFixedSize(26, 22)
        self._swatch.setStyleSheet(
            f"background:{default or '#5c6ff0'};border:1px solid {COLORS['border']};"
            f"border-radius:5px;")
        h.addWidget(self._swatch)
        h.addWidget(self._edit, 1)
        btn = QPushButton("🎨")
        btn.setFixedWidth(30)
        btn.setToolTip("打开颜色选择器")
        btn.setStyleSheet(_FIELD_STYLE)
        btn.clicked.connect(self._pick)
        h.addWidget(btn)
        self._edit.textChanged.connect(self._sync)

    def _sync(self, text: str):
        self._swatch.setStyleSheet(
            f"background:{text or '#5c6ff0'};border:1px solid {COLORS['border']};"
            f"border-radius:5px;")

    def _pick(self):
        color = QColorDialog.getColor(
            QColor(self._edit.text() or "#5c6ff0"), self, "选择颜色")
        if color.isValid():
            self._edit.setText(color.name())

    def text(self) -> str:
        return self._edit.text()


class _FileEdit(QWidget):
    """文件选择：输入框 + 📂 浏览按钮（保存到参数为本地文件路径字符串）。"""

    def __init__(self, default: str = "", parent=None):
        super().__init__(parent)
        self._edit = QLineEdit(default or "")
        self._edit.setStyleSheet(_FIELD_STYLE)
        self._edit.setPlaceholderText("点击 📂 选择文件，或直接输入路径")
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(4)
        h.addWidget(self._edit, 1)
        btn = QPushButton("📂")
        btn.setFixedWidth(30)
        btn.setToolTip("选择文件")
        btn.setStyleSheet(_FIELD_STYLE)
        btn.clicked.connect(self._browse)
        h.addWidget(btn)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件")
        if path:
            self._edit.setText(path)

    def path(self) -> str:
        return self._edit.text()


def _make_widget(p, widget: str = "input", options: str = ""):
    """按控件渲染类型生成输入控件（ui_layout 的 param 控件用）。

    widget: input(单行) / textarea(多行) / select(下拉)
    """
    t = getattr(p, "type_name", "str")
    if widget == "textarea":
        box = QPlainTextEdit()
        box.setMinimumHeight(72)
        box.setStyleSheet(_FIELD_STYLE)
        if isinstance(p.default, str):
            box.setPlainText(p.default)
        box.setPlaceholderText(getattr(p, "description", "") or p.name)
        return box
    if widget == "select":
        combo = QComboBox()
        combo.addItems(_split_options(options) or [str(getattr(p, "default", "") or "")])
        if isinstance(p.default, str) and p.default:
            combo.setCurrentText(p.default)
        combo.setStyleSheet(_FIELD_STYLE)
        return combo
    if widget == "slider":
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 100)
        if isinstance(p.default, (int, float)):
            slider.setValue(int(p.default))
        slider.setStyleSheet(_FIELD_STYLE)
        return slider
    if widget == "password":
        edit = QLineEdit()
        if isinstance(p.default, str):
            edit.setText(p.default)
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(getattr(p, "description", "") or p.name)
        edit.setStyleSheet(_FIELD_STYLE)
        return edit
    if widget == "radio":
        return _RadioGroup(_split_options(options),
                           str(getattr(p, "default", "") or ""))
    if widget == "checkbox":
        box = QCheckBox()
        box.setChecked(bool(p.default))
        box.setStyleSheet(f"color:{COLORS['fg_secondary']};")
        return box
    if widget == "date":
        de = QDateEdit()
        de.setCalendarPopup(True)
        de.setDisplayFormat("yyyy-MM-dd")
        if isinstance(p.default, str) and p.default:
            d = QDate.fromString(p.default, "yyyy-MM-dd")
            if d.isValid():
                de.setDate(d)
        de.setStyleSheet(_FIELD_STYLE)
        return de
    if widget == "color":
        return _ColorEdit(str(getattr(p, "default", "") or ""))
    if widget == "file":
        return _FileEdit(str(getattr(p, "default", "") or ""))
    if t == "int":
        box = QSpinBox()
        box.setRange(-2 ** 31, 2 ** 31 - 1)
        if isinstance(p.default, int):
            box.setValue(p.default)
        box.setStyleSheet(_FIELD_STYLE)
        return box
    if t == "float":
        box = QDoubleSpinBox()
        box.setRange(-1e9, 1e9)
        if isinstance(p.default, float):
            box.setValue(p.default)
        box.setStyleSheet(_FIELD_STYLE)
        return box
    if t == "bool":
        box = QCheckBox()
        box.setChecked(bool(p.default))
        box.setStyleSheet(f"color:{COLORS['fg_secondary']};")
        return box
    edit = QLineEdit()
    if isinstance(p.default, str):
        edit.setText(p.default)
    edit.setPlaceholderText(getattr(p, "description", "") or p.name)
    edit.setStyleSheet(_FIELD_STYLE)
    return edit


# ============================================================
# ui_layout 渲染器（预览与运行时共用）
# ============================================================

def _render_header(owner, c: dict, accent: str):
    text = c.get("text") or f"{getattr(owner, 'icon', '🧩')} {owner.name}"
    subtitle = c.get("subtitle") or getattr(owner, "description", "")
    wrap = QWidget()
    v = QVBoxLayout(wrap)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(4)
    title = QLabel(text)
    title.setStyleSheet(f"font-size:18px;font-weight:700;"
                        f"color:{COLORS['fg_primary']};"
                        f"background:transparent;border:none;")
    v.addWidget(title)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{COLORS['fg_tertiary']};"
                          f"background:transparent;border:none;font-size:12px;")
        v.addWidget(sub)
    return wrap, None


def _render_text(owner, c: dict, accent: str):
    lab = QLabel(c.get("text", ""))
    lab.setWordWrap(True)
    lab.setAlignment(_ALIGN_MAP.get(c.get("align", "left"),
                                    Qt.AlignmentFlag.AlignLeft))
    lab.setStyleSheet(f"color:{COLORS['fg_secondary']};"
                      f"background:transparent;border:none;font-size:13px;")
    return lab, None


def _render_separator(owner, c: dict, accent: str):
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"QFrame{{background:{COLORS['border']};"
                       f"border:none;max-height:1px;}}")
    return line, None


def _render_group(owner, c: dict, accent: str):
    lab = QLabel(c.get("title", "分组"))
    lab.setStyleSheet(f"color:{COLORS['fg_secondary']};"
                      f"background:transparent;border:none;"
                      f"font-size:12px;font-weight:600;margin-top:4px;")
    return lab, None


def _render_param(owner, c: dict, accent: str):
    name = c.get("param", "")
    p = owner._get_param(name)
    if p is None:
        return None, None
    widget = owner._make_widget(p, c.get("widget", "input"), c.get("options", ""))
    owner._inputs[name] = widget
    label = QLabel(c.get("label") or p.name)
    label.setStyleSheet(f"color:{COLORS['fg_secondary']};"
                        f"background:transparent;border:none;font-size:13px;")
    label.setToolTip(getattr(p, "description", "") or "")
    row = QHBoxLayout()
    row.addWidget(label)
    row.addWidget(widget, 1)
    return None, row


def _render_actions(owner, c: dict, accent: str):
    text = c.get("text") or "▶ 运行"
    btn = QPushButton(text)
    btn.setStyleSheet(_btn_qss(accent))
    btn.clicked.connect(owner._run)
    owner._run_btn = btn
    owner._run_text = text
    align = c.get("align", "right")
    row = QHBoxLayout()
    if align == "left":
        row.addWidget(btn)
        row.addStretch(1)
    elif align == "center":
        row.addStretch(1)
        row.addWidget(btn)
        row.addStretch(1)
    else:
        row.addStretch(1)
        row.addWidget(btn)
    return None, row


def _render_result(owner, c: dict, accent: str):
    out = QTextBrowser()
    if c.get("style") == "chat":
        qss = (f"QTextBrowser{{background:{COLORS['bg_primary']};"
               f"color:{COLORS['fg_primary']};border:1px solid {accent};"
               f"border-radius:12px;font-size:13px;padding:12px;}}")
    else:
        qss = (f"QTextBrowser{{background:{COLORS['bg_secondary']};"
               f"color:{COLORS['fg_primary']};border:1px solid {COLORS['border']};"
               f"border-radius:10px;font-size:13px;padding:10px;}}")
    out.setStyleSheet(qss)
    out.setPlaceholderText(c.get("placeholder") or "运行结果将显示在这里…")
    owner._out = out
    return out, None


# ============================================================
# 展示 / 操作 / 输出类控件渲染器（v5 扩展）
# ============================================================

def _render_quote(owner, c: dict, accent: str):
    lab = QLabel(c.get("text") or "引用内容")
    lab.setWordWrap(True)
    lab.setStyleSheet(f"background:{COLORS['bg_tertiary']};"
                      f"color:{COLORS['fg_secondary']};"
                      f"border-left:3px solid {accent};border-radius:6px;"
                      f"padding:8px 10px;font-size:13px;")
    return lab, None


def _render_spacer(owner, c: dict, accent: str):
    w = QWidget()
    try:
        w.setMinimumHeight(max(4, int(c.get("h", 16))))
    except (TypeError, ValueError):
        w.setMinimumHeight(16)
    return w, None


def _render_badge(owner, c: dict, accent: str):
    color = COLORS.get(c.get("color") or "accent", accent)
    lab = QLabel(c.get("text") or "徽章")
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setStyleSheet(f"background:{color};color:#fff;border-radius:11px;"
                      f"padding:2px 12px;font-size:12px;font-weight:600;")
    return lab, None


_TIP_ICONS = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "🚫"}


def _render_tip(owner, c: dict, accent: str):
    kind = c.get("kind") or "info"
    color = COLORS.get(kind, COLORS["info"])
    lab = QLabel(f"{_TIP_ICONS.get(kind, '')} {c.get('text', '')}")
    lab.setWordWrap(True)
    lab.setStyleSheet(f"background:{color}22;color:{color};"
                      f"border:1px solid {color}55;border-radius:8px;"
                      f"padding:6px 10px;font-size:12px;")
    return lab, None


def _render_image(owner, c: dict, accent: str):
    lab = QLabel()
    src = (c.get("src") or "").strip()
    text = c.get("text") or "图片占位"
    if src:
        pm = QPixmap(src)
        if not pm.isNull():
            try:
                w = int(c.get("w") or 0) or pm.width()
                h = int(c.get("h") or 0) or pm.height()
                lab.setPixmap(pm.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
            except (TypeError, ValueError):
                lab.setPixmap(pm)
        else:
            lab.setText(f"🖼 {text}\n（未找到图片：{src}）")
    else:
        lab.setText(f"🖼 {text}")
    lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lab.setWordWrap(True)
    lab.setStyleSheet(f"color:{COLORS['fg_tertiary']};"
                      f"background:{COLORS['bg_secondary']};"
                      f"border:1px dashed {COLORS['border']};border-radius:10px;"
                      f"font-size:12px;")
    return lab, None


def _render_link(owner, c: dict, accent: str):
    url = (c.get("url") or "#").strip()
    text = c.get("text") or url
    lab = QLabel(f'<a href="{url}" style="color:{accent};'
                 f'text-decoration:none;">🔗 {text}</a>')
    lab.setOpenExternalLinks(True)
    lab.setStyleSheet("background:transparent;border:none;")
    return lab, None


def _render_progress(owner, c: dict, accent: str):
    bar = QProgressBar()
    try:
        bar.setValue(max(0, min(100, int(c.get("value", 0)))))
    except (TypeError, ValueError):
        bar.setValue(0)
    bar.setFormat(c.get("text") or "%p%")
    bar.setStyleSheet(
        f"QProgressBar{{background:{COLORS['bg_tertiary']};"
        f"color:{COLORS['fg_primary']};border:none;border-radius:6px;"
        f"text-align:center;font-size:11px;}}"
        f"QProgressBar::chunk{{background:{accent};border-radius:6px;}}")
    return bar, None


def _render_stat(owner, c: dict, accent: str):
    card = QFrame()
    card.setStyleSheet(f"QFrame{{background:{COLORS['bg_secondary']};"
                       f"border:1px solid {COLORS['border']};border-radius:10px;}}")
    v = QVBoxLayout(card)
    v.setContentsMargins(10, 8, 10, 8)
    v.setSpacing(2)
    val = QLabel(c.get("value") or "0")
    val.setStyleSheet(f"color:{accent};font-size:22px;font-weight:700;"
                      f"background:transparent;border:none;")
    lab = QLabel(c.get("text") or "指标")
    lab.setStyleSheet(f"color:{COLORS['fg_tertiary']};font-size:11px;"
                      f"background:transparent;border:none;")
    v.addWidget(val)
    v.addWidget(lab)
    return card, None


def _render_button2(owner, c: dict, accent: str):
    btn = QPushButton(c.get("text") or "按钮")
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{accent};"
        f"border:1px solid {accent};border-radius:8px;padding:6px 16px;"
        f"font-weight:600;}}"
        f"QPushButton:hover{{background:{accent}1f;}}")
    if c.get("run") == "yes":
        btn.clicked.connect(owner._run)
    return btn, None


def _render_list_out(owner, c: dict, accent: str):
    out = QTextBrowser()
    out.setPlainText(c.get("text") or "— 列表输出示例 —\n• 项目一\n• 项目二\n• 项目三")
    out.setStyleSheet(
        f"QTextBrowser{{background:{COLORS['bg_secondary']};"
        f"color:{COLORS['fg_primary']};border:1px solid {COLORS['border']};"
        f"border-radius:10px;font-size:12px;padding:10px;}}")
    return out, None


def _render_table_out(owner, c: dict, accent: str):
    out = QTextBrowser()
    out.setHtml(
        "<table style='border-collapse:collapse;font-size:12px;'>"
        "<tr><th style='border:1px solid #444;padding:4px 8px;'>列 A</th>"
        "<th style='border:1px solid #444;padding:4px 8px;'>列 B</th></tr>"
        "<tr><td style='border:1px solid #444;padding:4px 8px;'>示例 1</td>"
        "<td style='border:1px solid #444;padding:4px 8px;'>示例 2</td></tr>"
        "</table>")
    out.setStyleSheet(
        f"QTextBrowser{{background:{COLORS['bg_secondary']};"
        f"color:{COLORS['fg_primary']};border:1px solid {COLORS['border']};"
        f"border-radius:10px;padding:10px;}}")
    return out, None


_RENDERERS = {
    "header": _render_header,
    "text": _render_text,
    "quote": _render_quote,
    "separator": _render_separator,
    "spacer": _render_spacer,
    "group": _render_group,
    "badge": _render_badge,
    "tip": _render_tip,
    "image": _render_image,
    "link": _render_link,
    "progress": _render_progress,
    "stat": _render_stat,
    "param": _render_param,
    "actions": _render_actions,
    "button2": _render_button2,
    "result": _render_result,
    "list_out": _render_list_out,
    "table_out": _render_table_out,
}


def render_layout(owner, layout: dict) -> QWidget:
    """按 ui_layout 渲染完整界面（生成工具运行时与设计器预览共用）。

    owner 需提供：icon/name/description/_get_param/_make_widget/_inputs/_run/_run_btn/_out。
    布局 mode：
      - "flow"（缺省）：控件自上而下堆叠
      - "free"：按 x/y/w/h 绝对定位在固定尺寸画布上（可滚动）
    """
    controls = list((layout or {}).get("controls") or [])
    accent = _accent_of(layout)
    if (layout or {}).get("mode") == "free":
        return _render_free(owner, controls, accent)
    # 兜底：缺 actions/result 时补默认，保证 _run() 可执行且有输出区
    if not any(c.get("type") == "actions" for c in controls):
        controls.append({"type": "actions", "text": "▶ 运行", "align": "right"})
    if not any(c.get("type") == "result" for c in controls):
        controls.append({"type": "result", "placeholder": "运行结果将显示在这里…",
                         "style": "plain"})

    w = QWidget()
    root = QVBoxLayout(w)
    root.setContentsMargins(20, 20, 20, 20)
    root.setSpacing(12)

    seen: set = set()
    for c in controls:
        t = c.get("type")
        if t == "param":
            name = c.get("param", "")
            if not name or name in seen:
                continue
            seen.add(name)
        fn = _RENDERERS.get(t)
        if fn is None:
            continue
        widget, layout_obj = fn(owner, c, accent)
        if widget is not None:
            root.addWidget(widget, 1 if t == "result" else 0)
        if layout_obj is not None:
            root.addLayout(layout_obj)
    return w


def _render_free(owner, controls: list, accent: str):
    """自由布局：控件按 x/y/w/h 绝对定位在可滚动画布上。"""
    if not any(c.get("type") == "actions" for c in controls):
        controls.append({"type": "actions", "text": "▶ 运行", "align": "right",
                         "x": 12, "y": 12, "w": 200, "h": 40})
    if not any(c.get("type") == "result" for c in controls):
        controls.append({"type": "result", "placeholder": "运行结果将显示在这里…",
                         "style": "plain", "x": 12, "y": 60, "w": 440, "h": 160})

    page = QWidget()
    page.setStyleSheet(f"background:{COLORS['bg_primary']};")
    seen: set = set()
    max_x = max_y = 0
    for c in controls:
        t = c.get("type")
        if t == "param":
            name = c.get("param", "")
            if not name or name in seen:
                continue
            seen.add(name)
        fn = _RENDERERS.get(t)
        if fn is None:
            continue
        widget, lay = fn(owner, c, accent)
        item = widget
        if item is None and lay is not None:
            item = QWidget()
            v = QVBoxLayout(item)
            v.setContentsMargins(0, 0, 0, 0)
            v.addLayout(lay)
        if item is None:
            continue
        try:
            x, y = int(c.get("x", 12)), int(c.get("y", 12))
            w, h = int(c.get("w", 200)), int(c.get("h", 40))
        except (TypeError, ValueError):
            x, y, w, h = 12, 12, 200, 40
        item.setParent(page)
        item.setGeometry(x, y, w, h)
        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)

    page_w = max(460, max_x + 12)
    page_h = max(600, max_y + 12)
    page.setFixedSize(page_w, page_h)

    scroll = QScrollArea()
    scroll.setWidgetResizable(False)
    scroll.setWidget(page)
    scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
    return scroll


class DesignerToolBase(BaseTool):
    """生成的工具基类：按 _func 的 @tool 参数渲染表单并执行。

    子类需覆写：tool_id / name / icon / category / description / _func。
    可选覆写：ui_layout（自定义界面布局，None 时用默认自动表单）。
    """

    #: 被 @tool 包装的 FunctionTool 实例
    _func = None

    #: 用户自定义界面布局（None/空 → 默认自动渲染）
    ui_layout: dict | None = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._widget: QWidget | None = None
        self._inputs: dict = {}
        self._run_btn: QPushButton | None = None
        self._run_text: str = "▶ 运行"

    @property
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._build_widget()
        return self._widget

    def _build_widget(self) -> QWidget:
        if self.ui_layout and (self.ui_layout.get("controls") or []):
            return render_layout(self, self.ui_layout)
        return self._build_default_widget()

    def _build_default_widget(self) -> QWidget:
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel(f"{self.icon} {self.name}")
        title.setStyleSheet(f"font-size:18px;font-weight:700;"
                            f"color:{COLORS['fg_primary']};"
                            f"background:{COLORS['bg_base']};border:none;")
        root.addWidget(title)

        desc = QLabel(self.description)
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{COLORS['fg_tertiary']};"
                           f"background:{COLORS['bg_base']};border:none;")
        root.addWidget(desc)

        # 参数表单（来自 @tool 的 parameters 元数据）
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        for p in self._func.parameters:
            label = QLabel(p.name)
            label.setStyleSheet(f"color:{COLORS['fg_secondary']};"
                                f"background:{COLORS['bg_base']};border:none;")
            label.setToolTip(p.description or "")
            widget = self._make_input(p)
            self._inputs[p.name] = widget
            form.addRow(label, widget)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        holder.setLayout(form)
        holder.setStyleSheet(f"background:{COLORS['bg_base']};")
        scroll.setWidget(holder)
        scroll.setStyleSheet("background:transparent;border:none;")
        root.addWidget(scroll)

        # 运行
        row = QHBoxLayout()
        self._run_btn = QPushButton("▶ 运行")
        self._run_btn.setStyleSheet(_BTN)
        self._run_btn.clicked.connect(self._run)
        row.addWidget(self._run_btn)
        row.addStretch(1)
        root.addLayout(row)

        # 结果
        self._out = QTextBrowser()
        self._out.setStyleSheet(
            f"QTextBrowser{{background:{COLORS['bg_secondary']};"
            f"color:{COLORS['fg_primary']};border:1px solid {COLORS['border']};"
            f"border-radius:10px;font-size:13px;padding:10px;}}")
        self._out.setPlaceholderText("运行结果将显示在这里…")
        root.addWidget(self._out, 1)

        return w

    # ---- ui_layout 渲染协议 ----

    def _get_param(self, name: str):
        """按名称查找参数元数据（无则返回 None）。"""
        for p in self._func.parameters:
            if p.name == name:
                return p
        return None

    def _make_widget(self, p, widget: str = "input", options: str = ""):
        return _make_widget(p, widget, options)

    # ---- 默认渲染（旧逻辑） ----

    def _make_input(self, p):
        t = getattr(p, "type_name", "str")
        if t == "int":
            box = QSpinBox()
            box.setRange(-2 ** 31, 2 ** 31 - 1)
            if isinstance(p.default, int):
                box.setValue(p.default)
            box.setStyleSheet(_FIELD_STYLE)
            return box
        if t == "float":
            box = QDoubleSpinBox()
            box.setRange(-1e9, 1e9)
            if isinstance(p.default, float):
                box.setValue(p.default)
            box.setStyleSheet(_FIELD_STYLE)
            return box
        if t == "bool":
            box = QCheckBox()
            box.setChecked(bool(p.default))
            box.setStyleSheet(f"color:{COLORS['fg_secondary']};")
            return box
        edit = QLineEdit()
        if isinstance(p.default, str):
            edit.setText(p.default)
        edit.setPlaceholderText(p.description or p.name)
        edit.setStyleSheet(_FIELD_STYLE)
        return edit

    def _collect(self) -> dict:
        values = {}
        for p in self._func.parameters:
            widget = self._inputs.get(p.name)
            if widget is None:
                continue
            if isinstance(widget, QSpinBox):
                values[p.name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                values[p.name] = widget.value()
            elif isinstance(widget, QCheckBox):
                values[p.name] = widget.isChecked()
            elif isinstance(widget, QPlainTextEdit):
                values[p.name] = widget.toPlainText()
            elif isinstance(widget, QComboBox):
                values[p.name] = widget.currentText()
            elif isinstance(widget, QSlider):
                values[p.name] = widget.value()
            elif isinstance(widget, QDateEdit):
                values[p.name] = widget.date().toString("yyyy-MM-dd")
            elif isinstance(widget, _RadioGroup):
                values[p.name] = widget.value()
            elif isinstance(widget, _ColorEdit):
                values[p.name] = widget.text()
            elif isinstance(widget, _FileEdit):
                values[p.name] = widget.path()
            elif isinstance(widget, QLineEdit):
                values[p.name] = widget.text()
            else:
                values[p.name] = widget.text()
        return values

    def _run(self):
        if self._run_btn is None:
            return
        self._run_btn.setEnabled(False)
        self._run_btn.setText("运行中…")
        try:
            ctx = ToolContext(tool_name=self.tool_id,
                              logger=logging.getLogger(self.tool_id))
            result = self._func.run(ctx, **self._collect())
            if self._out is not None:
                self._out.setPlainText(
                    json.dumps(result, ensure_ascii=False, indent=2, default=str))
        except Exception as e:  # noqa: BLE001 —— 用户代码异常显示给用户
            if self._out is not None:
                self._out.setPlainText(f"[错误] {type(e).__name__}: {e}")
        finally:
            self._run_btn.setEnabled(True)
            self._run_btn.setText(getattr(self, "_run_text", "▶ 运行"))

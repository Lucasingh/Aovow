"""
工具设计器（Tool Designer）—— 可视化设计 + IDE

三块核心区域：
  🎨 可视化设计   组件库（点击/拖拽添加参数）→ 参数画布（编辑名称/默认值/说明）→ 表单实时预览
  ⌨ 工具逻辑      Python 函数体编辑（源码自动预览）
  ▶ 实时运行      不保存也立即编译执行，结果与生成的 AWTF 源码同屏展示

保存后自动注册进侧边栏（双轨制：AWTF @tool + DesignerToolBase GUI）。
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import Qt, QMimeData, QByteArray, QTimer, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPlainTextEdit, QPushButton, QMessageBox, QTabWidget, QSplitter,
    QFrame, QDialog, QFormLayout, QScrollArea, QSpinBox, QDoubleSpinBox,
    QCheckBox,
)

from awtf import ToolContext

from workstation.core.signals import SignalBus
from workstation.tools.base_tool import BaseTool
from workstation.tools.designer_base import render_layout, _make_widget
from workstation.ui.styles import COLORS
from workstation.ui.responsive import get_responsive_engine

DESIGNER_DIR = Path(__file__).resolve().parent.parent / "designer_tools"
VALID_ID = re.compile(r"^[a-z][a-z0-9_]*$")

# 参数类型拖拽的自定义 MIME 类型
_MIME_PARAM = "application/x-aovow-param-type"
# 界面控件拖拽的自定义 MIME 类型
_MIME_UI = "application/x-aovow-ui-control"

# 组件库：类型 → 名称 / 图标 / 主题色
PARAM_TYPES = [
    {"key": "str",   "label": "文本", "icon": "🔤", "color": COLORS["info"]},
    {"key": "int",   "label": "整数", "icon": "🔢", "color": COLORS["success"]},
    {"key": "float", "label": "小数", "icon": "🔣", "color": COLORS["warning"]},
    {"key": "bool",  "label": "布尔", "icon": "☑",  "color": COLORS["accent"]},
]

# 界面组件库（27 种，覆盖 布局/输入/展示/操作/输出 五大类）
# 与 designer_base.render_layout 的渲染器一一对应。
# 每个条目：
#   key      —— 组件库标识（param 变体用 widget 名）
#   control  —— 添加到 ui_layout 的基础 dict（type，param 变体含 widget）
#   defaults —— 控件默认字段
#   fields   —— 属性面板可编辑字段（自由布局自动附加 x/y/w/h）
#   size     —— 自由布局默认尺寸 (w, h)
def _pentry(label, icon, color, widget, size, desc):
    """输入类（param 变体）组件条目工厂。"""
    return {"key": widget, "label": label, "icon": icon, "color": color,
            "desc": desc, "control": {"type": "param", "widget": widget},
            "defaults": {"param": "", "label": "", "widget": widget,
                         "options": "", "placeholder": ""},
            "fields": ["param", "label", "widget", "options", "placeholder"],
            "size": size}


UI_CONTROLS = [
    # ---- 布局类 ----
    {"key": "header", "label": "标题", "icon": "🔖", "color": COLORS["accent"],
     "desc": "工具主标题 + 副标题（空文案自动回退工具名 / 描述）",
     "control": {"type": "header"},
     "defaults": {"text": "", "subtitle": ""},
     "fields": ["text", "subtitle"], "size": (460, 60)},
    {"key": "text", "label": "说明", "icon": "📝", "color": COLORS["info"],
     "desc": "一段说明文字，可设置左 / 中 / 右对齐",
     "control": {"type": "text"},
     "defaults": {"text": "说明文字", "align": "left"},
     "fields": ["text", "align"], "size": (460, 44)},
    {"key": "quote", "label": "引用", "icon": "💬", "color": COLORS["info"],
     "desc": "带左侧主题色描边的引用块",
     "control": {"type": "quote"},
     "defaults": {"text": "引用内容"},
     "fields": ["text"], "size": (460, 60)},
    {"key": "separator", "label": "分隔线", "icon": "➖", "color": COLORS["warning"],
     "desc": "水平分隔线，用于把界面分区",
     "control": {"type": "separator"},
     "defaults": {}, "fields": [], "size": (460, 8)},
    {"key": "spacer", "label": "间距", "icon": "📏", "color": COLORS["border"],
     "desc": "留白间距，高度可调（自由布局下可当占位）",
     "control": {"type": "spacer"},
     "defaults": {}, "fields": ["h"], "size": (460, 16)},
    {"key": "group", "label": "分组", "icon": "📦", "color": COLORS["warning"],
     "desc": "分组小标题，用于组织同类控件",
     "control": {"type": "group"},
     "defaults": {"title": "分组"},
     "fields": ["title"], "size": (460, 24)},
    # ---- 展示类 ----
    {"key": "badge", "label": "徽章", "icon": "🏷", "color": COLORS["info"],
     "desc": "圆角彩色徽章标签",
     "control": {"type": "badge"},
     "defaults": {"text": "徽章", "color": "accent"},
     "fields": ["text", "color"], "size": (180, 30)},
    {"key": "tip", "label": "提示条", "icon": "💡", "color": COLORS["warning"],
     "desc": "信息/成功/警告/错误四种样式的提示条",
     "control": {"type": "tip"},
     "defaults": {"text": "这是一条提示信息", "kind": "info"},
     "fields": ["text", "kind"], "size": (460, 44)},
    {"key": "image", "label": "图片", "icon": "🖼", "color": COLORS["accent"],
     "desc": "显示本地图片（填路径）；留空显示占位",
     "control": {"type": "image"},
     "defaults": {"text": "图片占位", "src": ""},
     "fields": ["text", "src"], "size": (240, 140)},
    {"key": "link", "label": "链接", "icon": "🔗", "color": COLORS["info"],
     "desc": "点击用系统浏览器打开链接",
     "control": {"type": "link"},
     "defaults": {"text": "打开链接", "url": "https://"},
     "fields": ["text", "url"], "size": (460, 28)},
    {"key": "progress", "label": "进度条", "icon": "📊", "color": COLORS["success"],
     "desc": "水平进度条（0-100），可设置格式文案",
     "control": {"type": "progress"},
     "defaults": {"text": "%p%", "value": "60"},
     "fields": ["text", "value"], "size": (460, 26)},
    {"key": "stat", "label": "统计卡片", "icon": "📈", "color": COLORS["success"],
     "desc": "大数字 + 指标名 的统计卡片",
     "control": {"type": "stat"},
     "defaults": {"value": "128", "text": "处理次数"},
     "fields": ["value", "text"], "size": (140, 76)},
    # ---- 输入类（param 变体）----
    _pentry("单行输入", "⌨️", COLORS["success"], "input", (440, 40),
            "单行文本框，绑定参数画布中的参数"),
    _pentry("多行输入", "📄", COLORS["success"], "textarea", (440, 96),
            "多行文本框，适合长文本 / 提问内容"),
    _pentry("下拉选择", "📋", COLORS["success"], "select", (440, 40),
            "下拉选项（options 逗号分隔）"),
    _pentry("数字滑块", "🎚", COLORS["success"], "slider", (440, 40),
            "0-100 滑块，绑定整数参数"),
    _pentry("密码输入", "🔒", COLORS["warning"], "password", (440, 40),
            "密码框（内容以 • 显示），绑定文本参数"),
    _pentry("单选组", "🔘", COLORS["info"], "radio", (440, 80),
            "单选按钮组（options 逗号分隔）"),
    _pentry("勾选开关", "✅", COLORS["success"], "checkbox", (440, 32),
            "勾选框，绑定布尔参数"),
    _pentry("日期选择", "📅", COLORS["info"], "date", (440, 40),
            "日历式日期选择（yyyy-MM-dd）"),
    _pentry("颜色选择", "🎨", COLORS["info"], "color", (440, 40),
            "色块预览 + 系统取色器"),
    _pentry("文件选择", "📂", COLORS["warning"], "file", (440, 40),
            "文件路径输入 + 系统浏览按钮"),
    # ---- 操作类 ----
    {"key": "actions", "label": "运行按钮", "icon": "▶", "color": COLORS["accent"],
     "desc": "执行工具逻辑的按钮，可自定义文字与对齐",
     "control": {"type": "actions"},
     "defaults": {"text": "▶ 运行", "align": "right"},
     "fields": ["text", "align"], "size": (200, 40)},
    {"key": "button2", "label": "辅助按钮", "icon": "🔘", "color": COLORS["border"],
     "desc": "描边样式按钮，可选「点击触发运行」",
     "control": {"type": "button2"},
     "defaults": {"text": "按钮", "run": "no"},
     "fields": ["text", "run"], "size": (140, 36)},
    # ---- 输出类 ----
    {"key": "result", "label": "结果区", "icon": "🖥", "color": COLORS["info"],
     "desc": "运行结果输出区，可选普通 / 对话气泡样式",
     "control": {"type": "result"},
     "defaults": {"placeholder": "运行结果将显示在这里…", "style": "plain"},
     "fields": ["placeholder", "style"], "size": (460, 160)},
    {"key": "list_out", "label": "列表输出", "icon": "📃", "color": COLORS["info"],
     "desc": "示例列表展示区（装饰用，真实数据走结果区）",
     "control": {"type": "list_out"},
     "defaults": {"text": "— 列表输出示例 —\n• 项目一\n• 项目二"},
     "fields": ["text"], "size": (460, 140)},
    {"key": "table_out", "label": "表格输出", "icon": "📊", "color": COLORS["info"],
     "desc": "示例表格展示区（装饰用，真实数据走结果区）",
     "control": {"type": "table_out"},
     "defaults": {"text": ""},
     "fields": ["text"], "size": (460, 140)},
]

# 按控件 dict 反查组件条目（param 变体按 type+widget 匹配）
def _spec_for_ctrl(ctrl: dict) -> dict:
    for s in UI_CONTROLS:
        c = s["control"]
        if c["type"] == ctrl.get("type") and \
                c.get("widget") == ctrl.get("widget"):
            return s
    return UI_CONTROLS[0]

# 属性面板字段标签（按字段 key 统一）
_UI_FIELD_LABELS = {
    "text": "文案", "subtitle": "副标题", "align": "对齐", "title": "标题",
    "kind": "提示类型", "color": "徽章颜色", "src": "图片路径",
    "url": "链接地址", "value": "数值", "run": "触发运行",
    "placeholder": "占位文字", "style": "结果样式",
    "param": "绑定参数", "label": "显示名", "widget": "控件类型",
    "options": "选项（逗号分隔）",
    "x": "X 坐标", "y": "Y 坐标", "w": "宽度", "h": "高度",
}

# 主题色可选项（COLORS token 名）
THEME_TOKENS = ["accent", "accent_hover", "accent_pressed",
                "info", "success", "warning", "error"]

# 可编辑字段 → 下拉编辑器（数据以 itemData 存储）
_UI_SELECT_FIELDS = {
    "align": [("left", "左对齐"), ("center", "居中"), ("right", "右对齐")],
    "widget": [("input", "单行输入"), ("textarea", "多行输入"),
               ("select", "下拉选择"), ("slider", "数字滑块"),
               ("password", "密码输入"), ("radio", "单选组"),
               ("checkbox", "勾选开关"), ("date", "日期选择"),
               ("color", "颜色选择"), ("file", "文件选择")],
    "style": [("plain", "普通"), ("chat", "对话气泡")],
    "kind": [("info", "ℹ️ 信息"), ("success", "✅ 成功"),
             ("warning", "⚠️ 警告"), ("error", "🚫 错误")],
    "run": [("no", "不触发"), ("yes", "触发运行")],
    "color": [(tk, tk) for tk in THEME_TOKENS],
}

# 自由布局模式下附加的位置/尺寸字段
_UI_POS_FIELDS = ("x", "y", "w", "h")
_UI_INT_FIELDS = _UI_POS_FIELDS

# 布局模式
_UI_MODE_FLOW = "flow"
_UI_MODE_FREE = "free"

# 左下角状态栏悬浮提示（分区标题隐藏后，悬浮显示说明）
_HINT_LIBRARY = "组件库 · 点击或拖拽添加参数（文本 / 整数 / 小数 / 布尔）"
_HINT_CANVAS = "参数画布 · 点击卡片编辑名称/默认值/说明，⬆⬇ 排序，🗑 删除"
_HINT_PREVIEW = "表单实时预览 · 修改默认值会实时同步到参数卡片"
_HINT_UI_LIBRARY = "界面组件库 · 点击或拖拽添加（标题 / 说明 / 输入框 / 按钮 / 结果区…）"
_HINT_UI_CANVAS = "界面画布 · 点击卡片选中编辑；自由布局下按住卡片可拖拽摆放，属性面板可精确调 x/y/w/h"
_HINT_UI_PROPS = "属性面板 · 编辑选中卡片的文案 / 绑定参数 / 样式"
_HINT_UI_PREVIEW = "界面实时预览 · 与生成工具运行时渲染完全一致"
_STATUS_DEFAULT = "就绪 —— 悬浮左侧区域查看操作提示"

# ============================================================
# 样式（全部使用 COLORS tokens，禁止硬编码 hex）
# ============================================================
_FIELD_QSS = (
    f"QLineEdit,QComboBox{{background:{COLORS['bg_secondary']};"
    f"color:{COLORS['fg_primary']};border:1px solid {COLORS['border']};"
    f"border-radius:8px;padding:6px 10px;font-size:13px;}}"
    f"QLineEdit:focus,QComboBox:focus{{border:1px solid {COLORS['accent']};}}"
)
_CARD_FIELD_QSS = (
    f"QLineEdit{{background:{COLORS['bg_primary']};"
    f"color:{COLORS['fg_primary']};border:1px solid {COLORS['border']};"
    f"border-radius:6px;padding:3px 8px;font-size:12px;}}"
    f"QLineEdit:focus{{border:1px solid {COLORS['accent']};}}"
)
_ICON_BTN_QSS = (
    f"QPushButton{{background:transparent;color:{COLORS['fg_tertiary']};"
    f"border:none;border-radius:6px;padding:2px 4px;font-size:13px;}}"
    f"QPushButton:hover{{background:{COLORS['bg_hover']};color:{COLORS['fg_primary']};}}"
)
_BTN_QSS = (
    f"QPushButton{{background:{COLORS['accent']};color:#fff;border:none;"
    f"border-radius:8px;padding:8px 22px;font-weight:600;}}"
    f"QPushButton:hover{{background:{COLORS['accent_hover']};}}"
    f"QPushButton:pressed{{background:{COLORS['accent_pressed']};}}"
)
_GHOST_QSS = (
    f"QPushButton{{background:transparent;color:{COLORS['fg_primary']};"
    f"border:1px solid {COLORS['border']};border-radius:8px;padding:8px 16px;}}"
    f"QPushButton:hover{{background:{COLORS['bg_hover']};}}"
)
# 布局模式切换按钮：未选中为描边幽灵按钮，选中为主题色填充
_MODE_QSS = (
    f"QPushButton{{background:transparent;color:{COLORS['fg_secondary']};"
    f"border:1px solid {COLORS['border']};border-radius:8px;"
    f"padding:5px 14px;font-size:12px;}}"
    f"QPushButton:hover{{background:{COLORS['bg_hover']};color:{COLORS['fg_primary']};}}"
    f"QPushButton:checked{{background:{COLORS['accent']};color:#fff;"
    f"border-color:{COLORS['accent']};font-weight:600;}}"
)
_TAB_QSS = (
    f"QTabBar::tab{{background:transparent;color:{COLORS['fg_tertiary']};"
    f"padding:8px 18px;border:none;font-size:13px;}}"
    f"QTabBar::tab:selected{{color:{COLORS['fg_primary']};"
    f"border-bottom:2px solid {COLORS['accent']};}}"
    f"QTabWidget::pane{{border:none;}}"
)
_PREVIEW_QSS = (
    f"QPlainTextEdit{{background:{COLORS['bg_base']};color:{COLORS['fg_primary']};"
    f"border:none;border-radius:8px;font-family:'Consolas','Courier New';"
    f"font-size:12px;padding:10px;}}"
)
_PREVIEW_FIELD_QSS = (
    f"QSpinBox,QDoubleSpinBox,QLineEdit{{background:{COLORS['bg_secondary']};"
    f"color:{COLORS['fg_primary']};border:1px solid {COLORS['border']};"
    f"border-radius:6px;padding:3px 8px;font-size:12px;}}"
    f"QSpinBox:focus,QDoubleSpinBox:focus,QLineEdit:focus{{"
    f"border:1px solid {COLORS['accent']};}}"
)


def _cast(raw: str, t: str):
    """把输入框文本按类型转换；空/非法返回 None（视为未设置默认值）。"""
    if raw == "" or raw.lower() in ("none", "null"):
        return None
    try:
        if t == "int":
            return int(raw)
        if t == "float":
            return float(raw)
        if t == "bool":
            return raw.lower() in ("1", "true", "yes", "是")
    except ValueError:
        return None
    return raw


def _default_to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def camel_class(tool_id: str) -> str:
    """hello_world -> HelloWorld（用于生成工具类名）。"""
    return "".join(w.capitalize() for w in tool_id.split("_")) + "Tool"


class ToolMetaDialog(QDialog):
    """工具元数据设置弹窗：ID / 名称 / 分类 / 图标 / 描述（保存时弹出）。"""

    def __init__(self, current: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("工具设置")
        self.setModal(True)
        self.setMinimumWidth(400)
        cur = current or {}

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._id_edit = QLineEdit(cur.get("tool_id", ""))
        self._id_edit.setPlaceholderText("hello_world")
        self._name_edit = QLineEdit(cur.get("name", ""))
        self._name_edit.setPlaceholderText("工具名称")
        self._cat_combo = QComboBox()
        self._cat_combo.setEditable(True)
        self._cat_combo.addItems(["通用", "系统", "测试", "AI", "自定义"])
        if cur.get("category"):
            self._cat_combo.setCurrentText(cur["category"])
        self._icon_edit = QLineEdit(cur.get("icon", "🧩"))
        self._icon_edit.setMaxLength(4)
        self._desc_edit = QLineEdit(cur.get("description", ""))
        self._desc_edit.setPlaceholderText("一句话描述这个工具…")

        for w in (self._id_edit, self._name_edit, self._cat_combo,
                  self._icon_edit, self._desc_edit):
            w.setStyleSheet(_FIELD_QSS)

        form.addRow("工具 ID", self._id_edit)
        form.addRow("显示名称", self._name_edit)
        form.addRow("分类", self._cat_combo)
        form.addRow("图标", self._icon_edit)
        form.addRow("描述", self._desc_edit)

        btns = QHBoxLayout()
        cancel = QPushButton("取消")
        cancel.setStyleSheet(_GHOST_QSS)
        ok = QPushButton("确定")
        ok.setStyleSheet(_BTN_QSS)
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept_validated)
        btns.addStretch(1)
        btns.addWidget(cancel)
        btns.addWidget(ok)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.addLayout(form)
        root.addSpacing(8)
        root.addLayout(btns)

    def _accept_validated(self):
        try:
            self.values()
        except ValueError as e:
            QMessageBox.warning(self, "设置不完整", str(e))
            return
        self.accept()

    def values(self) -> dict:
        """收集并校验表单值，非法时抛 ValueError。"""
        tool_id = self._id_edit.text().strip()
        if not VALID_ID.match(tool_id):
            raise ValueError(
                "工具 ID 必须是合法标识符：小写字母开头，仅含小写字母/数字/下划线")
        return {
            "tool_id": tool_id,
            "name": self._name_edit.text().strip() or tool_id,
            "category": self._cat_combo.currentText().strip() or "通用",
            "icon": self._icon_edit.text().strip() or "🧩",
            "description": self._desc_edit.text().strip() or f"{tool_id} 工具",
        }


def _render_default(value) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, float)):
        return repr(value)
    return repr(str(value))


def build_source(meta: dict, params: list, body: str,
                 ui_layout: dict | None = None) -> str:
    """根据设计表单生成完整的 AWTF 工具源码。

    ui_layout 非 None 时，在生成的工具类内内嵌自定义界面布局
    （json 保中文），类属性 ui_layout 由 DesignerToolBase 读取渲染。
    """
    tool_id = meta["tool_id"]
    params_lines = []
    sig_parts = ["ctx: ToolContext"]
    for p in params:
        t = p["type"]
        default_repr = _render_default(p["default"])
        params_lines.append(
            f'        Parameter("{p["name"]}", {t}, '
            f'default={default_repr}, description={p["description"]!r}),')
        if p["default"] is None and t not in ("str",):
            sig_parts.append(f"{p['name']}: {t}")
        else:
            sig_parts.append(f"{p['name']}: {t} = {default_repr}")
    param_block = "\n".join(params_lines) if params_lines else "        # 无参数"
    body_indented = "\n".join(f"    {ln}" for ln in (body or "").splitlines())
    ui_block = ""
    if ui_layout:
        ui_block = ("\n    ui_layout = "
                    f"{json.dumps(ui_layout, ensure_ascii=False)}")

    return f'''"""自动生成的工具：{meta["name"]}（由 Aovow 工具设计器创建）"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_AWTF_ROOT = _Path(__file__).resolve().parent.parent.parent / "awtf"
if _AWTF_ROOT.is_dir() and str(_AWTF_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_AWTF_ROOT))

from awtf import Parameter, ToolContext, tool

from workstation.tools.designer_base import DesignerToolBase


@tool(
    name="{tool_id}",
    description={meta["description"]!r},
    tags=["designer"],
    category={meta["category"]!r},
    parameters=[
{param_block}
    ],
)
def {tool_id}({", ".join(sig_parts)}):
    """{meta["description"]}"""
{body_indented}


class {camel_class(tool_id)}(DesignerToolBase):
    tool_id = "{tool_id}"
    name = {meta["name"]!r}
    icon = {meta["icon"]!r}
    category = {meta["category"]!r}
    description = {meta["description"]!r}
    _func = {tool_id}{ui_block}
'''


class TypeCard(QFrame):
    """组件库卡片：点击添加，或按住拖拽到画布（参数 / 界面控件通用）。"""

    clicked = Signal(str)
    hovered = Signal()
    hover_left = Signal()

    def __init__(self, spec: dict, mime: str = _MIME_PARAM, parent=None):
        super().__init__(parent)
        self._spec = spec
        self._mime = mime
        self._drag_start = None
        self._dragged = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setFixedWidth(118)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f"点击添加「{spec['label']}」，或按住拖拽到画布")
        self.setStyleSheet(
            f"QFrame{{background:{COLORS['bg_secondary']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;}}"
            f"QFrame:hover{{background:{COLORS['bg_tertiary']};"
            f"border-color:{spec['color']};}}")

        h = QHBoxLayout(self)
        h.setContentsMargins(10, 8, 10, 8)
        h.setSpacing(8)
        icon = QLabel(spec["icon"])
        icon.setStyleSheet("background:transparent;font-size:15px;")
        label = QLabel(spec["label"])
        label.setStyleSheet(f"background:transparent;color:{COLORS['fg_primary']};"
                            f"font-size:12px;font-weight:600;")
        h.addWidget(icon)
        h.addWidget(label)
        h.addStretch(1)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = e.position()
            self._dragged = False

    def mouseMoveEvent(self, e):
        if self._drag_start is None:
            return
        if (e.buttons() & Qt.MouseButton.LeftButton) and \
                (e.position() - self._drag_start).manhattanLength() > 16:
            self._dragged = True
            mime = QMimeData()
            mime.setData(self._mime, QByteArray(self._spec["key"].encode()))
            drag = QDrag(self)
            drag.setMimeData(mime)
            drag.setPixmap(self.grab())
            drag.setHotSpot((e.position() - self._drag_start).toPoint())
            drag.exec(Qt.DropAction.CopyAction)

    def mouseReleaseEvent(self, e):
        was_click = (not self._dragged and self._drag_start is not None and
                     (e.position() - self._drag_start).manhattanLength() <= 16)
        self._drag_start = None
        self._dragged = False
        if was_click:
            self.clicked.emit(self._spec["key"])

    def enterEvent(self, e):
        self.hovered.emit()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover_left.emit()
        super().leaveEvent(e)


class ParamCard(QFrame):
    """画布上的参数卡片：类型徽章 + 名称 / 默认值 / 说明 + 排序与删除。"""

    changed = Signal()
    move_up = Signal()
    move_down = Signal()
    remove = Signal()
    hovered = Signal()
    hover_left = Signal()

    def __init__(self, spec: dict, param: dict, parent=None):
        super().__init__(parent)
        self._spec = spec
        self._param = param
        self._syncing = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet(
            f"QFrame{{background:{COLORS['bg_secondary']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;}}"
            f"QFrame:hover{{border-color:{COLORS['accent']};}}")

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)

        badge = QLabel(f"{spec['icon']} {spec['label']}")
        badge.setStyleSheet(
            f"background:transparent;color:{spec['color']};"
            f"border:1px solid {spec['color']};border-radius:9px;"
            f"padding:1px 8px;font-size:11px;font-weight:600;")
        badge.setToolTip(f"类型：{spec['label']}")
        top.addWidget(badge)

        self._name = QLineEdit(param["name"])
        self._name.setPlaceholderText("参数名")
        self._name.setToolTip("参数名（小写字母/数字/下划线，保存后即函数参数名）")
        self._name.setStyleSheet(_CARD_FIELD_QSS)
        self._name.textChanged.connect(self._on_text_changed)
        top.addWidget(self._name, 1)

        for text, tip, sig in (
            ("⬆", "上移", self.move_up),
            ("⬇", "下移", self.move_down),
            ("🗑", "删除参数", self.remove),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedWidth(30)
            b.setStyleSheet(_ICON_BTN_QSS)
            b.clicked.connect(sig.emit)
            top.addWidget(b)

        v.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self._default = QLineEdit()
        self._default.setPlaceholderText("默认值（可选）")
        self._default.setStyleSheet(_CARD_FIELD_QSS)
        self._default.setText(_default_to_text(param["default"]))
        self._default.textChanged.connect(self._on_default_changed)
        bottom.addWidget(self._default, 1)

        self._desc = QLineEdit()
        self._desc.setPlaceholderText("说明（可选）")
        self._desc.setStyleSheet(_CARD_FIELD_QSS)
        self._desc.setText(param.get("description", ""))
        self._desc.textChanged.connect(self._on_text_changed)
        bottom.addWidget(self._desc, 2)

        v.addLayout(bottom)

    # ---- 字段变化：就地更新参数 dict ----

    def _on_text_changed(self, text: str):
        if self._syncing:
            return
        if self.sender() is self._name:
            self._param["name"] = text
        elif self.sender() is self._desc:
            self._param["description"] = text
        self.changed.emit()

    def _on_default_changed(self, text: str):
        if self._syncing:
            return
        self._param["default"] = _cast(text, self._spec["key"])
        self.changed.emit()

    def set_default_text(self, text: str):
        """由表单实时预览同步默认值（不触发 changed，避免循环刷新）。"""
        self._syncing = True
        try:
            self._default.setText(text)
        finally:
            self._syncing = False

    def enterEvent(self, e):
        self.hovered.emit()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover_left.emit()
        super().leaveEvent(e)


class HoverFrame(QFrame):
    """带悬浮进出信号的面板（用于左下角状态栏分区提示）。"""

    hovered = Signal()
    hover_left = Signal()

    def enterEvent(self, e):
        self.hovered.emit()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover_left.emit()
        super().leaveEvent(e)


class ParamCanvas(QScrollArea):
    """参数画布：接收组件库拖拽，计算插入位置并通知添加。"""

    add_requested = Signal(str, int)
    hovered = Signal()
    hover_left = Signal()

    def __init__(self, mime: str = _MIME_PARAM, parent=None):
        super().__init__(parent)
        self._mime = mime
        self.cards_ref: list = []
        self._inner = QWidget()
        self._inner.setStyleSheet(f"background:{COLORS['bg_secondary']};")
        self._layout = QVBoxLayout(self._inner)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.setSpacing(8)
        self.setWidget(self._inner)
        self.setWidgetResizable(True)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            f"QScrollArea{{background:{COLORS['bg_secondary']};"
            f"border:1px dashed {COLORS['border_light']};border-radius:10px;}}")

        self._empty = QLabel(
            "🖱 还没有参数\n点击上方组件卡，或把组件拖拽到这里")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            f"color:{COLORS['fg_tertiary']};background:transparent;"
            f"font-size:12px;")
        self._layout.addWidget(self._empty)

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(self._mime):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(self._mime):
            e.acceptProposedAction()

    def dropEvent(self, e):
        key = bytes(e.mimeData().data(self._mime)).decode("utf-8")
        pos = self._inner.mapFrom(self.viewport(), e.position().toPoint())
        y = pos.y()
        idx = len(self.cards_ref)
        for i, card in enumerate(self.cards_ref):
            if card.geometry().center().y() > y:
                idx = i
                break
        self.add_requested.emit(key, idx)

    def enterEvent(self, e):
        self.hovered.emit()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover_left.emit()
        super().leaveEvent(e)


class LayoutCanvas(QScrollArea):
    """界面画布：流式（纵向堆叠）与自由（任意摆放）双模式。

    自由模式：控件卡可左键拖拽到任意位置、点击选中、画布自动撑大；
    拖拽投放组件时携带投放坐标（x, y，网格吸附）。
    """

    add_requested = Signal(str, int, int, int)  # key, index, x, y
    hovered = Signal()
    hover_left = Signal()

    GRID = 8
    PAGE_W = 460
    PAGE_H = 600

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards_ref: list = []
        self._free = False
        self._page = QWidget()
        self._page.setStyleSheet(f"background:{COLORS['bg_secondary']};")
        self._page.setMinimumSize(self.PAGE_W, self.PAGE_H)
        self._flow = QVBoxLayout(self._page)
        self._flow.setContentsMargins(12, 12, 12, 12)
        self._flow.setSpacing(8)
        self.setWidget(self._page)
        self.setWidgetResizable(True)
        self.setAcceptDrops(True)
        self.setStyleSheet(
            f"QScrollArea{{background:{COLORS['bg_secondary']};"
            f"border:1px dashed {COLORS['border_light']};border-radius:10px;}}")
        self._empty = QLabel("🖱 还没有界面控件\n点击上方组件卡，或把组件拖拽到这里")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setStyleSheet(
            f"color:{COLORS['fg_tertiary']};background:transparent;font-size:12px;")
        self._flow.addWidget(self._empty)

    def set_free(self, on: bool):
        self._free = on
        self._page.setMinimumSize(self.PAGE_W, self.PAGE_H)

    def place(self, cards: list):
        """按当前模式摆放卡片（由设计器在重建后调用）。"""
        for card in cards:
            self._flow.removeWidget(card)
        self._flow.removeWidget(self._empty)
        if self._free:
            self._empty.setGeometry(12, 12, self.PAGE_W - 24, 64)
            self._empty.setVisible(not bool(cards))
            for card in cards:
                c = card._ctrl
                card.setParent(self._page)
                card.setGeometry(int(c.get("x", 12)), int(c.get("y", 12)),
                                 int(c.get("w", 200)), int(c.get("h", 40)))
                card.show()
        else:
            self._flow.insertWidget(0, self._empty)
            self._empty.setVisible(not bool(cards))
            for card in cards:
                self._flow.addWidget(card)
                card.show()
        self._grow_to(cards)

    def _grow_to(self, cards: list):
        if not self._free:
            return
        w = h = 0
        for card in cards:
            g = card.geometry()
            w = max(w, g.right() + 12)
            h = max(h, g.bottom() + 12)
        self._page.setMinimumSize(max(self.PAGE_W, w), max(self.PAGE_H, h))

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(_MIME_UI):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if e.mimeData().hasFormat(_MIME_UI):
            e.acceptProposedAction()

    def dropEvent(self, e):
        if not e.mimeData().hasFormat(_MIME_UI):
            return
        key = bytes(e.mimeData().data(_MIME_UI)).decode("utf-8")
        pos = self._page.mapFrom(self.viewport(), e.position().toPoint())
        x = max(12, (pos.x() // self.GRID) * self.GRID)
        y = max(12, (pos.y() // self.GRID) * self.GRID)
        self.add_requested.emit(key, len(self.cards_ref), x, y)

    def enterEvent(self, e):
        self.hovered.emit()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.hover_left.emit()
        super().leaveEvent(e)


_UI_WIDGET_LABELS = {
    "input": "单行输入", "textarea": "多行输入", "select": "下拉选择",
    "slider": "数字滑块", "password": "密码输入", "radio": "单选组",
    "checkbox": "勾选开关", "date": "日期选择", "color": "颜色选择",
    "file": "文件选择",
}


class UILayoutCard(QFrame):
    """界面画布上的控件卡片：类型徽章 + 摘要 + 排序/层级 + 删除 + 选中。

    自由模式下支持：左键点击选中（出现编辑框）、按住拖拽改变画布位置。
    """

    move_up = Signal()
    move_down = Signal()
    remove = Signal()
    selected = Signal()
    moved = Signal()       # 拖拽移动中（位置已更新）
    moved_end = Signal()   # 拖拽结束

    GRID = 8

    def __init__(self, spec: dict, ctrl: dict, free: bool = False,
                 parent=None):
        super().__init__(parent)
        self._spec = spec
        self._ctrl = ctrl
        self._free = free
        self._selected = False
        self._press_global = None
        self._drag_off = None
        self._dragging = False
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._qss())

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        badge = QLabel(f"{spec['icon']} {spec['label']}")
        badge.setStyleSheet(
            f"background:transparent;color:{spec['color']};"
            f"border:1px solid {spec['color']};border-radius:9px;"
            f"padding:1px 8px;font-size:11px;font-weight:600;")
        badge.setToolTip(spec["desc"])
        top.addWidget(badge)

        self._summary = QLabel()
        self._summary.setStyleSheet(
            f"background:transparent;color:{COLORS['fg_secondary']};"
            f"font-size:12px;")
        self._summary.setToolTip(spec["desc"])
        top.addWidget(self._summary, 1)

        btns = []
        for text, sig in (("⬆", self.move_up), ("⬇", self.move_down),
                          ("🗑", self.remove)):
            b = QPushButton(text)
            b.setFixedWidth(30)
            b.setStyleSheet(_ICON_BTN_QSS)
            b.clicked.connect(sig.emit)
            btns.append(b)
            top.addWidget(b)
        # 记录按钮以便切换模式时改提示语
        self._up_btn, self._down_btn, self._del_btn = btns
        self._apply_mode_hints()

        v.addLayout(top)
        self.refresh()

    def _apply_mode_hints(self):
        if self._free:
            self._up_btn.setToolTip("层级上移（置顶）")
            self._down_btn.setToolTip("层级下移（置底）")
        else:
            self._up_btn.setToolTip("上移")
            self._down_btn.setToolTip("下移")
        self._del_btn.setToolTip("删除控件")

    def set_free(self, on: bool):
        self._free = on
        self._apply_mode_hints()

    def _qss(self) -> str:
        border = self._spec["color"] if self._selected else COLORS["border"]
        return (f"QFrame{{background:{COLORS['bg_secondary']};"
                f"border:1px solid {border};border-radius:10px;}}"
                f"QFrame:hover{{border-color:{self._spec['color']};}}")

    def set_selected(self, on: bool):
        """选中 / 取消选中（边框高亮为控件主题色）。"""
        self._selected = on
        self.setStyleSheet(self._qss())

    def refresh(self):
        """卡片数据变化后刷新摘要文本。"""
        c = self._ctrl
        t = c.get("type")
        if t == "param":
            bind = c.get("param") or "未绑定"
            w = _UI_WIDGET_LABELS.get(c.get("widget", "input"), "单行输入")
            self._summary.setText(f"{bind} · {w}")
            return
        elif t == "header":
            self._summary.setText(c.get("text") or "工具主标题")
        elif t == "text":
            self._summary.setText(c.get("text", "说明文字"))
        elif t == "quote":
            self._summary.setText("💬 " + (c.get("text") or "引用"))
        elif t == "separator":
            self._summary.setText("水平分隔线")
        elif t == "spacer":
            self._summary.setText(f"间距 · {c.get('h', 16)}px")
        elif t == "group":
            self._summary.setText(c.get("title", "分组"))
        elif t == "badge":
            self._summary.setText("🏷 " + (c.get("text") or "徽章"))
        elif t == "tip":
            kinds = {"info": "信息", "success": "成功", "warning": "警告", "error": "错误"}
            self._summary.setText(f"💡 {kinds.get(c.get('kind'), '信息')} · "
                                  f"{c.get('text', '')}")
        elif t == "image":
            self._summary.setText("🖼 " + (c.get("src") or c.get("text") or "图片"))
        elif t == "link":
            self._summary.setText("🔗 " + (c.get("text") or c.get("url") or ""))
        elif t == "progress":
            self._summary.setText(f"📊 进度 {c.get('value', '0')}%")
        elif t == "stat":
            self._summary.setText(f"📈 {c.get('value', '0')} · {c.get('text', '指标')}")
        elif t == "actions":
            self._summary.setText(c.get("text") or "▶ 运行")
        elif t == "button2":
            self._summary.setText("🔘 " + (c.get("text") or "按钮") +
                                  ("（触发运行）" if c.get("run") == "yes" else ""))
        elif t == "result":
            style = "对话气泡" if c.get("style") == "chat" else "普通"
            self._summary.setText(f"结果区 · {style}")
        elif t == "list_out":
            self._summary.setText("📃 列表输出")
        elif t == "table_out":
            self._summary.setText("📊 表格输出")
        else:
            self._summary.setText(str(t))

    # ---- 点击选中 + 拖拽移动（自由模式） ----

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.selected.emit()
            self._press_global = e.globalPosition().toPoint()
            self._drag_off = e.position().toPoint()
            self._dragging = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if not (self._free and (e.buttons() & Qt.MouseButton.LeftButton)):
            super().mouseMoveEvent(e)
            return
        if not self._dragging:
            if self._press_global is None or \
                    (e.globalPosition().toPoint() - self._press_global).manhattanLength() <= 8:
                super().mouseMoveEvent(e)
                return
            self._dragging = True
        parent = self.parentWidget()
        if parent is not None:
            pt = parent.mapFromGlobal(e.globalPosition().toPoint()) - self._drag_off
            x = max(4, (pt.x() // self.GRID) * self.GRID)
            y = max(4, (pt.y() // self.GRID) * self.GRID)
            self.move(x, y)
            self.moved.emit()

    def mouseReleaseEvent(self, e):
        if self._dragging:
            self._dragging = False
            self._press_global = None
            self._drag_off = None
            self.moved_end.emit()
        super().mouseReleaseEvent(e)


class _PreviewOwner:
    """渲染器 owner 代理：把设计器画布参数包成 SimpleNamespace，
    供 render_layout 在「界面设计」预览中复用（与生成工具运行时同一渲染函数）。"""

    def __init__(self, designer):
        self._designer = designer
        self.icon = designer._effective_meta()["icon"]
        self.name = designer._effective_meta()["name"]
        self.description = designer._effective_meta()["description"]
        self._inputs: dict = {}
        self._run_btn = None
        self._out = None
        self._run_text = "▶ 运行"

    def _get_param(self, name):
        for p in self._designer._params:
            if p["name"] == name:
                return SimpleNamespace(name=p["name"], type_name=p["type"],
                                       default=p["default"],
                                       description=p["description"])
        return None

    def _make_widget(self, p, widget: str = "input", options: str = ""):
        return _make_widget(p, widget, options)

    def _run(self):
        if self._out is not None:
            self._out.setPlainText("预览模式：保存并注册后，此按钮将执行真实工具逻辑")


class ToolDesignerTool(BaseTool):
    """可视化工具设计器：组件拖拽 + 画布编辑 + 表单实时预览 + 实时运行。"""

    tool_id = "tool_designer"
    name = "工具设计器"
    icon = "🛠️"
    category = "系统"
    description = "可视化设计自己的工具：组件拖拽、实时预览、实时运行、保存即注册"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._widget: QWidget | None = None
        # 工具元数据：保存/设置弹窗填写；未设置时实时运行使用占位值
        self._meta: dict | None = None
        # 画布参数列表：{"name","type","default","description"}
        self._params: list[dict] = []
        self._cards: list[ParamCard] = []
        # 自定义界面布局：{"mode", "theme": {"accent": token}, "controls": [有序控件]}
        self._ui_layout: dict = {"theme": {}, "controls": []}
        self._ui_mode: str = _UI_MODE_FLOW
        self._ui_cards: list[UILayoutCard] = []
        self._selected_ui_card: UILayoutCard | None = None
        self._selected_ui_index: int = -1

    @property
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._build_widget()
        return self._widget

    # ================= 界面 =================

    def _build_widget(self) -> QWidget:
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 防抖定时器：参数/代码变化后延时刷新，避免打字时高频重建
        self._preview_timer = QTimer(w)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._rebuild_preview)
        self._src_timer = QTimer(w)
        self._src_timer.setSingleShot(True)
        self._src_timer.setInterval(400)
        self._src_timer.timeout.connect(self._refresh_source_preview)
        self._ui_preview_timer = QTimer(w)
        self._ui_preview_timer.setSingleShot(True)
        self._ui_preview_timer.setInterval(150)
        self._ui_preview_timer.timeout.connect(self._rebuild_ui_preview)

        r = get_responsive_engine()

        # ---- 顶栏：标题 ----
        header = QFrame()
        header.setStyleSheet(f"background:{COLORS['bg_primary']};"
                             f"border-bottom:1px solid {COLORS['border']};")
        hv = QVBoxLayout(header)
        hv.setContentsMargins(18, 12, 18, 12)

        title_row = QHBoxLayout()
        icon = QLabel("🛠️")
        icon.setStyleSheet("background:transparent;font-size:20px;")
        title = QLabel("工具设计器")
        title.setStyleSheet(f"font-size:{r.font_size(18)}px;font-weight:800;"
                            f"color:{COLORS['fg_primary']};background:transparent;")
        sub = QLabel("可视化设计 · 实时运行 · 一键注册")
        sub.setStyleSheet(f"font-size:{r.font_size(12)}px;color:{COLORS['fg_tertiary']};"
                          f"background:transparent;")
        title_row.addWidget(icon)
        title_row.addWidget(title)
        title_row.addWidget(sub)
        title_row.addStretch(1)
        hv.addLayout(title_row)
        root.addWidget(header)

        # ---- 主区：左编辑 / 右实时运行 ----
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(
            f"QSplitter::handle{{background:{COLORS['border']};}}")

        tabs = QTabWidget()
        tabs.setStyleSheet(_TAB_QSS)
        tabs.addTab(self._build_design_tab(), "🎨 可视化设计")
        tabs.addTab(self._build_ui_tab(), "🖥 界面设计")
        tabs.addTab(self._build_code_tab(), "⌨ 工具逻辑")
        splitter.addWidget(tabs)

        splitter.addWidget(self._build_live_panel())
        splitter.setSizes([520, 320])
        root.addWidget(splitter, 1)

        # ---- 底栏：状态 + 操作 ----
        footer = QFrame()
        footer.setStyleSheet(f"background:{COLORS['bg_primary']};"
                             f"border-top:1px solid {COLORS['border']};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(18, 8, 18, 8)
        self._status = QLabel(_STATUS_DEFAULT)
        self._status.setStyleSheet(f"color:{COLORS['fg_tertiary']};"
                                   f"font-size:{r.font_size(12)}px;background:transparent;")
        fl.addWidget(self._status)
        fl.addStretch(1)

        self._settings_btn = QPushButton("⚙ 设置")
        self._settings_btn.setStyleSheet(_GHOST_QSS)
        self._settings_btn.clicked.connect(self._open_settings)
        self._save_btn = QPushButton("💾 保存并注册")
        self._save_btn.setStyleSheet(_BTN_QSS)
        self._save_btn.clicked.connect(self._save)
        fl.addWidget(self._settings_btn)
        fl.addWidget(self._save_btn)
        root.addWidget(footer)

        # 初始渲染
        self._render_cards()
        self._rebuild_preview()
        self._render_ui_cards()
        self._rebuild_ui_preview()
        self._refresh_source_preview()
        return w

    @staticmethod
    def _sec_label(text: str) -> QLabel:
        """分区标题（保留供代码页等场景使用）。"""
        lab = QLabel(text)
        lab.setStyleSheet(f"color:{COLORS['fg_tertiary']};"
                          f"font-size:{get_responsive_engine().font_size(12)}px;"
                          f"background:transparent;")
        return lab

    def _hover_status(self, text: str):
        """悬浮提示：写入左下角状态栏。"""
        self._status.setText(text)

    def _hover_reset(self):
        """离开分区后恢复默认状态文本。"""
        self._status.setText(_STATUS_DEFAULT)

    def _build_design_tab(self) -> QWidget:
        """可视化设计：组件库 → 参数画布 → 表单实时预览（悬浮看分区提示）。"""
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 14, 14, 8)
        v.setSpacing(10)

        # 组件库（分区提示走左下角状态栏）
        lib = HoverFrame()
        lib.setStyleSheet("background:transparent;border:none;")
        lib.hovered.connect(lambda: self._hover_status(_HINT_LIBRARY))
        lib.hover_left.connect(self._hover_reset)
        lh = QHBoxLayout(lib)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.setSpacing(8)
        for spec in PARAM_TYPES:
            card = TypeCard(spec)
            card.clicked.connect(self._on_add_param)
            card.hovered.connect(lambda: self._hover_status(_HINT_LIBRARY))
            card.hover_left.connect(self._hover_reset)
            lh.addWidget(card)
        lh.addStretch(1)
        v.addWidget(lib)

        # 参数画布
        self._canvas = ParamCanvas()
        self._canvas.add_requested.connect(self._on_add_param)
        self._canvas.hovered.connect(lambda: self._hover_status(_HINT_CANVAS))
        self._canvas.hover_left.connect(self._hover_reset)
        v.addWidget(self._canvas, 1)

        # 表单实时预览
        wrap = HoverFrame()
        wrap.hovered.connect(lambda: self._hover_status(_HINT_PREVIEW))
        wrap.hover_left.connect(self._hover_reset)
        wrap.setStyleSheet(
            f"QFrame{{background:{COLORS['bg_primary']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;}}")
        pv = QVBoxLayout(wrap)
        pv.setContentsMargins(12, 10, 12, 10)
        self._preview_scroll = QScrollArea()
        self._preview_scroll.setWidgetResizable(True)
        self._preview_scroll.setMaximumHeight(190)
        self._preview_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}")
        self._preview_holder = QWidget()
        self._preview_holder.setStyleSheet(f"background:{COLORS['bg_primary']};")
        self._preview_form = QFormLayout(self._preview_holder)
        self._preview_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._preview_form.setContentsMargins(0, 0, 0, 0)
        self._preview_form.setSpacing(8)
        self._preview_scroll.setWidget(self._preview_holder)
        pv.addWidget(self._preview_scroll)
        v.addWidget(wrap)
        return page

    def _build_ui_tab(self) -> QWidget:
        """🖥 界面设计：UI 组件库 → 界面画布 → 属性面板 → 界面实时预览。

        用户可自由拼装「标题/说明/分隔线/分组/输入框/按钮/结果区」，
        做出 AI 对话等不同形态的工具界面。
        """
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 14, 14, 8)
        v.setSpacing(10)

        # UI 组件库（悬浮提示走左下角状态栏）
        lib = HoverFrame()
        lib.setStyleSheet("background:transparent;border:none;")
        lib.hovered.connect(lambda: self._hover_status(_HINT_UI_LIBRARY))
        lib.hover_left.connect(self._hover_reset)
        lh = QHBoxLayout(lib)
        lh.setContentsMargins(0, 0, 0, 0)
        lh.setSpacing(6)
        for spec in UI_CONTROLS:
            card = TypeCard(spec, mime=_MIME_UI)
            card.clicked.connect(self._on_add_ui_control)
            card.hovered.connect(lambda: self._hover_status(_HINT_UI_LIBRARY))
            card.hover_left.connect(self._hover_reset)
            lh.addWidget(card)
        lh.addStretch(1)
        v.addWidget(lib)

        # 布局模式切换：流式（纵向堆叠）/ 自由（随意摆放 + 拖拽 + 定位）
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        mode_lab = QLabel("布局")
        mode_lab.setStyleSheet(
            f"color:{COLORS['fg_tertiary']};background:transparent;font-size:12px;")
        self._mode_flow_btn = QPushButton("📐 流式布局")
        self._mode_free_btn = QPushButton("🖼 自由布局")
        self._mode_flow_btn.setCheckable(True)
        self._mode_free_btn.setCheckable(True)
        for b in (self._mode_flow_btn, self._mode_free_btn):
            b.setStyleSheet(_MODE_QSS)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mode_flow_btn.setChecked(self._ui_mode == _UI_MODE_FLOW)
        self._mode_free_btn.setChecked(self._ui_mode == _UI_MODE_FREE)
        self._mode_flow_btn.setToolTip("控件从上到下依次排列，画布高度自动撑开")
        self._mode_free_btn.setToolTip(
            "控件可摆放在画布任意位置：左键按住卡片拖拽移动，点击卡片在右侧编辑 x/y/w/h")
        self._mode_flow_btn.clicked.connect(lambda: self._on_ui_mode_changed(False))
        self._mode_free_btn.clicked.connect(lambda: self._on_ui_mode_changed(True))
        mode_row.addWidget(mode_lab)
        mode_row.addWidget(self._mode_flow_btn)
        mode_row.addWidget(self._mode_free_btn)
        mode_row.addStretch(1)
        v.addLayout(mode_row)

        # 主题色 + AI 对话模板
        opt = QHBoxLayout()
        opt.setSpacing(8)
        theme_lab = QLabel("主题色")
        theme_lab.setStyleSheet(
            f"color:{COLORS['fg_tertiary']};background:transparent;font-size:12px;")
        self._theme_combo = QComboBox()
        for token in THEME_TOKENS:
            self._theme_combo.addItem(token, token)
        cur = (self._ui_layout.get("theme") or {}).get("accent") or "accent"
        idx = self._theme_combo.findData(cur)
        self._theme_combo.setCurrentIndex(max(0, idx))
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        self._theme_combo.setStyleSheet(_FIELD_QSS)
        self._theme_combo.setToolTip("界面主题色（COLORS token，影响按钮 / 结果区描边）")
        opt.addWidget(theme_lab)
        opt.addWidget(self._theme_combo)
        opt.addStretch(1)
        ai_btn = QPushButton("🤖 填入 AI 对话模板")
        ai_btn.setStyleSheet(_GHOST_QSS)
        ai_btn.setToolTip("一键生成 AI 对话工具：多行提问 + 💬 发送 + 对话结果区（DeepSeek）")
        ai_btn.clicked.connect(self._fill_ai_template)
        opt.addWidget(ai_btn)
        v.addLayout(opt)

        # 中部：左 = 界面画布 + 属性面板；右 = 界面实时预览
        mid = QSplitter(Qt.Orientation.Horizontal)
        mid.setHandleWidth(1)
        mid.setStyleSheet(
            f"QSplitter::handle{{background:{COLORS['border']};}}")

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        lv.setSpacing(8)

        # 界面画布
        self._ui_canvas = LayoutCanvas()
        self._ui_canvas.add_requested.connect(self._on_add_ui_control)
        self._ui_canvas.hovered.connect(lambda: self._hover_status(_HINT_UI_CANVAS))
        self._ui_canvas.hover_left.connect(self._hover_reset)
        lv.addWidget(self._ui_canvas, 1)

        # 属性面板
        props = HoverFrame()
        props.hovered.connect(lambda: self._hover_status(_HINT_UI_PROPS))
        props.hover_left.connect(self._hover_reset)
        props.setStyleSheet(
            f"QFrame{{background:{COLORS['bg_primary']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;}}")
        pv = QVBoxLayout(props)
        pv.setContentsMargins(10, 8, 10, 8)
        pv.setSpacing(6)
        self._ui_prop_hint = QLabel("选中画布中的卡片后，在这里编辑属性")
        self._ui_prop_hint.setStyleSheet(
            f"color:{COLORS['fg_tertiary']};background:transparent;"
            f"font-size:12px;")
        pv.addWidget(self._ui_prop_hint)
        self._ui_prop_form = QFormLayout()
        self._ui_prop_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._ui_prop_form.setContentsMargins(0, 0, 0, 0)
        self._ui_prop_form.setSpacing(6)
        pv.addLayout(self._ui_prop_form)
        lv.addWidget(props)

        mid.addWidget(left)

        # 界面实时预览
        pwrap = HoverFrame()
        pwrap.hovered.connect(lambda: self._hover_status(_HINT_UI_PREVIEW))
        pwrap.hover_left.connect(self._hover_reset)
        pwrap.setStyleSheet(
            f"QFrame{{background:{COLORS['bg_primary']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;}}")
        pv2 = QVBoxLayout(pwrap)
        pv2.setContentsMargins(12, 10, 12, 10)
        self._ui_preview_scroll = QScrollArea()
        self._ui_preview_scroll.setWidgetResizable(True)
        self._ui_preview_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}")
        self._ui_preview_holder = QWidget()
        self._ui_preview_holder.setStyleSheet(f"background:{COLORS['bg_primary']};")
        self._ui_preview_layout = QVBoxLayout(self._ui_preview_holder)
        self._ui_preview_layout.setContentsMargins(0, 0, 0, 0)
        self._ui_preview_scroll.setWidget(self._ui_preview_holder)
        pv2.addWidget(self._ui_preview_scroll)
        mid.addWidget(pwrap)

        mid.setSizes([300, 220])
        v.addWidget(mid, 1)
        return page

    def _build_code_tab(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 14, 14, 8)
        v.setSpacing(10)

        tip = QLabel("编写函数体逻辑（自动包在 def 内，return dict 最佳）")
        tip.setStyleSheet(f"color:{COLORS['fg_tertiary']};"
                          f"font-size:{get_responsive_engine().font_size(12)}px;"
                          f"background:transparent;")
        v.addWidget(tip)

        self._code_edit = QPlainTextEdit()
        self._code_edit.setStyleSheet(_PREVIEW_QSS)
        self._code_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._code_edit.setPlainText(
            "# 在这里写你的工具逻辑\n"
            "ctx.info(\"工具运行\")\n"
            "return {\"result\": \"你好，世界！\"}")
        self._code_edit.textChanged.connect(self._schedule_refresh)
        v.addWidget(self._code_edit, 1)

        example = QPushButton("📄 填入示例逻辑")
        example.setStyleSheet(_GHOST_QSS)
        example.clicked.connect(self._fill_example)
        v.addWidget(example)
        return page

    def _build_live_panel(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background:{COLORS['bg_secondary']};")
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 14, 14, 14)
        v.setSpacing(10)

        head = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{COLORS['success']};background:transparent;")
        lab = QLabel("实时运行")
        lab.setStyleSheet(f"font-size:{get_responsive_engine().font_size(15)}px;"
                          f"font-weight:700;color:{COLORS['fg_primary']};"
                          f"background:transparent;")
        hint = QLabel("不保存也能看效果")
        hint.setStyleSheet(f"font-size:11px;color:{COLORS['fg_tertiary']};"
                           f"background:transparent;")
        head.addWidget(dot)
        head.addWidget(lab)
        head.addWidget(hint)
        head.addStretch(1)
        self._run_btn = QPushButton("▶ 运行")
        self._run_btn.setStyleSheet(_BTN_QSS)
        self._run_btn.clicked.connect(self._run_live)
        head.addWidget(self._run_btn)
        v.addLayout(head)

        self._live_out = QPlainTextEdit()
        self._live_out.setReadOnly(True)
        self._live_out.setStyleSheet(_PREVIEW_QSS)
        self._live_out.setPlaceholderText(
            "点击「▶ 运行」立即执行你设计的工具\n\n结果会以 JSON 展示在这里")
        v.addWidget(self._live_out, 1)

        src_lab = QLabel("🧾 生成的 AWTF 源码（自动更新）")
        src_lab.setStyleSheet(f"font-size:12px;font-weight:600;"
                              f"color:{COLORS['fg_secondary']};background:transparent;")
        v.addWidget(src_lab)
        self._preview_box = QPlainTextEdit()
        self._preview_box.setReadOnly(True)
        self._preview_box.setMaximumHeight(170)
        self._preview_box.setStyleSheet(_PREVIEW_QSS)
        self._preview_box.setPlaceholderText("参数或代码变化后自动生成源码…")
        v.addWidget(self._preview_box)
        return page

    # ================= 画布逻辑 =================

    def _on_add_param(self, key: str, index: int | None = None):
        if index is None:
            index = len(self._params)
        index = max(0, min(index, len(self._params)))
        param = {"name": self._unique_name(key), "type": key,
                 "default": None, "description": ""}
        self._params.insert(index, param)
        self._render_cards()
        spec = next(s for s in PARAM_TYPES if s["key"] == key)
        self._status.setText(f"已添加参数「{param['name']}」（{spec['label']}）")
        self._schedule_refresh()
        self._sync_param_bindings()

    def _unique_name(self, key: str) -> str:
        base = f"{key}_param"
        name, i = base, 1
        existing = {p["name"] for p in self._params}
        while name in existing:
            i += 1
            name = f"{base}{i}"
        return name

    def _render_cards(self):
        lay = self._canvas._layout
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None and w is not self._canvas._empty:
                w.deleteLater()
        lay.addWidget(self._canvas._empty)
        self._canvas._empty.setVisible(not bool(self._params))
        self._cards = []
        for p in self._params:
            spec = next(s for s in PARAM_TYPES if s["key"] == p["type"])
            card = ParamCard(spec, p)
            card.changed.connect(self._on_param_card_changed)
            card.move_up.connect(lambda c=card: self._move_param(c, -1))
            card.move_down.connect(lambda c=card: self._move_param(c, 1))
            card.remove.connect(lambda c=card: self._remove_param(c))
            card.hovered.connect(lambda: self._hover_status(_HINT_CANVAS))
            card.hover_left.connect(self._hover_reset)
            lay.addWidget(card)
            self._cards.append(card)
        lay.addStretch(1)
        self._canvas.cards_ref = self._cards

    def _move_param(self, card: ParamCard, delta: int):
        i = self._cards.index(card)
        j = i + delta
        if not (0 <= j < len(self._params)):
            return
        self._params[i], self._params[j] = self._params[j], self._params[i]
        self._render_cards()
        self._schedule_refresh()

    def _remove_param(self, card: ParamCard):
        i = self._cards.index(card)
        self._params.pop(i)
        self._render_cards()
        self._schedule_refresh()
        self._status.setText(f"已删除参数（剩 {len(self._params)} 个）")
        self._sync_param_bindings()

    def _on_param_card_changed(self):
        self._schedule_refresh()

    # ================= 界面设计（ui_layout）逻辑 =================

    def _on_add_ui_control(self, key: str, index: int | None = None,
                           x: int | None = None, y: int | None = None):
        """组件库添加界面控件（点击或拖拽投递；自由模式携带投放坐标）。"""
        controls = self._ui_layout["controls"]
        spec = next((s for s in UI_CONTROLS if s["key"] == key), UI_CONTROLS[0])
        if index is None:
            index = len(controls)
        index = max(0, min(index, len(controls)))
        ctrl = dict(spec["control"])
        ctrl.update(spec["defaults"])
        if self._ui_mode == _UI_MODE_FREE:
            ctrl["x"], ctrl["y"], ctrl["w"], ctrl["h"] = \
                self._next_free_spot(x, y, spec["size"])
        controls.insert(index, ctrl)
        self._render_ui_cards()
        self._status.setText(f"已添加界面控件「{spec['label']}」")
        self._schedule_ui_refresh()

    def _render_ui_cards(self):
        """重建界面画布卡片；恢复之前选中项（按控件 dict 身份匹配）。"""
        canvas = self._ui_canvas
        sel_ctrl = None
        if self._selected_ui_card is not None:
            sel_ctrl = self._selected_ui_card._ctrl
        # 移除旧卡片（立即解除父子关系，避免残留重叠）
        for card in list(self._ui_cards):
            canvas._flow.removeWidget(card)
            card.setParent(None)
            card.deleteLater()
        self._ui_cards = []
        for ctrl in self._ui_layout["controls"]:
            spec = _spec_for_ctrl(ctrl)
            card = UILayoutCard(spec, ctrl,
                                free=(self._ui_mode == _UI_MODE_FREE))
            card.move_up.connect(lambda c=card: self._move_ui(c, -1))
            card.move_down.connect(lambda c=card: self._move_ui(c, 1))
            card.remove.connect(lambda c=card: self._remove_ui(c))
            card.selected.connect(lambda c=card: self._select_ui(c))
            card.moved.connect(lambda c=card: self._on_ui_card_moved(c))
            card.moved_end.connect(self._schedule_ui_refresh)
            self._ui_cards.append(card)
        canvas.cards_ref = self._ui_cards
        canvas.place(self._ui_cards)

        # 恢复选中
        self._selected_ui_card = None
        self._selected_ui_index = -1
        if sel_ctrl is not None:
            for i, c in enumerate(self._ui_layout["controls"]):
                if c is sel_ctrl:
                    self._selected_ui_card = self._ui_cards[i]
                    self._selected_ui_index = i
                    self._ui_cards[i].set_selected(True)
                    break
        self._show_ui_props()

    def _move_ui(self, card: UILayoutCard, delta: int):
        controls = self._ui_layout["controls"]
        i = self._ui_cards.index(card)
        j = i + delta
        if not (0 <= j < len(controls)):
            return
        controls[i], controls[j] = controls[j], controls[i]
        self._render_ui_cards()
        self._schedule_ui_refresh()

    def _remove_ui(self, card: UILayoutCard):
        controls = self._ui_layout["controls"]
        i = self._ui_cards.index(card)
        controls.pop(i)
        self._render_ui_cards()
        self._schedule_ui_refresh()
        self._status.setText(f"已删除界面控件（剩 {len(controls)} 个）")

    def _select_ui(self, card: UILayoutCard):
        """点击选中卡片 → 高亮 + 属性面板显示对应字段。"""
        for c in self._ui_cards:
            c.set_selected(c is card)
        self._selected_ui_card = card
        self._selected_ui_index = self._ui_cards.index(card)
        self._show_ui_props()

    def _show_ui_props(self):
        """按选中卡片的字段重建属性面板（未选中时显示引导文案）。"""
        form = self._ui_prop_form
        while form.count():
            item = form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._ui_prop_editors: dict = {}
        self._ui_prop_hint.setVisible(self._selected_ui_card is None)
        if self._selected_ui_card is None:
            return
        ctrl = self._selected_ui_card._ctrl
        spec = self._selected_ui_card._spec
        fields = list(spec["fields"])
        if self._ui_mode == _UI_MODE_FREE:
            fields += list(_UI_POS_FIELDS)
        for key in fields:
            editor = self._make_ui_prop_editor(key, ctrl.get(key, ""))
            label = QLabel(_UI_FIELD_LABELS.get(key, key))
            label.setStyleSheet(f"color:{COLORS['fg_secondary']};"
                                f"background:transparent;font-size:12px;")
            self._ui_prop_editors[key] = editor
            form.addRow(label, editor)

    def _make_ui_prop_editor(self, key: str, value):
        """按字段 key 生成属性编辑器（下拉 / 数值框 / 参数绑定下拉 / 单行文本）。"""
        if key in _UI_SELECT_FIELDS:
            combo = QComboBox()
            for val, lab in _UI_SELECT_FIELDS[key]:
                combo.addItem(lab, val)
            idx = combo.findData(value)
            combo.setCurrentIndex(max(0, idx))
            combo.currentIndexChanged.connect(
                lambda _i, k=key, c=combo: self._on_ui_prop_changed(k, c.currentData()))
            combo.setStyleSheet(_FIELD_QSS)
            return combo
        if key in _UI_INT_FIELDS:
            spin = QSpinBox()
            spin.setRange(0, 4000)
            spin.setValue(int(value or 0))
            spin.valueChanged.connect(
                lambda v, k=key: self._on_ui_prop_changed(k, v))
            spin.setStyleSheet(_FIELD_QSS)
            return spin
        if key == "param":
            combo = QComboBox()
            combo.addItem("（未绑定）", "")
            for p in self._params:
                if p["name"].strip():
                    combo.addItem(p["name"], p["name"])
            combo.setEditable(True)
            combo.setCurrentText(str(value or ""))
            combo.currentTextChanged.connect(
                lambda text, k=key: self._on_ui_prop_changed(k, text))
            combo.setStyleSheet(_FIELD_QSS)
            return combo
        edit = QLineEdit()
        edit.setText(str(value or ""))
        edit.textChanged.connect(
            lambda text, k=key: self._on_ui_prop_changed(k, text))
        edit.setStyleSheet(_FIELD_QSS)
        return edit

    def _on_ui_prop_changed(self, key: str, value):
        """属性面板修改 → 写入控件 dict → 刷新卡片摘要与预览。"""
        if self._selected_ui_card is None:
            return
        if key == "param" and value == "（未绑定）":
            value = ""
        ctrl = self._selected_ui_card._ctrl
        ctrl[key] = value
        self._selected_ui_card.refresh()
        if self._ui_mode == _UI_MODE_FREE and key in _UI_POS_FIELDS:
            # 自由模式：x/y/w/h 变化 → 实时移动画布卡片
            card = self._selected_ui_card
            card.setGeometry(int(ctrl.get("x", 12)), int(ctrl.get("y", 12)),
                             int(ctrl.get("w", 200)), int(ctrl.get("h", 40)))
            self._ui_canvas._grow_to(self._ui_cards)
        self._schedule_ui_refresh()

    def _on_theme_changed(self, index: int):
        self._ui_layout["theme"] = {"accent": self._theme_combo.itemData(index)}
        self._schedule_ui_refresh()

    # ================= 布局模式（流式 / 自由） =================

    def _on_ui_mode_changed(self, free: bool):
        """切换布局模式：flow（流式堆叠）↔ free（自由摆放）。"""
        if (free and self._ui_mode == _UI_MODE_FREE) or \
                (not free and self._ui_mode == _UI_MODE_FLOW):
            return
        self._ui_mode = _UI_MODE_FREE if free else _UI_MODE_FLOW
        self._ui_layout["mode"] = self._ui_mode
        self._mode_flow_btn.setChecked(not free)
        self._mode_free_btn.setChecked(free)
        self._ui_canvas.set_free(free)
        if free:
            self._ensure_positions()
        self._render_ui_cards()
        self._schedule_ui_refresh()
        self._status.setText(
            f"已切换为「{'自由' if free else '流式'}布局」："
            f"{'拖拽卡片可随意摆放，点击卡片可精确定位' if free else '控件从上到下自动排列'}")

    def _ensure_positions(self):
        """自由模式：为没有 x/y/w/h 的控件补上瀑布流位置与默认尺寸。"""
        for ctrl in self._ui_layout["controls"]:
            if "x" not in ctrl:
                spec = _spec_for_ctrl(ctrl)
                ctrl["x"], ctrl["y"], ctrl["w"], ctrl["h"] = \
                    self._next_free_spot(None, None, spec["size"])

    def _next_free_spot(self, x: int | None, y: int | None,
                        size: tuple) -> tuple:
        """自由模式：计算新控件放置位置与默认尺寸。

        提供投放坐标（拖拽投递）→ 网格吸附后直接使用；
        否则瀑布流找第一个不与其他控件重叠的位置。
        """
        w, h = size
        if x is not None and y is not None:
            return int(x), int(y), int(w), int(h)
        rects = []
        for c in self._ui_layout["controls"]:
            if "x" in c:
                rects.append((int(c["x"]), int(c["y"]),
                              int(c.get("w", 200)), int(c.get("h", 40))))
        step = self._ui_canvas.GRID
        y = 12
        while True:
            # 下界 +step 保证全宽控件至少尝试 x=12，避免 range 为空导致死循环
            for x in range(12, max(12 + step, self._ui_canvas.PAGE_W - w + step),
                           step):
                if not any(self._rects_overlap(x, y, w, h, r) for r in rects):
                    return x, y, w, h
            y += step

    @staticmethod
    def _rects_overlap(x: int, y: int, w: int, h: int, r: tuple) -> bool:
        rx, ry, rw, rh = r
        return not (x + w <= rx or rx + rw <= x or y + h <= ry or ry + rh <= y)

    def _on_ui_card_moved(self, card: UILayoutCard):
        """自由模式拖拽移动中：坐标实时写回控件 dict + 画布撑大。"""
        ctrl = card._ctrl
        g = card.geometry()
        ctrl["x"], ctrl["y"], ctrl["w"], ctrl["h"] = g.x(), g.y(), g.width(), g.height()
        self._ui_canvas._grow_to(self._ui_cards)
        if card is self._selected_ui_card:
            self._sync_ui_pos_editors(ctrl)

    def _sync_ui_pos_editors(self, ctrl: dict):
        """拖拽后静默刷新属性面板的 x/y/w/h 数值框。"""
        editors = getattr(self, "_ui_prop_editors", {})
        for key in _UI_POS_FIELDS:
            ed = editors.get(key)
            if isinstance(ed, QSpinBox):
                ed.blockSignals(True)
                ed.setValue(int(ctrl.get(key, 0)))
                ed.blockSignals(False)

    def _fill_ai_template(self):
        """一键填入 AI 对话模板：确保 prompt 参数 + 对话布局 + DeepSeek 函数体。"""
        # 模板基于流式布局：自由模式下先切回流式，避免控件全部堆叠在左上角
        self._ui_mode = _UI_MODE_FLOW
        self._ui_layout["mode"] = _UI_MODE_FLOW
        if hasattr(self, "_mode_flow_btn"):
            self._mode_flow_btn.setChecked(True)
            self._mode_free_btn.setChecked(False)
            self._ui_canvas.set_free(False)
        if not any(p["name"] == "prompt" for p in self._params):
            self._params.append({"name": "prompt", "type": "str",
                                 "default": "", "description": "你想问 AI 的问题"})
            self._render_cards()
        self._ui_layout = {
            "mode": _UI_MODE_FLOW,
            "theme": {"accent": "accent"},
            "controls": [
                {"type": "header", "text": "", "subtitle": ""},
                {"type": "text", "text": "向 DeepSeek 提问，即时返回回答", "align": "center"},
                {"type": "param", "param": "prompt", "label": "你的问题",
                 "widget": "textarea", "options": "", "placeholder": "输入你的问题…"},
                {"type": "actions", "text": "💬 发送", "align": "right"},
                {"type": "result", "placeholder": "AI 的回答将显示在这里…", "style": "chat"},
            ],
        }
        self._code_edit.setPlainText(
            "from awtf.ai.deepseek import chat, resolve_api_key\n"
            "\n"
            "api_key = resolve_api_key()\n"
            "if not api_key:\n"
            "    return {\"reply\": \"未配置 API Key：请设置 DEEPSEEK_API_KEY 环境变量\"}\n"
            "reply = chat(api_key, [{\"role\": \"user\", \"content\": prompt.strip()}])\n"
            "return {\"reply\": reply}")
        self._render_ui_cards()
        self._sync_param_bindings()
        self._rebuild_preview()
        self._schedule_ui_refresh()
        self._status.setText("已填入 AI 对话模板：多行提问 + 💬 发送 + 对话结果区")

    def _sync_param_bindings(self):
        """参数增删后同步 UI 布局绑定：被删参数的控件 → 标记「未绑定」。"""
        names = {p["name"] for p in self._params if p["name"].strip()}
        changed = False
        for ctrl in self._ui_layout["controls"]:
            if ctrl["type"] == "param" and ctrl.get("param") not in names:
                if ctrl.get("param"):
                    changed = True
                ctrl["param"] = ""
        for card in self._ui_cards:
            card.refresh()
        if self._selected_ui_card is not None:
            self._show_ui_props()
        if changed:
            self._schedule_ui_refresh()

    def _rebuild_ui_preview(self):
        """重建界面实时预览（复用 render_layout，与生成工具运行时一致）。"""
        lay = self._ui_preview_layout
        while lay.count():
            item = lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        if not self._ui_layout.get("controls"):
            empty = QLabel("添加界面组件后，这里会实时渲染出工具的界面")
            empty.setStyleSheet(f"color:{COLORS['fg_tertiary']};"
                                f"background:transparent;font-size:12px;")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(empty)
            return
        owner = _PreviewOwner(self)
        widget = render_layout(owner, self._ui_layout)
        lay.addWidget(widget)

    def _schedule_ui_refresh(self):
        """界面布局变化 → 防抖刷新界面预览 + 源码预览。"""
        self._ui_preview_timer.start()
        self._src_timer.start()

    # ================= 表单实时预览 =================

    def _rebuild_preview(self):
        form = self._preview_form
        while form.count():
            item = form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        params = [p for p in self._params if p["name"].strip()]
        if not params:
            empty = QLabel("添加参数后，这里会实时渲染出工具的输入表单")
            empty.setStyleSheet(f"color:{COLORS['fg_tertiary']};"
                                f"background:transparent;font-size:12px;")
            form.addRow(empty)
            return

        for p in params:
            label = QLabel(p["name"])
            label.setStyleSheet(f"color:{COLORS['fg_secondary']};"
                                f"background:transparent;font-size:12px;")
            label.setToolTip(p["description"] or p["name"])
            form.addRow(label, self._make_preview_input(p))

    def _make_preview_input(self, p: dict):
        t = p["type"]
        if t == "int":
            box = QSpinBox()
            box.setRange(-2 ** 31, 2 ** 31 - 1)
            box.setStyleSheet(_PREVIEW_FIELD_QSS)
            if isinstance(p["default"], int):
                box.setValue(p["default"])
            box.valueChanged.connect(lambda v, pp=p: self._on_preview_value(pp, v))
            return box
        if t == "float":
            box = QDoubleSpinBox()
            box.setRange(-1e9, 1e9)
            box.setStyleSheet(_PREVIEW_FIELD_QSS)
            if isinstance(p["default"], float):
                box.setValue(p["default"])
            box.valueChanged.connect(lambda v, pp=p: self._on_preview_value(pp, v))
            return box
        if t == "bool":
            box = QCheckBox()
            box.setChecked(bool(p["default"]))
            box.setStyleSheet(f"color:{COLORS['fg_secondary']};")
            box.toggled.connect(lambda v, pp=p: self._on_preview_value(pp, v))
            return box
        edit = QLineEdit()
        edit.setStyleSheet(_PREVIEW_FIELD_QSS)
        edit.setPlaceholderText(p["description"] or p["name"])
        if isinstance(p["default"], str):
            edit.setText(p["default"])
        edit.textChanged.connect(lambda text, pp=p: self._on_preview_value(pp, text))
        return edit

    def _on_preview_value(self, param: dict, value):
        """表单预览中修改默认值 → 同步到画布卡片（不触发循环重建）。"""
        param["default"] = value
        i = next((n for n, p in enumerate(self._params) if p is param), -1)
        if i >= 0:
            self._cards[i].set_default_text(_default_to_text(value))
        self._schedule_refresh()

    # ================= 元数据 / 参数 =================

    def _effective_meta(self) -> dict:
        """已设置则用真实元数据，否则返回占位值（实时运行/预览用）。"""
        if self._meta is not None:
            return self._meta
        return {
            "tool_id": "designer_preview",
            "name": "设计预览",
            "category": "自定义",
            "icon": "🧩",
            "description": "设计器实时预览工具",
        }

    def _effective_params(self) -> list:
        """清洗画布参数：跳过空名、str 空默认归一化、重名校验。"""
        params = []
        for p in self._params:
            name = p["name"].strip()
            if not name:
                continue
            default = p["default"]
            if p["type"] == "str" and default is None:
                default = ""
            params.append({"name": name, "type": p["type"],
                           "default": default, "description": p["description"]})
        names = [p["name"] for p in params]
        if len(names) != len(set(names)):
            raise ValueError("参数名不能重复，请检查画布中的参数")
        return params

    def _open_settings(self):
        """弹出工具设置对话框（保存时也会调用）。"""
        dlg = ToolMetaDialog(self._meta, self._widget)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._meta = dlg.values()
            self._status.setText(
                f"已设置：{self._meta['name']}（{self._meta['tool_id']}）"
                f" · 点「保存并注册」落地到侧边栏")

    # ================= 动作 =================

    def _build_source(self):
        return build_source(self._effective_meta(), self._effective_params(),
                            self._code_edit.toPlainText(), self._ui_layout_or_none())

    def _ui_layout_or_none(self):
        """界面布局无控件时返回 None（不内嵌 ui_layout，回退默认渲染）。"""
        return self._ui_layout if self._ui_layout.get("controls") else None

    def _schedule_refresh(self, *_args):
        self._src_timer.start()
        self._preview_timer.start()

    def _refresh_source_preview(self):
        try:
            src = self._build_source()
        except ValueError as e:
            self._preview_box.setPlainText(f"# 参数不合法：{e}")
            return
        self._preview_box.setPlainText(src)

    def _fill_example(self):
        self._code_edit.setPlainText(
            "for i in range(repeat):\n"
            "    ctx.info(f\"第 {i + 1} 次问候\")\n"
            "greeting = f\"你好，{name}！这是第 {repeat} 次见面。\"\n"
            "return {\"greeting\": greeting, \"repeat\": repeat}")
        self._status.setText("已填入示例逻辑（greet 风格）")

    def _run_live(self):
        """不保存，直接编译执行当前设计的工具。"""
        try:
            meta = self._effective_meta()
            params = self._effective_params()
            src = build_source(meta, params, self._code_edit.toPlainText(),
                               self._ui_layout_or_none())
        except ValueError as e:
            self._live_out.setPlainText(f"[参数不合法] {e}")
            return
        try:
            ns: dict = {"__file__": str(DESIGNER_DIR / f"{meta['tool_id']}.py"),
                        "__name__": f"designer_tools.{meta['tool_id']}"}
            exec(compile(src, f"{meta['tool_id']}.py", "exec"), ns)
        except Exception as e:  # noqa: BLE001 —— 用户代码语法/执行错误
            self._live_out.setPlainText(
                f"⛔ 代码无法执行：{type(e).__name__}: {e}")
            return

        func = ns[meta["tool_id"]]
        values = {p["name"]: p["default"] for p in params}
        ctx = ToolContext(tool_name=meta["tool_id"],
                          logger=logging.getLogger(meta["tool_id"]))
        t0 = time.perf_counter()
        try:
            result = func.run(ctx, **values)
            elapsed = (time.perf_counter() - t0) * 1000
            self._live_out.setPlainText(
                f"✅ {meta['icon']} {meta['name']} 运行成功  "
                f"({elapsed:.0f}ms)\n\n"
                + json.dumps(result, ensure_ascii=False, indent=2, default=str))
            self._status.setText(
                f"运行成功 {elapsed:.0f}ms · 参数 {values}")
        except Exception as e:  # noqa: BLE001 —— 工具逻辑异常展示给用户
            self._live_out.setPlainText(f"⛔ 运行出错：{type(e).__name__}: {e}")

    def _save(self):
        # 未设置过元数据 → 先弹设置对话框；取消则中止保存
        if self._meta is None:
            self._open_settings()
            if self._meta is None:
                return
        meta = self._meta
        try:
            src = build_source(meta, self._effective_params(),
                               self._code_edit.toPlainText(),
                               self._ui_layout_or_none())
        except ValueError as e:
            QMessageBox.warning(self._widget, "参数不合法", str(e))
            return
        try:
            compile(src, f"{meta['tool_id']}.py", "exec")
        except SyntaxError as e:
            QMessageBox.warning(self._widget, "语法错误", f"生成的代码存在语法错误：\n{e}")
            return

        DESIGNER_DIR.mkdir(parents=True, exist_ok=True)
        path = DESIGNER_DIR / f"{meta['tool_id']}.py"
        path.write_text(src, encoding="utf-8")
        self._preview_box.setPlainText(src)

        SignalBus().designer_tool_created.emit(meta["tool_id"])
        self._status.setText(
            f"✅ 已注册到侧边栏「{meta['category']}」→「{meta['name']}」")
        QMessageBox.information(
            self._widget, "已保存",
            f"工具「{meta['name']}」已生成并注册：\n{path}\n"
            f"打开侧边栏的「{meta['category']}」分组即可使用。")

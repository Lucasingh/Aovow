"""
使用教程工具

在图形界面中提供一份内置的上手指南：
- 欢迎介绍
- 登录账号（GitHub OAuth / 注册 / 密码登录）
- 认识界面（侧边栏 / 状态栏 / 全屏 / 最小窗口）
- 扩展：用 AWTF 自己做工具
- 常见问题（启动报错、网络代理等）

实现要点：
- 遵循 BaseTool 模式：tool_id + 懒加载 widget
- 顶部"快速跳转"按钮，点击滚动到对应章节（QScrollArea.ensureWidgetVisible）
- 内容为卡片式章节，暗色主题与全站一致
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

from workstation.tools.base_tool import BaseTool
from workstation.ui.responsive import get_responsive_engine


# ============================================================
# 教程内容（章节数据，便于维护）
# ============================================================

# 每个章节：(锚点id, 图标+标题, [(小标题, 正文HTML), ...])
SECTIONS = [
    {
        "id": "welcome",
        "title": "👋 欢迎使用 Aovow 工作站",
        "blocks": [
            ("",
             "Aovow 工作站是一个<strong style='color:#2dd4a7;'>可扩展的桌面工具平台</strong>。"
             "左侧边栏是所有工具的入口，点击即可切换；底部状态栏实时显示程序运行状态。<br><br>"
             "本教程将带你快速上手——从登录账号、认识界面，到动手做自己的工具。"),
            ("💡 小提示",
             "窗口最小可拖拽到 <strong>900×600</strong>；按 <strong style='color:#fbbf24;'>F11</strong> 可全屏/退出全屏；"
             "所有界面元素会随窗口大小自动缩放。"),
        ],
    },
    {
        "id": "login",
        "title": "① 登录账号（用户中心）",
        "blocks": [
            ("为什么要登录？",
             "账号体系用于保护你的数据与云端功能。点击左侧边栏的<strong>「👤 用户中心」</strong>进入。"),
            ("方式一：GitHub 一键登录（推荐）",
             "点击「使用 GitHub 登录」→ 浏览器自动打开 GitHub 授权页 → 点击 Authorize → "
             "授权成功后浏览器会显示绿色成功页，返回应用即可自动登录。<br>"
             "首次使用 GitHub 登录会自动注册账号，无需填写表单。"),
            ("方式二：用户名 + 密码",
             "点击「注册账号」设置用户名（3-20 位）和密码（6-32 位，需含字母和数字）；"
             "注册成功后用「密码登录」即可。密码使用 bcrypt 加密存储，安全可靠。"),
            ("⚠️ 常见问题",
             "GitHub 登录需要系统代理正常（国内访问 github.com）；若浏览器已显示授权成功但应用没反应，"
             "请稍等几秒，应用会在后台自动完成换取 token；长时间无响应可重试登录。"),
        ],
    },
    {
        "id": "ui",
        "title": "② 认识界面",
        "blocks": [
            ("左侧边栏",
             "工具按分组展示。点击顶部的<strong>折叠/展开按钮</strong>可以收起侧栏（仅显示图标），"
             "动画过程流畅；收起后再次点击即可展开。"),
            ("底部状态栏",
             "实时显示<strong>程序自身</strong>的 CPU 占用率与内存占用：<br>"
             "&nbsp;&nbsp;🟢 绿色 = 占用正常<br>"
             "&nbsp;&nbsp;🟡 黄色 = 占用偏高<br>"
             "&nbsp;&nbsp;🔴 红色 = 占用告警<br>"
             "旁边同时显示系统整体的 CPU / 内存参考值。"),
            ("窗口操作",
             "拖拽窗口边缘可自由调整大小，最小 900×600；<strong>F11</strong> 切换全屏；"
             "窗口位置与大小会自动记住，下次启动恢复。"),
        ],
    },
    {
        "id": "extend",
        "title": "③ 进阶：自己做工具",
        "blocks": [
            ("AWTF —— 写个函数就是一个工具",
             "工作站内置的工具体系支持扩展。配套的 <strong style='color:#2dd4a7;'>AWTF</strong>"
             "（A Work Tool Framework）框架让你用 Python 代码设计自己需要的程序：<br>"
             "&nbsp;&nbsp;• 写一个函数、加个 <code>@tool</code> 装饰器，就是一个工具<br>"
             "&nbsp;&nbsp;• 自动获得参数校验、错误处理、日志、命令行入口<br>"
             "&nbsp;&nbsp;• 三种形态：普通函数 / 工具类 / 异步函数"),
            ("快速体验",
             "框架位于 <code>C:\\Aovow\\awtf</code>，内置《使用指南》：<br>"
             "<code>python -m awtf new 我的工具 --dir my_programs</code><br>"
             "<code>python -m awtf run 我的工具 --discover my_programs</code>"),
        ],
    },
    {
        "id": "faq",
        "title": "④ 常见问题 FAQ",
        "blocks": [
            ("启动报错 No module named 'yaml' / 'psutil' / 'bcrypt'？",
             "这是因为用了系统默认的 Python（3.14，依赖不全）。请用 Anaconda Python 启动：<br>"
             "<code>C:\\Users\\lshen\\anaconda3\\python.exe run.py</code>"),
            ("侧边栏收起/展开时位置错乱？",
             "已在最新版修复（三段式动画 + 防重复点击锁）。若仍遇到，重启应用即可。"),
            ("数据存在哪里？",
             "账号数据在本地 MySQL（aovow_workstation 库）；"
             "应用配置在用户目录 <code>~/.aovow/</code>。"),
            ("更多帮助？",
             "随时在对话中告诉我们你遇到的问题或想要的新工具。"),
        ],
    },
]


class TutorialPanel(QWidget):
    """使用教程主面板"""

    def __init__(self, r, parent=None):
        super().__init__(parent)
        self._r = r
        self._section_anchors: dict[str, QWidget] = {}
        self._scroll: QScrollArea | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(container)
        margin = self._r.spacing(28)
        layout.setContentsMargins(margin, margin, margin, margin)
        layout.setSpacing(self._r.spacing(16))

        # 标题
        title = QLabel("📖 使用教程")
        title.setStyleSheet(
            f"font-size: {self._r.font_size(22)}px; font-weight: bold; color: #e4e4f0;")
        layout.addWidget(title)

        subtitle = QLabel("几分钟快速上手 Aovow 工作站")
        subtitle.setStyleSheet(f"font-size: {self._r.font_size(13)}px; color: #7a7a9e;")
        layout.addWidget(subtitle)
        layout.addSpacing(self._r.spacing(8))

        # 快速跳转
        layout.addWidget(self._build_jump_bar())
        layout.addSpacing(self._r.spacing(8))

        # 章节卡片
        for sec in SECTIONS:
            anchor, card = self._build_section(sec)
            self._section_anchors[sec["id"]] = anchor
            layout.addWidget(card)

        layout.addStretch()

        self._scroll.setWidget(container)
        root.addWidget(self._scroll)

    # ---------- 快速跳转条 ----------

    def _build_jump_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(
            "QFrame { background: #1e1e2e; border: 1px solid #3a3a5c; border-radius: 10px; }")
        h = QHBoxLayout(bar)
        h.setContentsMargins(self._r.spacing(12), self._r.spacing(10),
                             self._r.spacing(12), self._r.spacing(10))
        h.setSpacing(self._r.spacing(8))

        hint = QLabel("快速跳转：")
        hint.setStyleSheet("color: #7a7a9e; font-size: 12px; background: transparent; border: none;")
        h.addWidget(hint)

        labels = [
            ("welcome", "欢迎"), ("login", "登录"), ("ui", "界面"),
            ("extend", "做工具"), ("faq", "FAQ"),
        ]
        fs = self._r.font_size(12)
        for sid, text in labels:
            btn = QPushButton(text)
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            btn.setStyleSheet(
                f"QPushButton {{ background: #2a2a44; color: #c0c0e0; "
                f"border: 1px solid #3a3a5c; border-radius: 8px; "
                f"padding: 6px 14px; font-size: {fs}px; }}"
                f"QPushButton:hover {{ background: #6c5ce7; color: #fff; border-color: #6c5ce7; }}")
            btn.clicked.connect(lambda _=False, s=sid: self._jump_to(s))
            h.addWidget(btn)
        h.addStretch()
        return bar

    def _jump_to(self, section_id: str):
        """滚动到指定章节"""
        target = self._section_anchors.get(section_id)
        if target is not None and self._scroll is not None:
            self._scroll.ensureWidgetVisible(target, 0, 60)

    # ---------- 章节卡片 ----------

    def _build_section(self, sec: dict) -> tuple[QWidget, QWidget]:
        # anchor：卡片顶部的一个不可见锚点，用于定位滚动
        anchor = QWidget()
        anchor.setFixedHeight(1)
        anchor.setStyleSheet("background: transparent;")

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: #1e1e2e; border: 1px solid #3a3a5c; border-radius: 12px; }")
        v = QVBoxLayout(card)
        v.setContentsMargins(self._r.spacing(20), self._r.spacing(18),
                             self._r.spacing(20), self._r.spacing(18))
        v.setSpacing(self._r.spacing(12))

        title = QLabel(sec["title"])
        title.setWordWrap(True)
        title.setStyleSheet(
            f"font-size: {self._r.font_size(16)}px; font-weight: bold; "
            f"color: #a78bfa; background: transparent; border: none;")
        v.addWidget(title)

        for sub_title, body in sec["blocks"]:
            if sub_title:
                st = QLabel(sub_title)
                st.setWordWrap(True)
                st.setStyleSheet(
                    f"font-size: {self._r.font_size(13)}px; font-weight: bold; "
                    f"color: #e4e4f0; background: transparent; border: none; margin-top: 4px;")
                v.addWidget(st)
            body_lbl = QLabel(body)
            body_lbl.setWordWrap(True)
            body_lbl.setTextFormat(Qt.TextFormat.RichText)
            body_lbl.setStyleSheet(
                f"font-size: {self._r.font_size(12)}px; color: #a0a0c0; "
                f"line-height: 170%; background: transparent; border: none;")
            body_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            v.addWidget(body_lbl)

        # 用一个垂直容器把 anchor + card 组合（anchor 在卡片上方）
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        wv = QVBoxLayout(wrapper)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(0)
        wv.addWidget(anchor)
        wv.addWidget(card)
        return anchor, wrapper


class TutorialTool(BaseTool):
    """使用教程工具"""

    tool_id = "tutorial"
    name = "使用教程"
    icon = "📖"
    category = "系统"
    description = "工作站上手指南与常见问题"

    def __init__(self):
        self._widget: QWidget | None = None
        self._r = get_responsive_engine()

    @property
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._build_ui()
        return self._widget

    def _build_ui(self) -> QWidget:
        self._r = get_responsive_engine()
        return TutorialPanel(self._r)

    def on_activate(self):
        """切换到本工具时滚动回顶部"""
        if self._widget is not None:
            panel = self._widget
            scroll = panel.findChild(QScrollArea)
            if scroll is not None:
                scroll.verticalScrollBar().setValue(0)

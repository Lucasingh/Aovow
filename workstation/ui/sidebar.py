"""
侧边导航栏 — 现代化设计

特性：
- 品牌头部区域（Logo + 应用名）
- 按分类分组展示工具，分类标题用小号大写字母
- 激活态：左侧紫色指示条 + 半透明背景
- 悬停态：背景渐变
- 展开/收起动画（宽度过渡）
- 响应式宽度自动适配
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QScrollArea,
    QSizePolicy, QFrame, QGraphicsOpacityEffect
)
from PySide6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QVariantAnimation, QTimer
)

from workstation.tools.registry import ToolRegistry
from workstation.core.signals import SignalBus
from workstation.ui.responsive import ResponsiveEngine


class SidebarWidget(QWidget):
    """侧边导航栏"""

    def __init__(self, signals: SignalBus, tool_registry: ToolRegistry,
                 responsive: ResponsiveEngine, parent=None):
        super().__init__(parent)
        self._signals = signals
        self._registry = tool_registry
        self._responsive = responsive
        self._expanded = True
        self._active_tool_id: str = ""
        self._tool_buttons: dict = {}

        self._setup_ui()
        self._update_widths()
        self._connect_signals()

    def _setup_ui(self):
        """构建侧边栏 UI"""
        self.setObjectName("sidebarFrame")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 8)
        self._layout.setSpacing(0)

        # ---- 品牌头部 ----
        self._header = QLabel("  AOVOW")
        self._header.setObjectName("sidebarHeader")
        self._layout.addWidget(self._header)

        # 分割线
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #2a2a44; border: none;")
        self._layout.addWidget(sep)

        # 间距
        spacer_top = QFrame()
        spacer_top.setFixedHeight(8)
        spacer_top.setStyleSheet("background: transparent;")
        self._layout.addWidget(spacer_top)

        # ---- 滚动区域 ----
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._content_widget = QWidget()
        self._content_widget.setStyleSheet("background: transparent;")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)

        self._scroll_area.setWidget(self._content_widget)
        self._layout.addWidget(self._scroll_area, 1)

    def _update_widths(self):
        """从响应式引擎获取当前尺寸"""
        self._expanded_width = self._responsive.sidebar_width()
        self._collapsed_width = self._responsive.sidebar_collapsed_width()
        if self._expanded:
            self.setFixedWidth(self._expanded_width)

    def _connect_signals(self):
        self._signals.sidebar_toggled.connect(self._on_toggle)
        self._signals.tool_registered.connect(self._on_tool_registered)
        self._signals.tool_activated.connect(self._on_tool_activated)
        self._signals.app_started.connect(self._refresh_tools)
        self._signals.responsive_changed.connect(self._on_responsive_changed)

    def _on_responsive_changed(self):
        """响应式更新"""
        self._update_widths()
        if self._expanded:
            self.setFixedWidth(self._expanded_width)
        else:
            self.setFixedWidth(self._collapsed_width)

    def refresh_tools(self):
        """刷新工具列表"""
        # 清除旧内容
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._tool_buttons.clear()

        categories = self._registry.get_categories()

        if not categories:
            empty_label = QLabel("暂无工具")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_label.setStyleSheet("color: #7a7a9e; font-size: 11px; padding: 20px;")
            self._content_layout.addWidget(empty_label)
            self._content_layout.addStretch()
            return

        for category, tools in categories.items():
            # 分类标题
            cat_label = QLabel(f"  {category.upper()}")
            cat_label.setObjectName("sidebarCategory")
            self._content_layout.addWidget(cat_label)

            # 工具按钮
            for tool in tools:
                btn = QPushButton(f"  {tool.icon}    {tool.name}")
                btn.setObjectName("sidebarItem")
                btn.setToolTip(tool.description or tool.name)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setCheckable(True)
                tool_id = tool.tool_id
                btn.clicked.connect(
                    lambda checked, tid=tool_id: self._signals.tool_activated.emit(tid)
                )
                self._tool_buttons[tool_id] = btn
                self._content_layout.addWidget(btn)

            # 分类间间距
            cat_spacer = QFrame()
            cat_spacer.setFixedHeight(8)
            cat_spacer.setStyleSheet("background: transparent;")
            self._content_layout.addWidget(cat_spacer)

        self._content_layout.addStretch()

    def _refresh_tools(self):
        self.refresh_tools()

    def _on_tool_registered(self, tool_id: str):
        self.refresh_tools()

    def _on_tool_activated(self, tool_id: str):
        if self._active_tool_id and self._active_tool_id in self._tool_buttons:
            self._tool_buttons[self._active_tool_id].setChecked(False)
        if tool_id in self._tool_buttons:
            self._tool_buttons[tool_id].setChecked(True)
        self._active_tool_id = tool_id

    def _on_toggle(self, _=None):
        """切换展开/收起，带宽度过渡 + 内容淡入淡出"""
        if hasattr(self, '_animating') and self._animating:
            return  # 动画进行中，忽略重复点击

        self._animating = True
        self._expanded = not self._expanded
        target_width = (self._expanded_width if self._expanded
                        else self._collapsed_width)
        start_width = self.width()

        # 内容透明度效果
        content = self._content_widget
        opacity_effect = QGraphicsOpacityEffect(content)
        content.setGraphicsEffect(opacity_effect)
        opacity_effect.setOpacity(1.0)

        # 阶段1：淡出当前内容
        fade_out = QPropertyAnimation(opacity_effect, b"opacity")
        fade_out.setDuration(120)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve(QEasingCurve.Type.InQuad))

        # 阶段2：切换内容 + 宽度动画
        def on_fade_out_done():
            if not self._expanded:
                self._set_icon_only_mode(True)
                self._header.hide()
            else:
                self._set_icon_only_mode(False)
                self._header.show()

            # 宽度动画
            width_anim = QVariantAnimation()
            width_anim.setDuration(250)
            width_anim.setStartValue(start_width)
            width_anim.setEndValue(target_width)
            width_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
            width_anim.valueChanged.connect(lambda v: self.setFixedWidth(int(v)))

            # 阶段3：宽度完成后淡入
            def on_width_done():
                fade_in = QPropertyAnimation(opacity_effect, b"opacity")
                fade_in.setDuration(120)
                fade_in.setStartValue(0.0)
                fade_in.setEndValue(1.0)
                fade_in.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutQuad))
                fade_in.finished.connect(self._on_anim_complete)
                self._fade_in_anim = fade_in  # 防 GC
                fade_in.start()

            width_anim.finished.connect(on_width_done)
            self._width_anim = width_anim  # 防 GC
            width_anim.start()

        fade_out.finished.connect(on_fade_out_done)

        # 保持引用防止被 GC
        self._fade_out_anim = fade_out
        self._opacity_effect = opacity_effect

        fade_out.start()

    def _on_anim_complete(self):
        """动画全部完成"""
        self._animating = False
        # 移除透明效果（避免影响日常渲染性能）
        self._content_widget.setGraphicsEffect(None)

    def _start_width_anim(self, start_w: int, target_w: int):
        """启动宽度动画"""
        width_anim = QVariantAnimation()
        width_anim.setDuration(250)
        width_anim.setStartValue(start_w)
        width_anim.setEndValue(target_w)
        width_anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
        width_anim.valueChanged.connect(lambda v: self.setFixedWidth(int(v)))
        self._width_anim = width_anim  # 防 GC
        width_anim.start()

    def _set_icon_only_mode(self, icon_only: bool):
        """切换图标/完整模式"""
        # 分类标题：收起时隐藏
        for i in range(self._content_layout.count()):
            widget = self._content_layout.itemAt(i).widget()
            if widget and widget.objectName() == "sidebarCategory":
                widget.setVisible(not icon_only)

        # 工具按钮：收起时只显示图标
        for tool_id, btn in self._tool_buttons.items():
            if icon_only:
                tool = next((t for t in self._registry.list_all()
                             if t.tool_id == tool_id), None)
                if tool:
                    btn.setText(f"  {tool.icon}")
            else:
                tool = next((t for t in self._registry.list_all()
                             if t.tool_id == tool_id), None)
                if tool:
                    btn.setText(f"  {tool.icon}    {tool.name}")

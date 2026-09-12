"""
顶部工具栏 — 现代化设计

布局结构：
  [侧栏切换] | Aovow Workstation | ←弹性空间→ [搜索框] [设置]

特性：
- 品牌区：应用名 + 图标
- 搜索框：圆角、聚焦高亮、防抖
- 工具按钮：透明背景、悬停高亮
- 响应式：随窗口缩放调整尺寸
"""

from PySide6.QtWidgets import (
    QToolBar, QPushButton, QLabel, QLineEdit, QWidget, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer

from workstation.core.signals import SignalBus
from workstation.animation.manager import AnimationManager
from workstation.ui.responsive import ResponsiveEngine


class MainToolbar(QToolBar):
    """主工具栏"""

    def __init__(self, signals: SignalBus, animation_manager: AnimationManager,
                 responsive: ResponsiveEngine, parent=None):
        super().__init__("主工具栏", parent)
        self._signals = signals
        self._anim = animation_manager
        self._responsive = responsive

        self.setObjectName("mainToolbar")
        self.setMovable(False)
        self.setFloatable(False)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """构建工具栏 UI"""
        btn_size = self._responsive.scaled_int(34)
        search_width = self._responsive.scaled_int(220)
        icon_fs = self._responsive.font_size(16)
        title_fs = self._responsive.font_size(14)
        search_fs = self._responsive.font_size(12)

        # ---- 左侧：侧边栏切换 ----
        self._btn_toggle_sidebar = QPushButton("☰")
        self._btn_toggle_sidebar.setObjectName("toolBtn")
        self._btn_toggle_sidebar.setToolTip("切换侧边栏 (Ctrl+B)")
        self._btn_toggle_sidebar.setFixedSize(btn_size, btn_size)
        self._btn_toggle_sidebar.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_toggle_sidebar.setStyleSheet(
            f"QPushButton#toolBtn {{ font-size: {icon_fs}px; }}"
        )
        self.addWidget(self._btn_toggle_sidebar)

        # ---- 品牌区：Logo + 应用名 ----
        self._lbl_brand = QLabel("◆  Aovow")
        self._lbl_brand.setStyleSheet(
            f"color: #f0f0fa; font-size: {title_fs}px; font-weight: bold; "
            f"padding: 0 12px 0 4px; letter-spacing: 0.5px;"
        )
        self.addWidget(self._lbl_brand)

        # 分隔线
        self.addSeparator()

        # ---- 弹性空间 ----
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Expanding)
        self.addWidget(spacer)

        # ---- 右侧：搜索框 ----
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  搜索工具...")
        self._search_input.setFixedWidth(search_width)
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setStyleSheet(
            f"QLineEdit {{ background-color: #161624; border: 1px solid #2a2a44; "
            f"border-radius: 17px; padding: 6px 14px; font-size: {search_fs}px; "
            f"color: #f0f0fa; }}"
            f"QLineEdit:focus {{ border-color: #7c6cff; background-color: #1e1e30; }}"
            f"QLineEdit::placeholder {{ color: #7a7a9e; }}"
        )

        # 搜索防抖
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._on_search)
        self._search_input.textChanged.connect(lambda: self._search_timer.start(200))

        self.addWidget(self._search_input)

        # 间距
        gap = QWidget()
        gap.setFixedWidth(8)
        self.addWidget(gap)

        # ---- 设置按钮 ----
        self._btn_settings = QPushButton("⚙")
        self._btn_settings.setObjectName("toolBtn")
        self._btn_settings.setToolTip("设置")
        self._btn_settings.setFixedSize(btn_size, btn_size)
        self._btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_settings.setStyleSheet(
            f"QPushButton#toolBtn {{ font-size: {icon_fs}px; }}"
        )
        self.addWidget(self._btn_settings)

    def _connect_signals(self):
        self._btn_toggle_sidebar.clicked.connect(self._on_toggle_sidebar)
        self._btn_settings.clicked.connect(
            lambda: self._signals.status_message.emit("设置功能待实现", 3000))

    def _on_toggle_sidebar(self):
        self._signals.sidebar_toggled.emit(True)

    def _on_search(self):
        keyword = self._search_input.text().strip()
        if keyword:
            self._signals.navigation_changed.emit(f"search:{keyword}")

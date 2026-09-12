"""
内容展示区

通过 QStackedWidget 管理已加载的工具页面，
支持平滑切换动画和懒加载。
"""

from PySide6.QtWidgets import (
    QWidget, QStackedWidget, QVBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt

from workstation.tools.registry import ToolRegistry
from workstation.core.signals import SignalBus
from workstation.animation.manager import AnimationManager


class ContentArea(QFrame):
    """
    主内容展示区域。

    使用 QStackedWidget 管理多个工具页面，
    每个工具页面在首次激活时懒加载创建。
    """

    def __init__(self, signals: SignalBus, tool_registry: ToolRegistry,
                 animation_manager: AnimationManager, parent=None):
        super().__init__(parent)
        self._signals = signals
        self._registry = tool_registry
        self._anim = animation_manager

        self.setObjectName("contentFrame")
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """构建内容区 UI"""
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # QStackedWidget 管理页面
        self._stack = QStackedWidget()
        self._stack.setObjectName("toolContainer")
        self._layout.addWidget(self._stack)

        # 第一个页面: 欢迎页
        self._welcome_page = self._create_welcome_page()
        self._stack.addWidget(self._welcome_page)

        # 工具页面映射: {tool_id: page_index}
        self._tool_pages: dict = {}
        self._current_tool_id: str = ""

    def _create_welcome_page(self) -> QWidget:
        """创建欢迎页面"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo 图标
        logo = QLabel("◆")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet(
            "font-size: 64px; color: #7c6cff; margin-bottom: 16px; "
            "font-weight: bold;"
        )

        title = QLabel("Aovow Workstation")
        title.setObjectName("emptyStateTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("可扩展的 Python 工作站框架")
        subtitle.setObjectName("emptyStateSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            "color: #b8b8d4; font-size: 14px; margin-top: 8px;"
        )

        hint = QLabel("💡 从左侧导航栏选择工具，或使用顶部搜索栏快速查找")
        hint.setStyleSheet(
            "color: #7a7a9e; font-size: 12px; margin-top: 24px;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(3)
        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(hint)
        layout.addStretch(4)

        return page

    def _connect_signals(self):
        """连接信号"""
        self._signals.tool_activated.connect(self._on_tool_activated)

    def _on_tool_activated(self, tool_id: str):
        """工具被激活时切换页面"""
        if tool_id == self._current_tool_id:
            return

        # 获取工具实例（懒加载）
        tool = self._registry.get(tool_id)
        if tool is None:
            return

        # 首次加载：添加到 stack
        if tool_id not in self._tool_pages:
            widget = tool.widget
            index = self._stack.addWidget(widget)
            self._tool_pages[tool_id] = index

        # 执行切换动画
        target_index = self._tool_pages[tool_id]
        current_widget = self._stack.currentWidget()

        if self._anim.enabled and current_widget:
            # 使用动画管理器进行页面切换
            target_widget = self._stack.widget(target_index)
            self._anim.page_transition(
                current_widget, target_widget,
                direction="right", duration=300,
                callback=lambda: self._stack.setCurrentIndex(target_index)
            )
        else:
            self._stack.setCurrentIndex(target_index)

        self._current_tool_id = tool_id

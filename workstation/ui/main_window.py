"""
主窗口

整合工具栏、侧边栏、内容区和状态栏，
统一管理窗口布局、全局快捷键和响应式缩放。

响应式机制：
    resizeEvent 触发时，通过 ResponsiveEngine 计算新的缩放因子，
    然后重建全局 QSS 样式表并更新各组件的固定尺寸。
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut

from workstation.core.signals import SignalBus
from workstation.animation.manager import AnimationManager
from workstation.tools.registry import ToolRegistry
from workstation.config.settings import ConfigManager
from workstation.utils.performance import PerformanceMonitor

from .styles import build_stylesheet
from .responsive import get_responsive_engine
from .toolbar import MainToolbar
from .sidebar import SidebarWidget
from .content_area import ContentArea
from .status_bar import AppStatusBar


class MainWindow(QMainWindow):
    """
    应用主窗口。

    布局结构:
    ┌─────────────────────────────────────┐
    │           MainToolbar               │
    ├────────┬────────────────────────────┤
    │        │                            │
    │Sidebar │       ContentArea          │
    │        │                            │
    ├────────┴────────────────────────────┤
    │           AppStatusBar              │
    └─────────────────────────────────────┘

    响应式：窗口缩放时所有 UI 尺寸按比例自动调整。
    """

    def __init__(self, signals: SignalBus, animation_manager: AnimationManager,
                 tool_registry: ToolRegistry, config_manager: ConfigManager):
        super().__init__()
        self._signals = signals
        self._anim = animation_manager
        self._registry = tool_registry
        self._config = config_manager
        self._responsive = get_responsive_engine()

        # 响应式防抖定时器（避免 resize 时频繁重建样式）
        # 必须在 _setup_window() 之前创建：showMaximized() 会触发 resizeEvent，
        # 而 resizeEvent 依赖此定时器，否则 AttributeError。
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(80)  # 80ms 防抖
        self._resize_timer.timeout.connect(self._on_resize_debounced)

        # 窗口基础设置
        self._setup_window()

        # 应用初始样式
        self._apply_theme()

        # 构建 UI 组件
        self._setup_ui()

        # 连接信号
        self._connect_signals()

        # 性能监控
        self._setup_performance()

    # ========== 窗口设置 ==========

    def _setup_window(self):
        """配置窗口属性"""
        self.setWindowTitle(f"{self._config.get('app.name', 'Aovow Workstation')} "
                           f"v{self._config.get('app.version', '1.0.0')}")

        w = self._config.get("window.width", 1280)
        h = self._config.get("window.height", 800)
        # 最小尺寸：基于字体可读性，sm 断点 (≥900px) 时 scale=0.88，最小字号约 10px
        min_w = self._config.get("window.min_width", 900)
        min_h = self._config.get("window.min_height", 600)
        self.resize(w, h)
        self.setMinimumSize(min_w, min_h)

        if self._config.get("window.maximized", False):
            self.showMaximized()

        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """注册全局快捷键"""
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(
            lambda: self._signals.sidebar_toggled.emit(True)
        )
        QShortcut(QKeySequence("Ctrl+Q"), self).activated.connect(self.close)
        QShortcut(QKeySequence("F11"), self).activated.connect(
            lambda: self.showNormal() if self.isFullScreen() else self.showFullScreen()
        )

    def _apply_theme(self):
        """应用全局主题样式 — 强制刷新确保字体等变化生效"""
        stylesheet = build_stylesheet(self._responsive.get_sizes())
        app = QApplication.instance()
        # 清空再设置，强制 Qt 全量重新解析 QSS
        app.setStyleSheet("")
        app.setStyleSheet(stylesheet)

    # ========== UI 构建 ==========

    def _setup_ui(self):
        """构建主界面布局"""
        self._central = QWidget()
        self.setCentralWidget(self._central)

        root_layout = QVBoxLayout(self._central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. 工具栏
        self._toolbar = MainToolbar(self._signals, self._anim, self._responsive)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._toolbar)

        # 2. 中间区域：侧边栏 + 内容区
        body_widget = QWidget()
        body_layout = QHBoxLayout(body_widget)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # 2a. 侧边栏
        self._sidebar = SidebarWidget(self._signals, self._registry, self._responsive)

        # 2b. 内容区
        self._content_area = ContentArea(self._signals, self._registry, self._anim)

        body_layout.addWidget(self._sidebar)
        body_layout.addWidget(self._content_area, 1)

        root_layout.addWidget(body_widget, 1)

        # 3. 状态栏
        self._status_bar = AppStatusBar(self._signals, self._responsive)
        self.setStatusBar(self._status_bar)

    # ========== 信号连接 ==========

    def _connect_signals(self):
        pass

    # ========== 性能监控 ==========

    def _setup_performance(self):
        """启动性能监控——始终启用，状态栏需要显示指标"""
        self._perf_monitor = PerformanceMonitor(
            interval=self._config.get("performance.memory_monitor_interval", 3000)
        )
        self._perf_monitor.performance_updated.connect(self._on_performance_update)
        self._perf_monitor.start()

        # FPS 监控单独按配置控制
        if self._config.get("performance.fps_monitor_enabled", False):
            self._fps_clock = QTimer()
            self._fps_clock.timeout.connect(self._perf_monitor.tick_frame)
            self._fps_clock.start(16)

    def _on_performance_update(self, metrics):
        self._status_bar.update_performance(metrics)

    # ========== 事件处理 ==========

    def closeEvent(self, event):
        if self._config.get("window.remember_geometry", True):
            self._config.set("window.width", self.width())
            self._config.set("window.height", self.height())
            self._config.set("window.maximized", self.isMaximized())
            self._config.save()

        self._registry.shutdown()
        event.accept()

    def resizeEvent(self, event):
        """窗口大小调整 — 防抖后触发响应式更新"""
        super().resizeEvent(event)
        # 防抖：80ms 内连续 resize 只触发一次
        self._resize_timer.start()

    def _on_resize_debounced(self):
        """防抖后的响应式更新"""
        # 通知响应式引擎更新尺寸
        changed = self._responsive.update(self.width(), self.height())
        if not changed:
            return

        # 重建全局样式
        self._apply_theme()

        # 通知子组件更新尺寸
        self._signals.responsive_changed.emit()

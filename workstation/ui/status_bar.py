"""
底部状态指示区 — 现代化设计

展示内容：
- 左侧：状态消息 / 当前工具名
- 右侧：性能指标（线程/CPU/内存），带语义色

特性：
- 响应式高度和字体
- 性能指标根据数值变化颜色（CPU>80% 变红）
- 不重建控件，只更新样式
"""

from PySide6.QtWidgets import (
    QStatusBar, QLabel, QHBoxLayout, QWidget, QFrame
)
from PySide6.QtCore import Qt, QTimer

from workstation.core.signals import SignalBus
from workstation.ui.responsive import ResponsiveEngine


class AppStatusBar(QStatusBar):
    """应用状态栏"""

    def __init__(self, signals: SignalBus, responsive: ResponsiveEngine,
                 parent=None):
        super().__init__(parent)
        self._signals = signals
        self._responsive = responsive

        self.setObjectName("appStatusBar")
        self._update_height()

        self._setup_ui()
        self._connect_signals()

        self._message_timer = QTimer()
        self._message_timer.setSingleShot(True)
        self._message_timer.timeout.connect(lambda: self.showMessage("", 0))

    def _update_height(self):
        self.setFixedHeight(self._responsive.status_bar_height())

    def _setup_ui(self):
        fs = self._responsive.font_size(11)
        self._apply_style(fs)

        # 右侧性能指示器容器（只创建一次）
        self._perf_container = QWidget()
        self._perf_container.setObjectName("perfContainer")
        perf_layout = QHBoxLayout(self._perf_container)
        perf_layout.setContentsMargins(0, 0, 12, 0)
        perf_layout.setSpacing(self._responsive.spacing(16))

        self._lbl_threads = QLabel("🧵 --")
        self._lbl_threads.setObjectName("perfLabel")
        perf_layout.addWidget(self._lbl_threads)

        self._lbl_app_cpu = QLabel("App ⚡ --%")
        self._lbl_app_cpu.setObjectName("perfLabel")
        perf_layout.addWidget(self._lbl_app_cpu)

        self._lbl_sys_cpu = QLabel("Sys 🔧 --%")
        self._lbl_sys_cpu.setObjectName("perfLabel")
        perf_layout.addWidget(self._lbl_sys_cpu)

        self._lbl_mem = QLabel("💾 -- MB")
        self._lbl_mem.setObjectName("perfLabel")
        perf_layout.addWidget(self._lbl_mem)

        # 分割线
        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet("background-color: #2a2a44;")
        perf_layout.addWidget(sep)

        # 版本标识
        self._lbl_version = QLabel("v1.0")
        self._lbl_version.setStyleSheet(f"color: #4a4a68; font-size: {fs}px;")
        perf_layout.addWidget(self._lbl_version)

        self.addPermanentWidget(self._perf_container)

    def _apply_style(self, fs: int):
        self.setStyleSheet(
            f"QStatusBar {{ background-color: #10101e; color: #7a7a9e; "
            f"border-top: 1px solid #2a2a44; font-size: {fs}px; }}"
            f"QStatusBar::item {{ border: none; }}"
        )

    def _connect_signals(self):
        self._signals.status_message.connect(self._show_message)
        self._signals.tool_activated.connect(self._on_tool_activated)
        self._signals.responsive_changed.connect(self._on_responsive)

    def _on_responsive(self):
        """响应式更新"""
        self._update_height()
        fs = self._responsive.font_size(11)
        self._apply_style(fs)

    def _show_message(self, message: str, duration: int = 3000):
        self.showMessage(message, duration)

    def _on_tool_activated(self, tool_id: str):
        self._signals.status_message.emit(f"已切换到: {tool_id}", 2000)

    def update_performance(self, metrics):
        """更新性能指标，根据数值动态着色"""
        fs = self._responsive.font_size(11)

        # 线程数
        self._lbl_threads.setText(f"🧵 {metrics.thread_count}")

        # 进程 CPU
        app_cpu = metrics.cpu_percent
        app_color = "#f87171" if app_cpu > 80 else ("#fbbf24" if app_cpu > 50 else "#2dd4a7")
        self._lbl_app_cpu.setText(f"App ⚡ {app_cpu:.0f}%")
        self._lbl_app_cpu.setStyleSheet(f"color: {app_color}; font-size: {fs}px;")

        # 系统 CPU
        sys_cpu = metrics.system_cpu_percent
        sys_color = "#f87171" if sys_cpu > 80 else ("#fbbf24" if sys_cpu > 50 else "#b8b8d4")
        self._lbl_sys_cpu.setText(f"Sys 🔧 {sys_cpu:.0f}%")
        self._lbl_sys_cpu.setStyleSheet(f"color: {sys_color}; font-size: {fs}px;")

        # 内存
        mem_val = metrics.memory_mb
        mem_color = "#f87171" if mem_val > 500 else ("#fbbf24" if mem_val > 200 else "#b8b8d4")
        self._lbl_mem.setText(f"💾 {mem_val:.0f} MB")
        self._lbl_mem.setStyleSheet(f"color: {mem_color}; font-size: {fs}px;")

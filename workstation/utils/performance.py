"""
性能监控模块

提供运行时性能指标采集，包括：
- 启动时间
- 内存使用
- CPU 使用率
- FPS（界面帧率）
- 操作响应延迟
"""

import time
import os
import sys
import threading
import psutil
from typing import Dict, Optional, Callable
from dataclasses import dataclass, field

from PySide6.QtCore import QObject, QTimer, Signal


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    timestamp: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0          # 进程 CPU 使用率
    system_cpu_percent: float = 0.0   # 系统 CPU 使用率
    thread_count: int = 0
    fps: float = 0.0
    avg_response_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "memory_mb": round(self.memory_mb, 2),
            "memory_percent": round(self.memory_percent, 1),
            "cpu_percent": round(self.cpu_percent, 1),
            "system_cpu_percent": round(self.system_cpu_percent, 1),
            "thread_count": self.thread_count,
            "fps": round(self.fps, 1) if self.fps > 0 else None,
            "avg_response_ms": round(self.avg_response_ms, 2),
        }


class PerformanceMonitor(QObject):
    """
    性能监控器。

    定时采集系统资源使用数据并通过信号广播。

    使用方式:
        monitor = PerformanceMonitor(interval=3000)
        monitor.performance_updated.connect(handler)
        monitor.start()
    """

    performance_updated = Signal(PerformanceMetrics)
    """性能数据更新信号"""

    def __init__(self, interval: int = 3000, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._interval = interval
        self._process = psutil.Process(os.getpid())
        self._timer: Optional[QTimer] = None
        self._metrics_history: list = []
        self._start_time: Optional[float] = None

        # FPS 相关
        self._frame_count = 0
        self._fps_timer: Optional[QTimer] = None
        self._fps = 0.0

        # 响应延迟追踪
        self._response_times: list = []
        self._max_response_samples = 50

    def start(self):
        """启动性能监控"""
        self._start_time = time.perf_counter()

        # 预热 cpu_percent（首次调用返回 0，丢弃）
        self._process.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None)

        # 资源监控定时器
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._collect_metrics)
        self._timer.start(self._interval)

        # FPS 监控定时器
        self._fps_timer = QTimer(self)
        self._fps_timer.timeout.connect(self._update_fps)
        self._fps_timer.start(1000)  # 每秒计算一次

        self._collect_metrics()  # 立即采集一次

    def stop(self):
        """停止性能监控"""
        if self._timer:
            self._timer.stop()
        if self._fps_timer:
            self._fps_timer.stop()

    def tick_frame(self):
        """每帧调用一次（用于 FPS 计算）"""
        self._frame_count += 1

    def record_response_time(self, ms: float):
        """记录一次操作响应时间"""
        self._response_times.append(ms)
        if len(self._response_times) > self._max_response_samples:
            self._response_times.pop(0)

    def get_avg_response_time(self) -> float:
        """获取平均响应时间"""
        if not self._response_times:
            return 0.0
        return sum(self._response_times) / len(self._response_times)

    def get_startup_time_ms(self) -> float:
        """获取启动耗时(ms)"""
        if self._start_time:
            return (time.perf_counter() - self._start_time) * 1000
        return 0.0

    def get_current_metrics(self) -> PerformanceMetrics:
        """获取当前性能快照"""
        return self._collect_snapshot()

    def _collect_metrics(self):
        """采集并广播性能指标"""
        metrics = self._collect_snapshot()
        self._metrics_history.append(metrics)
        # 只保留最近 100 条
        if len(self._metrics_history) > 100:
            self._metrics_history.pop(0)
        self.performance_updated.emit(metrics)

    def _collect_snapshot(self) -> PerformanceMetrics:
        """采集当前性能快照"""
        try:
            mem_info = self._process.memory_info()
            memory_mb = mem_info.rss / (1024 * 1024)
            memory_percent = self._process.memory_percent()
            # interval=None 非阻塞，首次返回 0，之后返回自上次调用以来的使用率
            cpu_percent = self._process.cpu_percent(interval=None)
            system_cpu = psutil.cpu_percent(interval=None)
            thread_count = self._process.num_threads()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            memory_mb = 0.0
            memory_percent = 0.0
            cpu_percent = 0.0
            system_cpu = 0.0
            thread_count = 0

        return PerformanceMetrics(
            timestamp=time.time(),
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            cpu_percent=cpu_percent,
            system_cpu_percent=system_cpu,
            thread_count=thread_count,
            fps=self._fps,
            avg_response_ms=self.get_avg_response_time(),
        )

    def _update_fps(self):
        """更新 FPS"""
        self._fps = self._frame_count
        self._frame_count = 0

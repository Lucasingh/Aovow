"""
基础服务管理器

管理应用级别的共享服务，如线程池、日志服务、性能监控等。
所有服务遵循懒加载原则，仅在首次访问时初始化。
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Any, Dict, Callable, Optional
import os

logger = logging.getLogger(__name__)


class ServiceManager:
    """
    管理全局共享服务实例。

    支持的服务类型：
    - thread_pool: 线程池（用于I/O密集型任务）
    - process_pool: 进程池（用于CPU密集型任务）
    - logger: 统一日志服务

    设计原则：懒加载 + 单例
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._services: Dict[str, Any] = {}
            self._factory: Dict[str, Callable] = {
                'thread_pool': self._create_thread_pool,
                'process_pool': self._create_process_pool,
            }

    def get(self, name: str) -> Optional[Any]:
        """懒加载获取服务实例"""
        if name not in self._services:
            factory = self._factory.get(name)
            if factory:
                self._services[name] = factory()
            else:
                logger.warning(f"未知服务类型: {name}")
        return self._services.get(name)

    def register(self, name: str, factory: Callable):
        """注册自定义服务工厂"""
        self._factory[name] = factory

    def _create_thread_pool(self) -> ThreadPoolExecutor:
        """创建线程池，大小为 CPU 核心数的 2 倍"""
        cpu_count = os.cpu_count() or 4
        max_workers = min(cpu_count * 2, 32)
        return ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="aovow-worker"
        )

    def _create_process_pool(self) -> ProcessPoolExecutor:
        """创建进程池，用于 CPU 密集型计算"""
        cpu_count = os.cpu_count() or 4
        return ProcessPoolExecutor(
            max_workers=max(1, cpu_count - 1)
        )

    def shutdown(self):
        """关闭所有服务，释放资源"""
        for name, service in self._services.items():
            if hasattr(service, 'shutdown'):
                try:
                    service.shutdown(wait=False)
                except Exception as e:
                    logger.error(f"关闭服务 {name} 失败: {e}")
        self._services.clear()

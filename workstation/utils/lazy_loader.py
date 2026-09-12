"""
懒加载工具

提供惰性导入装饰器和代理类，
推迟模块/类的实际加载时间。
"""

import importlib
import threading
from typing import Any, Callable, Dict, Optional


class LazyLoader:
    """
    懒加载代理。

    延迟导入模块，仅在首次访问属性时才实际加载。
    减少应用启动时间。

    使用方式:
        heavy_module = LazyLoader("numpy")
        result = np.array([1, 2, 3])  # 此时才实际导入

    或作为装饰器:
        @lazy_import("heavy_module.Class")
        class MyWrapper:
            pass
    """

    def __init__(self, module_name: str, class_name: Optional[str] = None):
        self._module_name = module_name
        self._class_name = class_name
        self._module = None
        self._lock = threading.Lock()

    def _load(self):
        """实际加载模块"""
        if self._module is None:
            with self._lock:
                if self._module is None:  # 双重检查
                    self._module = importlib.import_module(self._module_name)
        return self._module

    def __getattr__(self, name: str) -> Any:
        module = self._load()
        return getattr(module, name)

    def __call__(self, *args, **kwargs) -> Any:
        """当懒加载的是类时，支持实例化"""
        if self._class_name:
            module = self._load()
            cls = getattr(module, self._class_name)
            return cls(*args, **kwargs)
        raise TypeError("LazyLoader 不可直接调用，除非指定了 class_name")

    def __repr__(self):
        if self._module is None:
            return f"<LazyLoader: {self._module_name}>"
        return f"<LazyLoader: {self._module_name} (loaded)>"


class ResourceCache:
    """
    资源缓存管理器。

    缓存已加载的控件/数据，支持 LRU 淘汰策略，
    减少重复创建和内存占用。
    """

    def __init__(self, max_size: int = 50):
        self._cache: Dict[str, Any] = {}
        self._max_size = max_size
        self._access_order: list = []
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """获取缓存项"""
        with self._lock:
            if key in self._cache:
                # 更新访问顺序
                self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
        return None

    def put(self, key: str, value: Any):
        """存入缓存"""
        with self._lock:
            if key in self._cache:
                self._access_order.remove(key)
            elif len(self._cache) >= self._max_size:
                # 淘汰最久未使用的
                oldest = self._access_order.pop(0)
                del self._cache[oldest]
            self._cache[key] = value
            self._access_order.append(key)

    def remove(self, key: str):
        """移除缓存项"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._access_order.remove(key)

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def __len__(self) -> int:
        return len(self._cache)

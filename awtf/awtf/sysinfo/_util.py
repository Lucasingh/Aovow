"""
sysinfo 公共工具：psutil 可选探测、字节格式化、平台判断。

设计原则：
- **零第三方依赖**：psutil 只在已安装时用于增强数据；否则自动降级为标准库实现。
- 所有返回值都是 JSON 安全的基础类型（str/int/float/bool/None），可直接序列化。
"""

from __future__ import annotations

import importlib.util
from typing import Any, Dict, Optional

# psutil 是否可用（可选增强）
PSUTIL_AVAILABLE = importlib.util.find_spec("psutil") is not None


def get_psutil():
    """惰性导入 psutil；未安装返回 None。"""
    if not PSUTIL_AVAILABLE:
        return None
    import psutil  # 局部导入，避免模块级强依赖

    return psutil


def format_bytes(num: float) -> str:
    """字节数转人类可读字符串，如 ``1.5 GB``。"""
    if num is None or num < 0:
        return "0 B"
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    value = float(num)
    i = 0
    while value >= 1024 and i < len(units) - 1:
        value /= 1024
        i += 1
    if i == 0:
        return f"{int(value)} {units[i]}"
    return f"{value:.1f} {units[i]}"


def safe_dict(**kwargs: Any) -> Dict[str, Any]:
    """构建字段全为 JSON 安全值的字典（过滤 None）。"""
    return {k: v for k, v in kwargs.items() if v is not None}

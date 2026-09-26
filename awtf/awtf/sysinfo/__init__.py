"""
系统信息获取模块（sysinfo）。

一键采集设备硬件、操作系统、网络、运行环境四类信息，返回 JSON 安全字典。

快速上手::

    from awtf.sysinfo import collect_system_info

    info = collect_system_info()
    print(info["hardware"]["cpu"]["model"])
    print(info["hardware"]["memory"]["total"])

也可以按子模块单独采集::

    from awtf.sysinfo.hardware import cpu_info, memory_info, disk_info
    from awtf.sysinfo.osinfo import os_info, is_windows
    from awtf.sysinfo.network import network_info
    from awtf.sysinfo.runtime import runtime_info

实现说明：
- **零第三方依赖**：标准库路径可完成全部采集；已安装 ``psutil`` 时自动增强
  （真实 CPU 型号/频率、逐核使用率、接口详情、磁盘分区）。
- 全部函数都是纯同步、快速、非阻塞，适合工具调用与诊断报告。
"""

from __future__ import annotations

from typing import Any, Dict

from ._util import PSUTIL_AVAILABLE, format_bytes, safe_dict
from .hardware import cpu_info, disk_info, memory_info
from .network import network_info
from .osinfo import is_linux, is_macos, is_windows, os_info
from .runtime import runtime_info

__all__ = [
    "collect_system_info",
    "cpu_info",
    "memory_info",
    "disk_info",
    "os_info",
    "network_info",
    "runtime_info",
    "is_windows",
    "is_linux",
    "is_macos",
    "PSUTIL_AVAILABLE",
    "format_bytes",
]


def collect_system_info(*, probe_connectivity: bool = False) -> Dict[str, Any]:
    """一键采集完整系统信息。

    Args:
        probe_connectivity: 是否探测外网连通性（会发真实网络请求，
            默认 False 保持轻量）。

    Returns:
        字典：hardware（cpu/memory/disk）、os、network、runtime、
        psutil_available（是否用了 psutil 增强）。
    """
    return {
        "hardware": {
            "cpu": cpu_info(),
            "memory": memory_info(),
            "disk": disk_info(),
        },
        "os": os_info(),
        "network": network_info(probe_connectivity=probe_connectivity),
        "runtime": runtime_info(),
        "psutil_available": PSUTIL_AVAILABLE,
    }

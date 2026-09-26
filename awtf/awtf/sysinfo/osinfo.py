"""
操作系统信息：系统名、版本、内核、架构、平台字符串。
全部基于标准库 ``platform``，无第三方依赖。
"""

from __future__ import annotations

import platform
import struct
import sys
from typing import Any, Dict


def os_info() -> Dict[str, Any]:
    """获取操作系统信息。

    Returns:
        字典：system、release、version、machine（架构）、bits、
        platform（完整平台字符串，如 ``Windows-11-10.0.26100``）。
    """
    system = platform.system()
    machine = platform.machine() or "unknown"
    bits = struct.calcsize("P") * 8

    return {
        "system": system or "unknown",
        "release": platform.release() or "",
        "version": platform.version() or "",
        "machine": machine,
        "bits": bits,
        "platform": platform.platform() or "",
        "node": platform.node() or "",
        "processor": platform.processor() or "",
        "python_implementation": sys.implementation.name,
    }


def is_windows() -> bool:
    """当前是否 Windows。"""
    return platform.system().lower() == "windows"


def is_linux() -> bool:
    """当前是否 Linux。"""
    return platform.system().lower() == "linux"


def is_macos() -> bool:
    """当前是否 macOS。"""
    return platform.system().lower() == "darwin"

"""
硬件信息：CPU、内存、存储。

- 标准库路径：``platform.processor()`` / ``os.cpu_count()`` /
  ``ctypes.GlobalMemoryStatusEx``（Windows）/ ``/proc/meminfo``（Linux）/
  ``sysctl``（macOS）/ ``shutil.disk_usage``（磁盘）。
- psutil 增强：真实 CPU 型号与频率、逐核心使用率、磁盘分区详情。
"""

from __future__ import annotations

import os
import platform
import shutil
import string
from typing import Any, Dict, List, Optional

from ._util import PSUTIL_AVAILABLE, format_bytes, get_psutil, safe_dict

_PROC_MEMINFO = "/proc/meminfo"


def _get_memory_total_windows() -> Optional[int]:
    """Windows：通过 ctypes 调 GlobalMemoryStatusEx 获取物理内存（字节）。"""
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return int(stat.ullTotalPhys)
    except Exception:
        return None


def _get_memory_total_linux() -> Optional[int]:
    """Linux：解析 /proc/meminfo 的 MemTotal（kB）。"""
    try:
        with open(_PROC_MEMINFO, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = line.split()[1]
                    return int(kb) * 1024
    except Exception:
        return None
    return None


def _get_memory_total_macos() -> Optional[int]:
    """macOS：sysctl -n hw.memsize。"""
    try:
        import subprocess

        out = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, timeout=3,
        )
        return int(out.stdout.strip())
    except Exception:
        return None


def cpu_info() -> Dict[str, Any]:
    """获取 CPU 信息。

    Returns:
        字典：model（型号）、cores（物理核）、logical_cores（逻辑核）、
        frequency_mhz（频率）、usage_percent（使用率）、per_core（psutil 增强）。
    """
    psutil = get_psutil()
    info: Dict[str, Any] = {
        "model": platform.processor() or platform.machine(),
        "cores": _physical_cores(psutil),
        "logical_cores": os.cpu_count() or 0,
        "frequency_mhz": None,
        "usage_percent": None,
        "per_core": None,
    }

    if psutil is not None:
        try:
            freq = psutil.cpu_freq()
            if freq is not None:
                info["frequency_mhz"] = round(freq.current, 1)
        except Exception:
            pass
        try:
            info["usage_percent"] = round(psutil.cpu_percent(interval=None), 1)
        except Exception:
            pass
        try:
            info["per_core"] = [
                round(v, 1) for v in psutil.cpu_percent(interval=None, percpu=True)
            ]
        except Exception:
            pass

    return info


def _physical_cores(psutil) -> Optional[int]:
    if psutil is not None:
        try:
            return psutil.cpu_count(logical=False)
        except Exception:
            pass
    return None


def memory_info() -> Dict[str, Any]:
    """获取内存信息。

    Returns:
        字典：total_bytes、available_bytes、used_bytes、usage_percent、total（人类可读）。
    """
    psutil = get_psutil()
    total: Optional[int] = None
    available: Optional[int] = None

    if psutil is not None:
        try:
            vm = psutil.virtual_memory()
            total = vm.total
            available = vm.available
        except Exception:
            pass

    if total is None:
        if os.name == "nt":
            total = _get_memory_total_windows()
        elif sys_platform() == "linux":
            total = _get_memory_total_linux()
        elif sys_platform() == "darwin":
            total = _get_memory_total_macos()

    total = total or 0
    available = available if available is not None else total
    used = max(0, total - available)
    usage = round(used / total * 100, 1) if total else 0.0

    return {
        "total_bytes": total,
        "available_bytes": available,
        "used_bytes": used,
        "usage_percent": usage,
        "total": format_bytes(total),
        "available": format_bytes(available),
    }


def _windows_drive_paths() -> List[str]:
    """Windows：枚举存在的盘符（C:\\ 等）。"""
    drives = []
    for letter in string.ascii_uppercase:
        path = f"{letter}:\\"
        if os.path.exists(path):
            drives.append(path)
    return drives


def _unix_mount_points() -> List[str]:
    """Linux/macOS：常见挂载点列表。"""
    mounts = []
    for mnt in ("/", "/home", "/tmp"):
        if os.path.exists(mnt):
            mounts.append(mnt)
    return mounts


def disk_info() -> Dict[str, Any]:
    """获取存储信息。

    Returns:
        字典：disks（各分区列表，含 total/used/free/mountpoint）、
        total_bytes、used_bytes、free_bytes。
    """
    psutil = get_psutil()
    disks: List[Dict[str, Any]] = []

    if psutil is not None:
        try:
            for part in psutil.disk_partitions(all=False):
                try:
                    usage = shutil.disk_usage(part.mountpoint)
                except OSError:
                    continue
                disks.append(
                    {
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_bytes": usage.total,
                        "used_bytes": usage.used,
                        "free_bytes": usage.free,
                        "usage_percent": round(usage.used / usage.total * 100, 1)
                        if usage.total else 0.0,
                        "total": format_bytes(usage.total),
                    }
                )
        except Exception:
            pass

    if not disks:
        # 标准库降级
        paths = _windows_drive_paths() if os.name == "nt" else _unix_mount_points()
        for path in paths:
            try:
                usage = shutil.disk_usage(path)
            except OSError:
                continue
            disks.append(
                {
                    "device": path,
                    "mountpoint": path,
                    "fstype": None,
                    "total_bytes": usage.total,
                    "used_bytes": usage.used,
                    "free_bytes": usage.free,
                    "usage_percent": round(usage.used / usage.total * 100, 1)
                    if usage.total else 0.0,
                    "total": format_bytes(usage.total),
                }
            )

    total = sum(d["total_bytes"] for d in disks)
    used = sum(d["used_bytes"] for d in disks)
    free = sum(d["free_bytes"] for d in disks)
    return {
        "disks": disks,
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "total": format_bytes(total),
    }


def sys_platform() -> str:
    """返回归一化平台名：windows / linux / darwin / other。"""
    return platform.system().lower() or sys.platform

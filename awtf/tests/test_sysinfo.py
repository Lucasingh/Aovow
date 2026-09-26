"""sysinfo 模块单元测试。"""

import json
import platform

import pytest

from awtf.sysinfo import (
    collect_system_info,
    cpu_info,
    disk_info,
    format_bytes,
    memory_info,
    network_info,
    os_info,
    runtime_info,
)
from awtf.sysinfo.osinfo import is_linux, is_macos, is_windows


class TestCollectSystemInfo:
    def test_full_structure(self):
        info = collect_system_info()
        assert set(info) == {"hardware", "os", "network", "runtime",
                             "psutil_available"}
        assert set(info["hardware"]) == {"cpu", "memory", "disk"}
        assert isinstance(info["psutil_available"], bool)

    def test_json_serializable(self):
        json.dumps(collect_system_info(), ensure_ascii=False)


class TestCpu:
    def test_fields(self):
        info = cpu_info()
        assert info["model"]
        assert isinstance(info["logical_cores"], int)
        assert info["logical_cores"] >= 1

    def test_usage_bounded(self):
        info = cpu_info()
        if info["usage_percent"] is not None:
            assert 0 <= info["usage_percent"] <= 100


class TestMemory:
    def test_fields(self):
        info = memory_info()
        assert info["total_bytes"] > 0
        assert 0 <= info["usage_percent"] <= 100
        assert info["total"].endswith(("B", "KB", "MB", "GB", "TB"))


class TestDisk:
    def test_nonempty(self):
        info = disk_info()
        assert info["disks"]
        first = info["disks"][0]
        assert first["mountpoint"]
        assert first["total_bytes"] > 0
        assert info["total_bytes"] > 0


class TestOs:
    def test_fields(self):
        info = os_info()
        assert info["system"] in ("Windows", "Linux", "Darwin", "unknown")
        assert info["machine"]
        assert info["bits"] in (32, 64)

    def test_platform_flags_consistent(self):
        system = platform.system().lower()
        assert is_windows() == (system == "windows")
        assert is_linux() == (system == "linux")
        assert is_macos() == (system == "darwin")


class TestNetwork:
    def test_fields(self):
        info = network_info()
        assert info["hostname"]
        assert info["ip"] is None or isinstance(info["ip"], str)
        assert info["loopback_ok"] is True
        assert isinstance(info["interfaces"], list)

    def test_interfaces_shape(self):
        info = network_info()
        if info["interfaces"]:
            iface = info["interfaces"][0]
            assert "name" in iface
            assert "addresses" in iface


class TestRuntime:
    def test_fields(self):
        info = runtime_info()
        assert info["python"]["version"]
        assert info["cwd"]
        assert info["pid"] > 0

    def test_env_whitelist_no_secrets(self):
        info = runtime_info()
        secrets = {"KEY", "PASSWORD", "TOKEN", "SECRET", "CREDENTIAL", "AUTH"}
        for key in info["env"]:
            upper = key.upper()
            assert not any(s in upper for s in secrets), f"泄露环境变量: {key}"


class TestFormatBytes:
    @pytest.mark.parametrize("num,expected", [
        (0, "0 B"),
        (1024, "1.0 KB"),
        (1024 * 1024 * 3, "3.0 MB"),
        (1024 ** 3 * 2, "2.0 GB"),
        (None, "0 B"),
        (-5, "0 B"),
    ])
    def test_cases(self, num, expected):
        assert format_bytes(num) == expected

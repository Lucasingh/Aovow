"""
网络状态：主机名、本机 IP、网络接口、默认网关与连通性。

- 本机 IP 用标准库 ``socket`` 的 UDP 连接技巧（不发包即可取出口 IP）。
- 接口/网关详情用 psutil（可选增强）。
- 连通性探测默认只测本机回环（127.0.0.1），不做外网请求，保证快且无副作用。
"""

from __future__ import annotations

import socket
from typing import Any, Dict, List, Optional

from ._util import get_psutil, safe_dict


def _local_ip() -> Optional[str]:
    """通过 UDP 连接公共 DNS 获取本机出口 IP（实际不发送数据）。"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return None
    finally:
        s.close()


def _loopback_reachable() -> bool:
    """回环连通性：TCP 栈能处理连接即视为可达。

    端口拒绝（ECONNREFUSED，如 10061）与超时（ETIMEDOUT，如 10060/110）
    都说明协议栈正常；只有明确不可达（host/network unreachable）才返回 False。
    """
    try:
        s = socket.create_connection(("127.0.0.1", 1), timeout=1)
        s.close()
        return True
    except OSError as e:
        unreachable = {getattr(socket, "EHOSTUNREACH", 11002),
                       getattr(socket, "ENETUNREACH", 11001)}
        if e.errno in unreachable:
            return False
        # ConnectionRefused / Timeout 等 → 栈已就绪
        return True


def _iface_stats(psutil) -> List[Dict[str, Any]]:
    """psutil 增强：网络接口列表（含 IP/掩码/收发字节）。"""
    result: List[Dict[str, Any]] = []
    try:
        addrs = psutil.net_if_addrs()
        counters = psutil.net_io_counters(pernic=True)
    except Exception:
        return result

    for name, items in addrs.items():
        ips = []
        for item in items:
            ips.append(
                safe_dict(
                    family=str(item.family.name) if getattr(item.family, "name", None) else None,
                    address=item.address,
                    netmask=item.netmask,
                    broadcast=item.broadcast,
                )
            )
        cnt = counters.get(name)
        result.append(
            safe_dict(
                name=name,
                addresses=ips,
                bytes_sent=cnt.bytes_sent if cnt else None,
                bytes_recv=cnt.bytes_recv if cnt else None,
            )
        )
    return result


def network_info(*, probe_connectivity: bool = False) -> Dict[str, Any]:
    """获取网络状态。

    Args:
        probe_connectivity: 是否额外探测外网连通性（会发一次真实请求，
            默认 False 保持轻量）。

    Returns:
        字典：hostname、ip（出口 IP）、interfaces（psutil 增强，可为空列表）、
        loopback_ok（回环连通）、connectivity（probe_connectivity 为 True 时）。
    """
    psutil = get_psutil()
    info: Dict[str, Any] = {
        "hostname": socket.gethostname() or "",
        "ip": _local_ip(),
        "interfaces": _iface_stats(psutil) if psutil is not None else [],
        "loopback_ok": _loopback_reachable(),
    }

    if probe_connectivity:
        info["connectivity"] = _probe_internet()

    return info


def _probe_internet() -> str:
    """探测外网连通性：ok / timeout / error。"""
    try:
        with socket.create_connection(("1.1.1.1", 443), timeout=3):
            return "ok"
    except socket.timeout:
        return "timeout"
    except OSError:
        return "error"

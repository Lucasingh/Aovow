"""
系统信息采集示例：python -m awtf 环境下运行
    python examples/sysinfo_demo.py [--json]

无第三方依赖；已安装 psutil 时自动增强。
"""

import json
import sys

sys.path.insert(0, ".")

from awtf.sysinfo import collect_system_info  # noqa: E402


def main() -> int:
    to_json = "--json" in sys.argv
    info = collect_system_info()

    if to_json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    hw = info["hardware"]
    print("=" * 46)
    print("  AWTF 系统信息（sysinfo 模块）")
    print("=" * 46)
    print(f"  CPU    : {hw['cpu']['model']}")
    print(f"           逻辑核 {hw['cpu']['logical_cores']}，"
          f"物理核 {hw['cpu']['cores']}，使用率 {hw['cpu']['usage_percent']}%")
    print(f"  内存   : {hw['memory']['total']}，"
          f"使用率 {hw['memory']['usage_percent']}%")
    for d in hw["disk"]["disks"][:3]:
        print(f"  磁盘   : {d['mountpoint']} {d['total']} "
              f"({d['usage_percent']}% 已用)")
    print(f"  系统   : {info['os']['system']} {info['os']['release']} "
          f"{info['os']['bits']}-bit")
    print(f"  网络   : {info['network']['hostname']} @ {info['network']['ip']} "
          f"(回环 {'OK' if info['network']['loopback_ok'] else '异常'})")
    print(f"  Python : {'.'.join(map(str, info['runtime']['python']['version_info']))} "
          f"@ {info['runtime']['python']['prefix']}")
    print(f"  psutil : {'增强开启' if info['psutil_available'] else '标准库降级'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

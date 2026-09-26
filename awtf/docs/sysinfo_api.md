# sysinfo —— 系统信息获取模块 API 参考

> 版本 1.1.0 新增。一键采集**设备硬件、操作系统、网络、运行环境**四类信息，
> 全部返回 JSON 安全字典（str/int/float/bool/None），可直接序列化、落库、上报。
>
> **零第三方依赖**：标准库即可完成全部采集；已安装 `psutil` 时自动增强
> （真实 CPU 型号/频率、逐核使用率、接口详情、磁盘分区表）。

---

## 快速上手

```python
from awtf.sysinfo import collect_system_info

info = collect_system_info()

print(info["hardware"]["cpu"]["model"])       # CPU 型号
print(info["hardware"]["memory"]["total"])    # 内存总量（人类可读）
print(info["os"]["system"])                   # Windows / Linux / Darwin
print(info["network"]["ip"])                  # 本机出口 IP
print(info["runtime"]["python"]["version"])   # Python 版本串
```

## 顶层函数

### `collect_system_info(*, probe_connectivity=False) -> dict`

一键汇总全部信息。

| 参数 | 说明 |
|------|------|
| `probe_connectivity` | 是否探测外网连通性（发一次真实连接请求，默认 `False` 保持轻量） |

返回结构：

```python
{
  "hardware": {
    "cpu":     {...},   # CPU 信息
    "memory":  {...},   # 内存信息
    "disk":    {...},   # 存储信息
  },
  "os":       {...},    # 操作系统
  "network":  {...},    # 网络状态
  "runtime":  {...},    # 运行环境
  "psutil_available": True,   # 是否启用 psutil 增强
}
```

## 子模块 API

### `awtf.sysinfo.hardware`

| 函数 | 返回 |
|------|------|
| `cpu_info()` | `model` 型号、`cores` 物理核、`logical_cores` 逻辑核、`frequency_mhz` 频率（psutil）、`usage_percent` 使用率（psutil）、`per_core` 逐核（psutil） |
| `memory_info()` | `total_bytes` / `available_bytes` / `used_bytes` / `usage_percent` / `total` / `available`（人类可读） |
| `disk_info()` | `disks` 分区列表（`device/mountpoint/fstype/total_bytes/used_bytes/free_bytes/usage_percent/total`）、`total_bytes`/`used_bytes`/`free_bytes`/`total` 汇总 |

### `awtf.sysinfo.osinfo`

| 函数 | 返回 |
|------|------|
| `os_info()` | `system`、`release`、`version`、`machine`、`bits`（32/64）、`platform`、`node`、`processor`、`python_implementation` |
| `is_windows()` / `is_linux()` / `is_macos()` | 布尔：当前是否该平台 |

### `awtf.sysinfo.network`

| 函数 | 返回 |
|------|------|
| `network_info(*, probe_connectivity=False)` | `hostname`、`ip`（出口 IP）、`interfaces`（psutil 增强）、`loopback_ok`、`connectivity`（可选） |

> `interfaces` 每项：`name`、`addresses`（family/address/netmask/broadcast）、
> `bytes_sent`、`bytes_recv`。

### `awtf.sysinfo.runtime`

| 函数 | 返回 |
|------|------|
| `runtime_info()` | `python`（version/version_info/executable/prefix/platform/implementation）、`env`（**白名单环境变量**）、`cwd`、`user`、`pid` |

> **安全**：`env` 只暴露白名单（PATH/HOME/APPDATA 等），
> 任何含 KEY/PASSWORD/TOKEN/SECRET/CREDENTIAL/AUTH 的变量一律不输出。

### `awtf.sysinfo._util`

| 函数 | 说明 |
|------|------|
| `format_bytes(num)` | 字节数转人类可读，如 `format_bytes(3 * 1024**3)` → `"3.0 GB"` |
| `PSUTIL_AVAILABLE` | 布尔：psutil 是否已安装（`import awtf.sysinfo` 后可用） |

## 跨平台行为

| 平台 | CPU | 内存 | 磁盘 | 网络 |
|------|-----|------|------|------|
| Windows | `platform.processor`；psutil 增强 | `ctypes.GlobalMemoryStatusEx` | `shutil.disk_usage` 遍历盘符 | 标准 socket |
| Linux | `platform.processor`；psutil 增强 | `/proc/meminfo` | `shutil.disk_usage` 常见挂载点 | 标准 socket |
| macOS | `platform.processor`；psutil 增强 | `sysctl hw.memsize` | `shutil.disk_usage` 常见挂载点 | 标准 socket |

有 psutil 的三平台全部走 psutil（更全：CPU 型号/频率/逐核、分区表、接口明细）。

## 性能说明

- 所有采集均为**同步快速调用**（`psutil.cpu_percent(interval=None)` 非阻塞采样）。
- `collect_system_info()` 单次耗时通常 < 50ms（无外网探测时）。
- 默认**不做外网请求**；需要连通性时显式传 `probe_connectivity=True`。

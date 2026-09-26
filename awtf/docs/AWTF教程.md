# AWTF 教程（全能力版）

> **AWTF（A Work Tool Framework）** 是一个让你**用 Python 代码设计、搭建自己需要的工具与程序**的框架。
> 写一个函数 + `@tool` 装饰器，就等于做了一个工具：自动获得参数校验、错误处理、日志、
> 命令行入口、自动文档；进阶还能直接生成跨平台 GUI、采集系统信息、接入 DeepSeek 大模型，
> 并作为「双轨制」工具挂进 Aovow 工作站侧边栏。

- 适用版本：awtf 1.1.0（Python 包名 `awtf`，CLI 命令 `awtf`）
- 运行环境：Python 3.9+，**核心零第三方依赖**；可选增强：`psutil`（系统信息增强）、`pyyaml`（YAML 配置）
- 配套分册：[使用指南](使用指南.md)（入门）｜ [快速开始](quickstart.md) ｜ [工具开发指南](authoring_guide.md) ｜ [API 参考](api_reference.md) ｜ [UI 组件库](ui_guide.md) ｜ [系统信息](sysinfo_api.md)

---

## 目录

**第一部分 · 零基础入门**
1. [AWTF 是什么](#1-awtf-是什么)
2. [安装与环境自检](#2-安装与环境自检)
3. [5 分钟：生成并运行第一个工具](#3-5-分钟生成并运行第一个工具)
4. [写工具的三种方式](#4-写工具的三种方式)
5. [参数系统](#5-参数系统)
6. [运行工具（Python API / CLI）](#6-运行工具python-api--cli)
7. [结果对象与错误处理](#7-结果对象与错误处理)

**第二部分 · 进阶能力**
8. [配置管理](#8-配置管理)
9. [日志](#9-日志)
10. [UI 组件库：零依赖快速 GUI](#10-ui-组件库零依赖快速-gui)
11. [系统信息：一键采集设备状态](#11-系统信息一键采集设备状态)
12. [AI 大模型：DeepSeek 流式对话](#12-ai-大模型deepseek-流式对话)
13. [工具发现与打包发布](#13-工具发现与打包发布)

**第三部分 · 工作站集成（Aovow Workstation）**
14. [双轨制：一个文件 = CLI 工具 + 侧边栏 GUI 工具](#14-双轨制一个文件--cli-工具--侧边栏-gui-工具)
15. [工具设计器：可视化设计工具](#15-工具设计器可视化设计工具)
16. [注册到侧边栏与生命周期](#16-注册到侧边栏与生命周期)

[FAQ 常见问题](#faq-常见问题) ｜ [文档地图](#文档地图)

---

# 第一部分 · 零基础入门

## 1. AWTF 是什么

AWTF 让「写一个函数」等于「做了一个工具」，并自动附赠：

- **参数校验**：类型自动转换、必填/默认、枚举、范围、长度、正则；
- **错误处理**：工具报错自动包装成结构化结果（含 traceback），不崩调用方；
- **日志**：每个工具有独立 logger，执行日志可随结果返回；
- **配置**：配置文件 + 环境变量分层合并；
- **CLI**：`list / info / run / new / docs / doctor` 开箱即用；
- **自动文档**：参数 schema、Markdown 文档自动生成；
- **进阶模块**：UI 组件库（tkinter GUI）、系统信息采集、DeepSeek AI 对话；
- **可发布**：第三方包通过 entry points 被自动发现；可嵌入工作站成为双轨制工具。

执行链路只有一条（CLI 和 Python 代码走同一条）：

```
工具定义（@tool / ToolBase）
   → 注册表 ToolRegistry
   → registry.run(工具名, 参数)
       → 参数转换与校验（一次性收集所有错误）
       → 注入上下文 ctx（logger/config/metadata）
       → 执行（同步/异步自动调度）
   → ToolResult（ok / data / error / 耗时 / 日志）
```

---

## 2. 安装与环境自检

```bash
# 方式 A：直接用源码（推荐开发期）
# 把 C:\Aovow\awtf 放进 PYTHONPATH，或直接在项目内使用
set PYTHONPATH=C:\Aovow\awtf;%PYTHONPATH%    # PowerShell: $env:PYTHONPATH="C:\Aovow\awtf"

# 方式 B：安装到当前 Python 环境
cd C:\Aovow\awtf
pip install .

# 可选增强
pip install psutil    # 系统信息采集增强（真实 CPU 型号/逐核使用率）
pip install pyyaml    # YAML 配置文件支持
```

自检：

```bash
python -m awtf doctor
```

> Windows 提示：若系统默认 `python` 缺包，请用 Anaconda Python 运行：
> `C:\Users\lshen\anaconda3\python.exe -m awtf doctor`。

---

## 3. 5 分钟：生成并运行第一个工具

```bash
python -m awtf new hello --dir my_tools --description "打招呼工具"
```

生成 `my_tools/tools_hello.py`，核心是一个带 `@tool` 装饰的函数：

```python
from awtf import Parameter, ToolContext, tool

@tool(
    name="hello",
    version="0.1.0",
    tags=["custom"],
    parameters=[
        Parameter("text", str, description="输入文本", min_length=1),
        Parameter("repeat", int, default=1, min=1, max=10, description="重复次数"),
    ],
)
def hello(ctx: ToolContext, text: str, repeat: int = 1) -> dict:
    """打招呼工具"""
    ctx.info("执行 hello: text=%s repeat=%s", text, repeat)
    if ctx.dry_run:
        return {"would_do": f"把 {text!r} 重复 {repeat} 次"}
    return {"tool": "hello", "input": text,
            "output": (text + " ") * repeat, "repeat": repeat}
```

命令行运行：

```bash
python -m awtf list --discover my_tools          # 查看工具列表
python -m awtf info hello --discover my_tools    # 查看参数说明
python -m awtf run hello --text "世界" --repeat 2 --discover my_tools
python -m awtf run hello --text "测试" --dry-run --discover my_tools   # 演练
```

Python 中调用：

```python
from awtf import ToolRegistry

registry = ToolRegistry()
registry.discover_path("my_tools")               # 发现目录里的所有工具
result = registry.run("hello", {"text": "世界", "repeat": 3})
if result.ok:
    print(result.data["output"])                 # 世界 世界 世界
else:
    print("失败：", result.error["message"])
```

---

## 4. 写工具的三种方式

### 4.1 函数工具（推荐，90% 场景）

```python
from awtf import tool, ToolContext

@tool(name="word_count", tags=["text"])
def word_count(ctx: ToolContext, text: str, language: str = "en") -> dict:
    """统计文本词数。

    Args:
        text: 待统计文本
        language: en 按空格分词；zh 按中文字符计
    """
    count = len([c for c in text if "\u4e00" <= c <= "\u9fff"]) if language == "zh" \
        else len(text.split())
    ctx.info("统计完成：%d 词", count)
    return {"words": count, "chars": len(text)}
```

要点：
- **类型从注解自动推断**：`text: str`、`language: str = "en"` 自动成为必填/可选参数；
- **docstring 的 `Args:` 段自动变成参数说明**（也支持 Sphinx 风格 `:param x:`）；
- 装饰后**仍可像普通函数一样直接调用**：`word_count(ctx, text="hi")`；
- 首行 docstring 自动成为工具描述（也可用 `@tool(description=...)` 覆盖）。

### 4.2 类工具（需要状态、复杂参数、生命周期）

```python
from awtf import ToolBase, Parameter, ParameterSet, ToolContext, ToolConfigError
import pathlib

class OrganizeDirTool(ToolBase):
    name = "organize_dir"
    description = "按扩展名归类文件"
    tags = ("files",)

    parameters = ParameterSet([
        Parameter("dir", "path", description="目标目录"),
        Parameter("recursive", bool, default=False, description="是否递归子目录"),
    ])

    def run(self, ctx: ToolContext, dir: pathlib.Path, recursive: bool = False) -> dict:
        if not dir.exists():
            raise ToolConfigError(f"目录不存在: {dir}")   # 业务错误主动抛出
        files = list(dir.rglob("*") if recursive else dir.iterdir())
        ctx.info("发现 %d 个文件", len([f for f in files if f.is_file()]))
        return {"total_files": len(files)}
```

### 4.3 异步工具（并发 IO）

```python
import asyncio
from awtf import tool, ToolContext

@tool(name="sleep_sort", tags=["async"])
async def sleep_sort(ctx: ToolContext, numbers: list) -> dict:
    """异步演示。"""
    async def delayed(n):
        await asyncio.sleep(n / 100)
        return n
    results = await asyncio.gather(*(delayed(float(n)) for n in numbers))
    return {"sorted": sorted(results)}
```

异步工具调用方式与同步完全一致：`registry.run("sleep_sort", {"numbers": [3, 1, 2]})`。

---

## 5. 参数系统

参数是工具的「输入合同」。两种声明方式：**自动推断**（注解 + 默认值 + docstring）或**显式 `Parameter(...)`**（需要约束时）。

### 5.1 支持的类型

| 类型 | 注解写法 | CLI 传入示例 | 转换结果 |
|------|----------|--------------|----------|
| 字符串 | `str` | `--name 张三` | `"张三"` |
| 整数 | `int` | `--count 3` | `3` |
| 浮点 | `float` | `--rate 0.8` | `0.8` |
| 布尔 | `bool` | `--flag true` | `True`（也接受 yes/on/1/是） |
| 列表 | `list` | `--tags a,b,c` 或 `--tags '["a","b"]'` | `["a","b","c"]` |
| 字典 | `dict` | `--data '{"k":1}'` | `{"k": 1}` |
| 路径 | `pathlib.Path` 或 `"path"` | `--dir ~/docs` | `Path("~/docs").expanduser()` |
| 可选 | `Optional[str]` | 不传 | `None` |

### 5.2 校验约束

```python
Parameter("age",   int,  min=0, max=120)                 # 数值范围
Parameter("role",  str,  choices=["admin", "user"])      # 枚举
Parameter("code",  str,  pattern=r"^\d{4}$")             # 正则
Parameter("name",  str,  min_length=2, max_length=20)    # 长度
Parameter("token", str,  required=True, secret=True)     # 敏感值（日志脱敏为 ***）
```

必填规则：**没有默认值 → 必填**；给了 `default=...` → 自动可选；可用 `required=True/False` 显式覆盖。

### 5.3 校验失败长什么样

错误**一次性收集所有字段问题**（不是报一个停一个）：

```python
result = registry.run("add", {"count": "abc", "age": 999})
# result.error["code"] == "VALIDATION_ERROR"
# result.error["details"]["field_errors"] == {
#   "name":  "缺少必填参数",
#   "count": "无法转换为整数: 'abc'",
#   "age":   "数值 999 大于最大值 120",
# }
```

---

## 6. 运行工具（Python API / CLI）

### 6.1 Python API

```python
from awtf import ToolRegistry

registry = ToolRegistry()
registry.discover_path("my_tools")

result = registry.run(
    "hello",                                # 工具名
    {"text": "世界", "repeat": 2},          # 参数字典（自动转换/校验）
    config={"hello": {"greeting": "你好"}},  # 可选：配置
    metadata={"source": "web", "request_id": "req-001"},  # 可选：元数据
    capture_logs=True,                      # 可选：捕获执行日志
)
```

进程级单例注册表（多处共享）：

```python
from awtf import get_default_registry
reg = get_default_registry()
```

查询工具：`registry.names()` / `registry.has("add")` / `registry.list_tools(tag="math")` / `registry.describe("add")`。

### 6.2 命令行 CLI

```bash
python -m awtf list     [--discover 目录或文件] [--tag xxx] [--json]
python -m awtf info     <工具名> [--discover ...]
python -m awtf run      <工具名> [--参数 值 ...] [--dry-run] [-v] [--json] [--discover ...]
python -m awtf new      <工具名> [--dir 目录] [--description "说明"] [--no-readme]
python -m awtf docs     [工具名] [--discover ...]     # 输出 Markdown 文档
python -m awtf doctor
```

参数值**先尝试按 JSON 解析，失败再当字符串**；`--discover` 放工具名前后皆可。
退出码：`0` 成功 / `1` 工具执行失败 / `2` 用法错误（便于写脚本判断）。

---

## 7. 结果对象与错误处理

`registry.run()` **永远返回 `ToolResult`，默认不抛业务异常**。

```python
result.ok            # True/False
result.data          # 成功时的返回值
result.error         # 失败时：{"code","message","tool","details"}
result.duration_ms   # 耗时（毫秒）
result.metadata      # 你传入的元数据
result.logs          # capture_logs=True 时的日志行列表
result.to_dict()     # 转 JSON 安全字典（CLI/网络回传）
result.get("k")      # data 是字典时按键取值
```

异常风格（偏好 try/except 时）：

```python
from awtf import ToolValidationError, ToolExecutionError, ToolNotFoundError
try:
    result = registry.run("risky", params, raise_on_error=True)
except ToolValidationError as e:
    print(e.field_errors)             # 所有字段错误
except ToolExecutionError as e:
    print(e.traceback_text)           # 完整 traceback
except ToolNotFoundError as e:
    print(e.details["available"])     # 可用工具列表
```

错误码速查：`VALIDATION_ERROR`（参数问题，含 field_errors）｜ `TOOL_NOT_FOUND`（工具未注册，含 available）｜ `EXECUTION_ERROR`（内部异常，含 traceback）｜ `CONFIG_ERROR`（配置缺失）｜ `REGISTRATION_ERROR`（重名注册）｜ `DISCOVERY_ERROR`（发现/导入失败）。
工具内主动抛 `ToolError` 子类会被原样保留；抛普通 `ValueError` 会被包装为 `EXECUTION_ERROR`，不会击穿调用方。

---

# 第二部分 · 进阶能力

## 8. 配置管理

优先级：**默认值 < 配置文件 < 环境变量**。

```python
from awtf import load_config

config = load_config(
    "config.json",                          # .json；.yaml 需 pip install pyyaml
    defaults={"backup": {"keep_days": 7}},
)
registry.run("backup", {...}, config=config)
```

环境变量覆盖规则：`AWTF__段名__键名=值`，值按 JSON 解析，如 `set AWTF__BACKUP__KEEP_DAYS=60`。

工具内读取：

```python
def backup(ctx: ToolContext, ...):
    keep = ctx.section_config("backup").get_int("keep_days", 7)
    target = ctx.get_config("target_dir", required=True)   # 缺失抛 CONFIG_ERROR
```

`ToolConfig` 提供 `get / get_str / get_int / get_float / get_bool`，支持 `required=True`。

## 9. 日志

```python
from awtf import setup_logging
setup_logging("INFO", log_file="tools.log")   # 控制台 + 文件（只需调用一次）
```

- 每个工具有独立 logger：`awtf.tools.<工具名>`，工具内直接用 `ctx.info(...)`；
- 把一次执行的日志收进结果（适合在界面里展示）：`registry.run(..., capture_logs=True)` 后 `result.logs`。

---

## 10. UI 组件库：零依赖快速 GUI

`awtf.ui` 让你**用纯数据描述界面**，默认 tkinter 渲染后端（标准库，跨平台，可打包）。

组件 = 纯数据描述（`LabelSpec / ButtonSpec / InputSpec / CardSpec / RowSpec / TextAreaSpec ...`），
渲染由后端完成。完整用法见 [ui_guide.md](ui_guide.md)。

```python
from awtf.ui import (
    App, LabelSpec, ButtonSpec, InputSpec, InputField, CardSpec, RowSpec,
)

app = App(
    title="示例",
    width=480, height=360,
    children=[
        LabelSpec("欢迎使用 AWTF UI", bold=True, size=16),
        CardSpec(title="登录", children=[
            InputSpec(InputField("username", label="用户名", required=True)),
            InputSpec(InputField("password", label="密码", kind="password",
                                 required=True, hint="敏感字段不落盘")),
        ]),
        RowSpec([
            ButtonSpec("确定", on_click="on_ok"),
            ButtonSpec("取消", style="ghost", on_click="on_cancel"),
        ]),
    ],
)
render_app(app)   # 进入事件循环
```

**AppWindow 交互模式**（子类化，处理回调 + 动态刷新）：

```python
from awtf.ui import App, ButtonSpec, InputField, InputSpec, LabelSpec, TextAreaSpec, show_message, MessageDialog
from awtf.ui.tk_backend import AppWindow

class MyWin(AppWindow):
    def __init__(self):
        app = App(
            title="我的窗口", width=680, height=520,
            children=[
                InputSpec(InputField("input", label="", required=True,
                                     placeholder="输入消息"),
                          on_submit="on_send"),
                ButtonSpec("发送", on_click="on_send"),
                TextAreaSpec("log", height=16, readonly=True,
                             text="👋 开始…\n\n"),
            ],
        )
        super().__init__(app, {"on_send": self.on_send})
        self.root.after(40, self._poll)   # 定时轮询（流式/后台任务刷新 UI）

    def on_send(self, payload=None):
        values = self.get_values()        # 始终从输入框取最新值
        self.append_text("log", f"你：{values.get('input')}\n")

    def _poll(self):
        ...  # 从队列读后台结果，append_text 更新界面
        self.root.after(40, self._poll)

    def _warn(self, msg):
        show_message(self.root, MessageDialog("提示", msg, level="warning"))
```

关键 API：
- `App(title, width, height, children=[...])` 描述窗口；
- `InputField(name, label, kind="password/number", required, default, placeholder, hint, min, max)`；
- `InputSpec(field, on_submit="回调名")` 支持回车提交；
- `TextAreaSpec(name, height, readonly, text)` 只读/可写文本区；
- `ButtonSpec(text, on_click, style="primary/ghost")`、`CardSpec(title, children)`、`RowSpec([...])`、`DividerSpec()`、`IconSpec(text, size)`；
- `AppWindow(app, callbacks)`：`self.get_values()` / `self.append_text(name, chunk)` / `self.text_areas[name]`（tk.Text）/ `self._inputs[name]`（输入控件）；
- 对话框：`show_message(root, MessageDialog(title, msg, level))`、`show_confirm`、`show_input`；反馈：`ProgressBar / Spinner / Toast`。

> Tk 非线程安全：**UI 更新只能在主线程**。流式/耗时任务放后台线程，用 `queue.Queue` + `root.after` 轮询回主线程更新（见下方 DeepSeek 示例与 `examples/deepseek_chat_demo.py`）。

---

## 11. 系统信息：一键采集设备状态

`awtf.sysinfo` 零依赖采集硬件 / 系统 / 网络 / 运行环境四类信息，返回 JSON 安全字典。

```python
from awtf.sysinfo import collect_system_info

info = collect_system_info()
print(info["hardware"]["cpu"]["model"])
print(info["hardware"]["memory"]["total"])
print(info["os"]["platform"])          # win32 / linux / darwin
```

返回结构：

```python
{
  "hardware": {"cpu": {...}, "memory": {...}, "disk": {...}},
  "os":        {"platform", "release", "machine", ...},
  "network":   {"hostname", "fqdn", "interfaces", "ip", "connectivity"?},
  "runtime":   {"python", "platform", "uptime_s", "load_avg", ...},
  "psutil_available": True,            # 是否用了 psutil 增强
}
```

按需采集子模块：

```python
from awtf.sysinfo.hardware import cpu_info, memory_info, disk_info
from awtf.sysinfo.osinfo import os_info, is_windows, is_linux, is_macos
from awtf.sysinfo.network import network_info
from awtf.sysinfo.runtime import runtime_info
from awtf.sysinfo import format_bytes
```

- `collect_system_info(probe_connectivity=True)` 会额外探测外网连通性（发真实请求，默认 False）；
- 已安装 `psutil` 时自动增强（真实 CPU 型号/频率、逐核使用率、接口详情、磁盘分区）；
- 全部函数纯同步、快速、非阻塞。详见 [sysinfo_api.md](sysinfo_api.md)。

## 12. AI 大模型：DeepSeek 流式对话

`awtf.ai.deepseek` 零依赖接入 DeepSeek（OpenAI 兼容 API，SSE 流式）。

```python
from awtf.ai import stream_chat, chat, DEFAULT_MODEL, MODELS

# 非流式一问一答
reply = chat(None, [{"role": "user", "content": "你好"}])
# reply == "完整回答文本"

# 流式：逐块 yield 增量文本
parts = []
for chunk in stream_chat("sk-xxx", [{"role": "user", "content": "讲个故事"}],
                         model="deepseek-chat"):
    parts.append(chunk)
print("".join(parts))
```

API Key 解析优先级（`resolve_api_key`）：**显式传参 > 环境变量 `DEEPSEEK_API_KEY` > `AOVOW_AI_API_KEY`**。

内置 AWTF 工具 `deepseek_ask`（可 CLI 运行）：

```bash
python -m awtf run deepseek_ask --message "用一句话介绍 Python" --discover awtf/awtf/ai/deepseek.py
```

完整带 GUI 的流式对话示例见 `examples/deepseek_chat_demo.py`：后台线程读 SSE → `queue` → 主线程 `after(40)` 轮询 → `append_text` 流式渲染，界面不卡。

---

## 13. 工具发现与打包发布

### 13.1 三种发现方式

```python
registry.discover_path("my_tools/")               # 扫描目录下所有 .py
registry.discover_path("my_tools/tools_hello.py") # 单个文件
registry.discover_module("my_pkg.tools")          # 导入已安装模块
registry.discover_entry_points()                  # 发现已安装包注册的工具
```

规则：模块内所有 `@tool` 装饰的函数、`ToolBase` 子类/实例自动注册（下划线开头的文件跳过）。

### 13.2 打包发布给别人

在你的包 `pyproject.toml` 声明 entry point：

```toml
[project.entry-points."awtf.tools"]
my_bundle = "my_pkg.tools:register_tools"
```

`register_tools` 可以是 `ToolBase` 实例、`ToolRegistry` 或返回它们的工厂函数。用户装包后：

```python
registry = ToolRegistry()
registry.discover_entry_points()   # 你的工具自动出现
```

### 13.3 重名冲突

同名重复注册默认报 `REGISTRATION_ERROR`；确需覆盖：`registry.register(tool, override=True)`。

---

# 第三部分 · 工作站集成（Aovow Workstation）

## 14. 双轨制：一个文件 = CLI 工具 + 侧边栏 GUI 工具

**双轨制**是 Aovow 工作站的工具标准：同一个 `.py` 文件同时定义
**AWTF `@tool` 函数**（可命令行运行）和 **`BaseTool` GUI 子类**（在工作站侧边栏显示）。
参考 `workstation/tools/hello_world_tool.py`：

```python
# ========== 轨 1：AWTF 函数工具 ==========
import sys as _sys
from pathlib import Path as _Path

# 引导 awtf 真包进 sys.path（开发环境 & 打包后都能导入）
_awtf_root = _Path(__file__).resolve().parent.parent.parent / "awtf"
if str(_awtf_root) not in _sys.path:
    _sys.path.insert(0, str(_awtf_root))

from awtf import Parameter, ToolContext, tool

@tool(name="hello_world", description="最简单的 AWTF 示例工具", tags=["demo"],
      parameters=[
          Parameter("name", str, default="World", description="向谁打招呼"),
          Parameter("repeat", int, default=1, min=1, max=10, description="重复次数"),
      ])
def hello_world(ctx: ToolContext, name: str = "World", repeat: int = 1) -> dict:
    """Hello World！"""
    ctx.info("hello_world: name=%s, repeat=%d", name, repeat)
    messages = ["HELLO, " + name.upper() + "!" for _ in range(repeat)]
    return {"greeting": messages[0], "messages": messages, "count": repeat}

# ========== 轨 2：工作站 GUI 工具 ==========
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from workstation.tools.base_tool import BaseTool

class HelloWorldTool(BaseTool):
    tool_id = "hello_world"
    name = "HelloWorld"
    icon = "👋"
    category = "测试"                  # 决定出现在侧边栏哪个分组
    description = "AWTF + 工作站集成示例工具"

    def __init__(self):
        self._widget: QWidget | None = None   # 懒加载

    @property
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._build_ui()   # 构建你的 PySide6 界面
        return self._widget
```

命令行跑同一工具：

```bash
python -m awtf run hello_world --name Aovow --repeat 2 --discover workstation/tools/hello_world_tool.py
```

> 注意：`BaseTool` 的 `widget` 是抽象 property，必须**懒加载**（首次访问才构建），
> 并在顶部做 awtf 引导，否则打包后 `from awtf import ...` 会因 import 路径问题失败。

## 15. 工具设计器：可视化设计工具

工作站内置「🛠️ 工具设计器」（分类「系统」），**不用写全文件**就能造工具：

1. **左栏「⚙ 参数定义」**：表格添加参数（名称/类型/默认值/说明）；
2. **左栏「⌨ 工具逻辑」**：只写函数体（自动包进 `def`，`return dict` 最佳）；
3. **右栏「实时运行」**：点「▶ 运行」**不保存**就编译执行，结果 JSON 即时显示；
4. **底栏「💾 保存并注册」**：弹出「工具设置」填写 ID/名称/分类/图标/描述 → 保存。

保存后自动生成文件到 `workstation/designer_tools/<tool_id>.py` 并**动态注册**进侧边栏。
生成源码是标准双轨制：

```python
@tool(name="<tool_id>", description=..., category=..., parameters=[...])
def <tool_id>(ctx: ToolContext, ...): ...          # 轨 1：AWTF 函数

class <CamelCase>Tool(DesignerToolBase):           # 轨 2：GUI（自动按参数渲染表单）
    _func = <tool_id>
```

`DesignerToolBase`（`workstation/tools/designer_base.py`）自动按 `@tool` 参数元数据渲染输入表单
（str→输入框 / int→数字框 / float→小数框 / bool→勾选框），点「运行」执行并 JSON 展示结果。

## 16. 注册到侧边栏与生命周期

内置工具在 `workstation/core/application.py` 的 `_init_tools()` 注册：

```python
from workstation.tools.registry import ToolRegistry
self.tool_registry = ToolRegistry()
self.tool_registry.register(HelloWorldTool)        # 传入工具类
self.signals.tool_registered.emit(HelloWorldTool.tool_id)   # 通知侧边栏刷新
```

设计器生成的工具：启动时 `_load_designer_tools()` 扫描 `designer_tools/*.py` 自动加载；
运行时新建则通过 `SignalBus().designer_tool_created` 信号动态注册。

**生命周期**（`BaseTool` 约定）：

```python
class MyTool(BaseTool):
    def on_activate(self):   ...   # 切换到本工具时（如重置界面/启动定时器）
    def on_deactivate(self): ...   # 切走时（如停止后台线程）
    def on_close(self):      ...   # 应用关闭时清理资源
```

**工作站工具编写规范速记**：
- 顶部做 awtf 引导（`_AWTF_ROOT` 插入 sys.path）；
- 懒加载 `widget` property；界面样式用设计系统 tokens（`workstation/ui/styles.py` 的 `COLORS`），不硬编码颜色；
- 耗时任务用 `QThread`，信号命名避开 Qt 内置信号（如用 `chunk_received` 而非 `finished`）；
- 网络请求按系统代理配置；不用 `os.system`（跨平台兼容）。

---

## FAQ 常见问题

**Q1：必须用 CLI 吗？** 不用。CLI 只是薄壳，核心是 Python API，两者走同一条校验/错误链路。

**Q2：参数一定要写 `Parameter(...)` 吗？** 不用。注解 + 默认值就能自动推断；需要枚举/范围/正则等约束时才显式写。

**Q3：工具里能抛异常吗？** 可以。`ToolError` 子类原样保留错误码；普通异常包装成 `EXECUTION_ERROR` 附带 traceback，调用方不崩。

**Q4：异步工具怎么调用？** 和同步完全一样——`registry.run(...)`，注册表自动处理事件循环。

**Q5：`from awtf import ...` 报错（unknown location）？** 这是 cwd 下有同名无 `__init__.py` 的 namespace 目录抢占真包所致。把真包父目录显式加进 `sys.path`（见第 14 节引导写法）。

**Q6：Windows 提示 `No module named yaml/psutil/PySide6`？** 用已装依赖的环境（Anaconda Python）运行；这些是可选的，核心功能零依赖。

**Q7：怎么让别人 pip install 后就能用我的工具？** 在包的 `pyproject.toml` 声明 `[project.entry-points."awtf.tools"]`（见第 13 节）。

**Q8：UI 在后台线程更新会卡/闪？** Tk 非线程安全——UI 更新只能在主线程。用 `queue.Queue` + `root.after` 轮询模式。

**Q9：打包成 exe 后工具不见了？** 确认 `BaseTool` 已注册进 `application.py` 的 `_init_tools()`；设计器工具需在 `designer_tools/` 目录存在且启动扫描成功。

---

## 文档地图

| 文档 | 内容 |
|------|------|
| [使用指南](使用指南.md) | 零基础完整入门（安装→实战备份工具→FAQ） |
| [快速开始](quickstart.md) | 3 分钟上手摘要 |
| [工具开发指南](authoring_guide.md) | 参数/类工具/异步/配置/dry-run 完整模式 |
| [API 参考](api_reference.md) | 所有公开类与函数 |
| [UI 组件库](ui_guide.md) | `awtf.ui` 全部组件与渲染细节 |
| [系统信息](sysinfo_api.md) | `awtf.sysinfo` 字段说明 |
| 本教程 | 全能力总览：入门 + 进阶 + 工作站集成 |

*本教程内容与 awtf 1.1.0 / Aovow Workstation 实现一一对应；如发现示例与行为不符，以源码与 `python -m awtf doctor` 为准。*

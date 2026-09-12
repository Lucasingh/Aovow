# API 参考

## 公开 API 速览

```python
from awtf import (
    # 工具定义
    tool, ToolBase, FunctionTool, ToolMeta,
    # 参数
    Parameter, ParameterSet, infer_parameters,
    # 注册表
    ToolRegistry, get_default_registry,
    # 上下文与结果
    ToolContext, ToolResult,
    # 错误
    ToolError, ToolNotFoundError, ToolValidationError,
    ToolExecutionError, ToolConfigError,
    ToolRegistrationError, ToolDiscoveryError,
    # 配置
    ToolConfig, load_config, save_config, deep_merge,
    # 日志
    setup_logging, get_tool_logger, LogCapture,
    # 脚手架
    scaffold, render_tool_file, render_readme,
)
```

---

## 工具定义

### `@tool`

```python
tool(func=None, *, name=None, description=None, parameters=None,
     version="1.0.0", tags=(), author="", category="general")
```

装饰器，把函数转为 `FunctionTool`。支持带括号/不带括号两种用法。
参数从函数签名与类型注解推断；显式传 `parameters=[...]` 时以声明为准。

### `ToolBase`

类工具基类。子类需设置：

| 类属性 | 说明 |
|--------|------|
| `name` | 工具名（必填，非空） |
| `description` | 描述（缺省取 docstring 首行） |
| `version` | 版本，默认 "1.0.0" |
| `tags` / `author` / `category` | 元数据 |
| `parameters` | `ParameterSet` 实例 |

需实现 `run(self, ctx, **params)`；异步工具实现 `async def run` 或重写 `arun`。

方法：
- `describe() -> dict`：完整描述（元数据 + 参数 schema + kind/async）。

---

## 参数

### `Parameter`

```python
Parameter(name, type=str, *, default=_UNSET, required=None, description="",
          choices=None, min=None, max=None, min_length=None, max_length=None,
          pattern=None, secret=False)
```

- 传 `default` 即自动可选；`required` 显式指定优先；
- `type`：`str/int/float/bool/list/dict/pathlib.Path/Optional[X]/List[X]` 或字符串；
- 方法：`coerce(value)`（类型转换，失败抛 ValueError）、`validate(value)`（约束）、
  `to_dict()`（schema）、`mask(value)`（脱敏）。

### `ParameterSet`

- `validate(raw, tool=None) -> dict`：校验+转换，返回完整参数；
  失败抛 `ToolValidationError`（`field_errors` 聚合所有错误，未知参数在 `__unknown__`）。
- `names()` / `get(name)` / `to_list()`。

### `infer_parameters(func) -> ParameterSet`

从函数签名推断；跳过前导 `ctx/context/self`；解析 docstring 的 `:param:` 与 `Args:` 段。

---

## 注册表 `ToolRegistry`

| 方法 | 说明 |
|------|------|
| `register(tool, *, override=False) -> ToolBase` | 注册 FunctionTool/ToolBase 实例/ToolBase 子类；未装饰函数抛 `ToolRegistrationError`；重名默认抛错 |
| `unregister(name) -> bool` | 注销 |
| `tool(*, name=None, override=False, **meta)` | 装饰器：定义并注册函数工具 |
| `get(name) -> ToolBase` | 不存在抛 `ToolNotFoundError` |
| `has(name)` / `names()` / `len(reg)` / `name in reg` | 查询 |
| `list_tools(*, tag=None, category=None) -> list[dict]` | 元数据列表（可过滤） |
| `describe(name) -> dict` | 单个工具完整描述 |
| **`run(name, params=None, *, config=None, metadata=None, capture_logs=False, raise_on_error=False) -> ToolResult`** | **唯一执行入口** |
| `discover_module(module)` / `discover_path(path)` / `discover_entry_points()` | 自动发现，返回注册的工具名列表 |

`run` 链路：工具存在性 → 参数校验（类型转换+约束）→ 构造 `ToolContext` →
执行（同步/异步自动调度）→ 异常包装 → 计时，返回 `ToolResult`。

`get_default_registry()`：进程级单例注册表。

---

## 上下文 `ToolContext`

| 属性/方法 | 说明 |
|-----------|------|
| `tool_name` | 工具名 |
| `logger` | `awtf.tools.<name>` logger |
| `config` | 全局配置字典 |
| `metadata` | 运行元数据 |
| `dry_run` | 是否演练模式 |
| `section_config(section=None)` | 取配置段视图（默认同名段） |
| `get_config(key, default)` | 读配置项 |
| `debug/info/warning/error(msg, *args)` | 日志便捷方法 |

## 结果 `ToolResult`

| 字段/方法 | 说明 |
|-----------|------|
| `ok` | 是否成功 |
| `data` | 返回值 |
| `error` | `{code, message, tool, details}` 或 None |
| `duration_ms` / `started_at` / `finished_at` | 计时 |
| `metadata` / `logs` | 元数据与捕获的日志 |
| `to_dict()` | JSON 安全字典 |
| `raise_for_status()` | 失败抛 `ToolError` |
| `get(key, default)` | data 为字典时按键取值 |

---

## 错误体系

```
ToolError (code, message, tool, details; to_dict())
├── ToolNotFoundError       # details.available
├── ToolValidationError     # field_errors: {字段: 原因}
├── ToolExecutionError      # original, traceback_text
├── ToolConfigError
├── ToolRegistrationError   # details.existing_version/new_version
└── ToolDiscoveryError
```

## 配置

- `load_config(path=None, *, defaults=None, env_prefix="AWTF__") -> dict`
  分层合并；环境变量 `AWTF__A__B` → 嵌套键；值按 JSON 解析。
- `save_config(path, data)`：按 .json/.yaml 后缀写；无 pyyaml 时 YAML 降级为 JSON。
- `deep_merge(base, override) -> dict`：递归合并，不改输入。
- `ToolConfig(raw, *, section=None)`：`get/get_str/get_int/get_float/get_bool`，
  支持 `required=True`、`secret=True`。

## 日志

- `setup_logging(level=INFO, *, log_file=None, force=False)`
- `get_tool_logger(name) -> Logger`
- `LogCapture(logger_name)` 上下文管理器：`with LogCapture(...) as cap: cap.records`

## CLI（`python -m awtf`）

| 命令 | 说明 |
|------|------|
| `list [--tag --category --json] [--discover P] [--entry-points]` | 列出工具 |
| `info <name> [--json] [--discover P]` | 详情（参数 schema） |
| `run <name> [--key value ...] [--dry-run] [-v] [--json] [--discover P]` | 运行；成功退出码 0，业务失败 1，用法错误 2 |
| `new <name> [--dir D] [--description S] [--no-readme]` | 脚手架 |
| `docs [name] [--discover P]` | Markdown 文档 |
| `doctor` | 环境自检 |

参数值按 JSON 解析（`--count 3` → int，`--tags '["a"]'` → list），解析失败按字符串。

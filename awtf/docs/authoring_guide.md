# 工具开发指南

## 1. 三种工具形态

### 1.1 函数工具（推荐，90% 场景）

```python
from awtf import tool, ToolContext

@tool(
    name="send_email",
    version="1.1.0",
    tags=["notification", "email"],
    author="you@example.com",
    category="communication",
)
def send_email(ctx: ToolContext, to: str, subject: str, body: str = "",
               cc: list = None) -> dict:
    """发送邮件。

    Args:
        to: 收件人地址
        subject: 主题
        body: 正文
        cc: 抄送列表
    """
    ...
```

- 参数类型从注解**自动推断**，docstring 的 `Args:` 段自动提取为参数说明；
- 有默认值的参数自动变为可选；
- 被装饰后仍然可以像普通函数一样直接调用：`send_email(ctx, to="a@b.c", subject="x")`。

### 1.2 类工具（需要状态/生命周期）

```python
from awtf import ToolBase, Parameter, ParameterSet, ToolContext

class DbQueryTool(ToolBase):
    name = "db_query"
    description = "执行只读 SQL 查询"
    version = "2.0.0"
    tags = ("database",)

    parameters = ParameterSet([
        Parameter("sql", str, description="SELECT 语句", min_length=7,
                  pattern=r"(?i)^\s*select"),
        Parameter("limit", int, default=100, min=1, max=1000),
    ])

    def __init__(self):
        super().__init__()
        self._conn = None  # 可持有状态（懒连接）

    def run(self, ctx: ToolContext, sql: str, limit: int = 100) -> dict:
        ctx.info("query: %.40s...", sql)
        ...
        return {"rows": [...], "count": n}
```

### 1.3 异步工具

定义为 `async def` 即可，注册表自动调度事件循环：

```python
@tool(name="fetch_all")
async def fetch_all(ctx, urls: list) -> dict:
    """并发抓取多个 URL。"""
    import asyncio
    async def fetch(u): ...
    results = await asyncio.gather(*(fetch(u) for u in urls))
    return {"results": results}
```

## 2. 参数系统

### 2.1 支持的类型

| 类型 | 注解写法 | CLI 输入转换 |
|------|----------|--------------|
| 字符串 | `str` | 原样 |
| 整数 | `int` | `"42"` → 42 |
| 浮点 | `float` | `"3.14"` → 3.14 |
| 布尔 | `bool` | `true/false/yes/no/1/0/是/否` |
| 列表 | `list` | `"a,b,c"` 逗号分隔；JSON 数组 |
| 字典 | `dict` | JSON 字符串 |
| 路径 | `pathlib.Path` / `"path"` | 自动 `expanduser()` |
| 可选 | `Optional[str]` | None 安全 |

### 2.2 校验约束

```python
Parameter("age", int, min=0, max=120)                    # 数值范围
Parameter("role", str, choices=["admin", "user"])        # 枚举
Parameter("code", str, pattern=r"^\d{4}$")               # 正则
Parameter("name", str, min_length=2, max_length=20)      # 长度
Parameter("token", str, required=True, secret=True)      # 敏感值（日志脱敏）
Parameter("note", str, default="", required=False)       # 显式可选
```

- 所有字段的错误会**一次性收集**（不是报一个停一个）；
- 传入未声明的参数会产生 `__unknown__` 错误，帮助发现拼写问题。

### 2.3 上下文 ctx

每个工具的首个参数是 `ToolContext`，由运行器注入：

```python
def my_tool(ctx: ToolContext, ...):
    ctx.info("消息")        # ctx.logger / debug / warning / error
    cfg = ctx.section_config("my_tool")   # 读配置段
    api_key = cfg.get("api_key", required=True)
    timeout = ctx.get_config("timeout", 30)
    if ctx.dry_run:        # 演练模式：只报告将做什么
        return {"would_do": ...}
```

## 3. 配置

分层：**默认值 < 配置文件 < 环境变量**。

```json
// config.json
{
  "send_email": { "smtp_host": "smtp.example.com", "timeout": 30 },
  "app_name": "my-tools"
}
```

```bash
# 环境变量覆盖（AWTF__段__键）
export AWTF__SEND_EMAIL__TIMEOUT=60
```

```python
from awtf import load_config

config = load_config("config.json", defaults={"send_email": {"timeout": 10}})
registry.run("send_email", {...}, config=config)
```

YAML 文件需 `pip install pyyaml`。

## 4. 错误处理

两种风格，任选：

```python
# 风格 A：结果判断（默认，适合 CLI/IPC）
result = registry.run("risky", params)
if not result.ok:
    print(result.error["code"], result.error["message"])

# 风格 B：异常模式
try:
    result = registry.run("risky", params, raise_on_error=True)
except ToolValidationError as e:
    print(e.field_errors)
except ToolExecutionError as e:
    print(e.traceback_text)
```

工具内部主动抛出 `ToolError` 子类会被原样保留；抛普通异常会被包装为
`ToolExecutionError`（含完整 traceback），不会击穿到调用方。

## 5. 日志

```python
from awtf import setup_logging
setup_logging("INFO", log_file="tools.log")

# 执行时捕获日志到结果（随结果回传/展示）
result = registry.run("my_tool", params, capture_logs=True)
print(result.logs)
```

## 6. 发现与发布

- **目录/文件发现**：`registry.discover_path("my_tools/")`（扫描 .py）或
  `discover_path("my_tools/report.py")`；
- **模块发现**：`registry.discover_module("my_pkg.tools")`；
- **entry points**（打包发布）：在 pyproject.toml 声明

```toml
[project.entry-points."awtf.tools"]
my_bundle = "my_pkg.tools:register"
```

  其中 `register` 可以是 `ToolBase` 实例、`ToolRegistry` 或返回它们的工厂函数；
  第三方安装后 `registry.discover_entry_points()` 自动发现。

## 7. 命名与冲突

- 工具名必须唯一；重复注册默认抛 `REGISTRATION_ERROR`；
- 确认覆盖时传 `registry.register(tool, override=True)`；
- 建议带版本号（`version`），冲突错误会提示新旧版本；
- 名称可用点号做命名空间，如 `"text.count_words"`。

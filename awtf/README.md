# AWTF

> **A Work Tool Framework** —— 让用户用 Python 代码设计、搭建自己需要的工具与程序的框架。
> 写一个函数，就是一个可运行的工具——自动获得参数校验、错误处理、日志、配置、CLI 和自动文档；
> 多个工具组合起来，就是你自己的一套程序。

## 为什么需要它

你想做的每一个小工具、脚本、自动化程序，往往都在重复造轮子：参数解析、输入校验、
报错处理、日志、配置、命令行入口…… AWTF 把这些收敛成一条标准链路，
让你**只写业务逻辑，其余交给框架**：

```
工具定义（@tool / ToolBase）
   → 注册（ToolRegistry，含命名冲突检测与自动发现）
   → 执行（registry.run → 类型转换/校验 → 上下文注入 → 异常包装）
   → 标准化结果（ToolResult：ok/data/error/耗时/日志）
```

**核心特性**

- 🔧 **三种工具形态**：`@tool` 装饰函数（参数从类型注解自动推断）、`ToolBase` 类、`async def` 异步工具
- ✅ **参数系统**：类型转换（str/int/float/bool/list/dict/path）、必填/默认、枚举、范围、长度、正则，**一次聚合所有错误**
- 🛡️ **统一错误处理**：工具异常自动包装为结构化结果（含 traceback），也可切换为异常模式
- 📋 **配置管理**：默认值 < JSON/YAML 文件 < 环境变量分层合并
- 📝 **日志**：按工具命名的 logger，可选执行期日志捕获写入结果
- 🔍 **自动发现**：目录扫描、模块导入、setuptools entry points
- 🖥️ **CLI 开箱即用**：`list / info / run / new（脚手架）/ docs / doctor`
- 💻 **系统信息采集（sysinfo）**：CPU/内存/磁盘/操作系统/网络/运行时一键获取，psutil 可选增强，JSON 安全输出
- 🧩 **跨平台 UI 组件库（ui）**：按钮/输入框/卡片/列表/表格/对话框/进度条/Toast，纯数据描述 + tkinter 渲染，零第三方依赖
- 📚 **文档与测试**：Markdown 文档自动生成，148 个单元测试覆盖全链路（含 UI 验证逻辑与渲染构造）
- 🪶 **零依赖**：核心功能仅用 Python 标准库（YAML 支持为可选）

## 30 秒上手

```bash
# 生成一个新工具
$ python -m awtf new hello --dir my_tools --description "打招呼工具"

# 运行它
$ python -m awtf run hello --text "世界" --repeat 2 --discover my_tools
```

或者直接写代码：

```python
from awtf import tool, ToolRegistry

@tool(name="greet", tags=["demo"])
def greet(ctx, name: str, count: int = 1) -> str:
    """向用户打招呼。

    Args:
        name: 用户名
        count: 重复次数
    """
    ctx.info("greet %s x%s", name, count)
    return ("你好，" + name) * count

registry = ToolRegistry()
registry.register(greet)

result = registry.run("greet", {"name": "世界", "count": 2})
if result.ok:
    print(result.data)            # 你好，世界你好，世界
else:
    print(result.error["message"])
```

类工具（需要状态/复杂校验时）：

```python
from awtf import ToolBase, Parameter, ParameterSet, ToolContext

class CalculatorTool(ToolBase):
    name = "calculator"
    description = "四则运算"
    tags = ("math",)
    parameters = ParameterSet([
        Parameter("expression", str, description="算式，如 1+2*3", min_length=1),
        Parameter("safe", bool, default=True, description="只允许数字与运算符"),
    ])

    def run(self, ctx: ToolContext, expression: str, safe: bool = True) -> dict:
        if safe and not set(expression) <= set("0123456789+-*/.() "):
            raise ValueError("包含非法字符")
        return {"expression": expression, "result": eval(expression)}  # noqa: S307
```

## CLI

```bash
python -m awtf list   --discover my_tools/          # 列出工具
python -m awtf info   greet --discover my_tools/    # 参数/类型/默认值
python -m awtf run    greet --name 世界 --discover my_tools/   # 运行（JSON 结果）
python -m awtf run    greet --name 世界 --dry-run -v           # 演练+详细日志
python -m awtf docs   greet --discover my_tools/    # 输出 Markdown 文档
python -m awtf new    my_tool --dir my_tools/       # 脚手架
python -m awtf doctor                                # 环境自检
```

## 目录结构

```
awtf/
├── awtf/
│   ├── errors.py        # 错误体系（ToolError 及 6 个子类）
│   ├── parameters.py    # Parameter/ParameterSet：转换、校验、签名推断
│   ├── result.py        # ToolResult：标准化结果
│   ├── context.py       # ToolContext：logger/config/metadata 注入
│   ├── config.py        # 分层配置（JSON/YAML/env）
│   ├── logging_utils.py # 日志配置与捕获
│   ├── base.py          # ToolBase/FunctionTool/@tool
│   ├── registry.py      # ToolRegistry：注册/发现/执行
│   ├── templates.py     # 脚手架模板
│   ├── cli.py           # 命令行
│   ├── sysinfo/         # 系统信息采集（hardware/osinfo/network/runtime）
│   ├── ai/              # 大模型对话（deepseek：stream_chat/chat/@tool deepseek_ask）
│   └── ui/              # UI 组件库（core/widgets/containers/dialogs/feedback + tk_backend）
├── examples/            # 文本工具/文件整理(类工具)/异步工具/sysinfo/ui_demo/DeepSeek 流式对话 示例
├── tests/               # 161 个 pytest 用例（含 sysinfo、AI 与 UI 测试）
└── docs/                # 使用指南 / quickstart / 开发指南 / API 参考 / sysinfo / ui
```

## 文档

- **📖 [使用指南（从零上手完整教程）](docs/使用指南.md)**
- [快速开始](docs/quickstart.md)
- [工具开发指南](docs/authoring_guide.md)
- [API 参考](docs/api_reference.md)
- [💻 sysinfo 系统信息模块 API](docs/sysinfo_api.md)
- [🧩 UI 组件库指南](docs/ui_guide.md)

## 运行测试

```bash
pip install pytest
pytest tests/ -v
```

## License

MIT

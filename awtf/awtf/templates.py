"""
脚手架模板 —— ``awtf new <name>`` 生成新工具文件。

模板内置了工具开发的标准结构：文档字符串规范（用途/参数/返回/示例/错误）、
参数声明示例、ctx 用法、dry-run 支持，让用户从"可运行的正确示例"开始改。

模板使用 ``string.Template``（$占位符），避免与 Python 代码中的
花括号冲突。
"""

from __future__ import annotations

import pathlib
import string
from typing import Tuple

TOOL_TEMPLATE = '''\
"""\
工具：$title

用途：
    $description

参数：
    text   (str)  输入文本
    repeat (int)  重复次数（1-10）

返回：
    dict，包含 input / output / repeat 字段

示例：
    # Python 调用
    from awtf import ToolRegistry
    registry = ToolRegistry()
    registry.discover_path(__file__)
    result = registry.run("$tool_name", {"text": "你好", "repeat": 3})

    # 命令行调用
    python -m awtf run $tool_name --text "你好" --repeat 3 --discover .

错误：
    VALIDATION_ERROR —— 参数缺失或类型不符
    EXECUTION_ERROR  —— 运行时异常（自动包装，含 traceback）
"""

from __future__ import annotations

from awtf import Parameter, ToolContext, tool


@tool(
    name="$tool_name",
    version="0.1.0",
    tags=["custom"],
    author="",
    parameters=[
        Parameter("text", str, description="输入文本", min_length=1),
        Parameter("repeat", int, default=1, min=1, max=10, description="重复次数"),
    ],
)
def $func_name(ctx: ToolContext, text: str, repeat: int = 1) -> dict:
    """$description"""
    ctx.info("执行 $tool_name: text=%s repeat=%s", text, repeat)

    if ctx.dry_run:
        return {"would_do": f"把 {text!r} 重复 {repeat} 次"}

    return {
        "tool": "$tool_name",
        "input": text,
        "output": (text + " ") * repeat,
        "repeat": repeat,
    }
'''

README_TEMPLATE = '''\
# $title

> 由 awtf 脚手架生成的自定义工具。

## 用途

$description

## 安装依赖

```bash
pip install awtf
```

## 使用方式

### 命令行

```bash
# 列出可用工具
python -m awtf list --discover .

# 查看工具详情（参数/类型/默认值）
python -m awtf info $tool_name --discover .

# 运行工具
python -m awtf run $tool_name --text "你好" --repeat 3 --discover .
```

### Python 代码

```python
from awtf import ToolRegistry

registry = ToolRegistry()
registry.discover_path(__file__)  # 或 discover_module("my_tools")

result = registry.run("$tool_name", {"text": "你好", "repeat": 3})
if result.ok:
    print(result.data)
else:
    print("失败:", result.error["message"])
```

## 参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| text | str | 是 | - | 输入文本 |
| repeat | int | 否 | 1 | 重复次数（1-10） |

## 开发

- 直接修改本文件中的函数；参数也可从类型注解自动推断；
- 需要复杂校验时，在 `@tool(parameters=[...])` 中声明 `Parameter`；
- 用 `ctx.logger` / `ctx.info()` 记录日志，`ctx.get_config()` 读配置，
  `ctx.dry_run` 判断演练模式。
'''


def _render(template: str, values: dict) -> str:
    return string.Template(template).substitute(values)


def render_tool_file(tool_name: str, *, description: str = "在这里描述工具用途") -> str:
    """渲染工具 .py 文件内容。"""
    func_name = tool_name.replace("-", "_").replace(" ", "_")
    return _render(TOOL_TEMPLATE, {
        "title": tool_name,
        "tool_name": tool_name,
        "func_name": func_name,
        "description": description,
    })


def render_readme(tool_name: str, *, description: str = "在这里描述工具用途") -> str:
    return _render(README_TEMPLATE, {
        "title": tool_name,
        "tool_name": tool_name,
        "description": description,
    })


def scaffold(tool_name: str, directory: str | pathlib.Path = ".",
             *, with_readme: bool = True,
             description: str = "在这里描述工具用途") -> Tuple[pathlib.Path, pathlib.Path | None]:
    """在目录下生成工具文件（及 README），返回 (工具文件路径, README路径)。

    文件名规则：``tools_<tool_name>.py``（加前缀以避免与标准库冲突）。
    """
    base = pathlib.Path(directory).expanduser()
    base.mkdir(parents=True, exist_ok=True)

    file_name = f"tools_{tool_name.replace('-', '_')}.py"
    tool_path = base / file_name
    if tool_path.exists():
        raise FileExistsError(f"文件已存在: {tool_path}")
    tool_path.write_text(render_tool_file(tool_name, description=description),
                         encoding="utf-8")

    readme_path = None
    if with_readme:
        readme_path = base / "README.md"
        if not readme_path.exists():
            readme_path.write_text(render_readme(tool_name, description=description),
                                   encoding="utf-8")
    return tool_path, readme_path

# hello

> 由 awtf 脚手架生成的自定义工具。

## 用途

在这里描述工具用途

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
python -m awtf info hello --discover .

# 运行工具
python -m awtf run hello --text "你好" --repeat 3 --discover .
```

### Python 代码

```python
from awtf import ToolRegistry

registry = ToolRegistry()
registry.discover_path(__file__)  # 或 discover_module("my_tools")

result = registry.run("hello", {"text": "你好", "repeat": 3})
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

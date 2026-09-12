# 快速开始

## 安装

awtf 核心功能零第三方依赖，Python 3.9+ 即可：

```bash
# 直接从源码使用（把 awtf/ 目录放到 PYTHONPATH）
# 或安装到环境
pip install .

# 可选：YAML 配置支持
pip install pyyaml
```

验证安装：

```bash
python -m awtf doctor
```

## 三种使用方式

### 方式一：脚手架（最快）

```bash
python -m awtf new weather --dir my_tools --description "查询天气"
```

生成 `my_tools/tools_weather.py`，直接编辑函数体，然后：

```bash
python -m awtf run weather --city 北京 --discover my_tools
```

### 方式二：Python API（最常用）

```python
from awtf import tool, ToolRegistry

registry = ToolRegistry()

@registry.tool(tags=["text"])
def reverse(ctx, text: str) -> str:
    """反转文本。

    Args:
        text: 输入文本
    """
    return text[::-1]

result = registry.run("reverse", {"text": "abc"})
print(result.data)  # cba
```

### 方式三：CLI 发现已有工具

把工具写成一个 .py 文件，无需注册语句——CLI 会自动发现：

```python
# my_tools/report.py
from awtf import tool

@tool(name="report")
def report(ctx, title: str, sections: int = 3) -> dict:
    """生成报告骨架。"""
    return {"title": title, "outline": [f"第{i}章" for i in range(1, sections + 1)]}
```

```bash
python -m awtf list --discover my_tools
python -m awtf run report --title 周报 --sections 5 --discover my_tools/report.py
```

## 结果对象

`registry.run()` 永远返回 `ToolResult`，不抛业务异常：

```python
result = registry.run("report", {"title": "x"})

result.ok            # True / False
result.data          # 成功时的返回值
result.error         # 失败时：{code, message, details}
result.duration_ms   # 耗时
result.metadata      # 你传入的元数据（source/request_id/dry_run...）
result.logs          # capture_logs=True 时的执行日志
result.to_dict()     # JSON 安全字典（CLI/IPC 用）
result.raise_for_status()  # 偏好异常流程时使用
```

错误码：

| code | 含义 |
|------|------|
| `VALIDATION_ERROR` | 参数缺失/类型不符/违反约束（field_errors 含全部字段问题） |
| `TOOL_NOT_FOUND` | 工具未注册（details.available 列出可用工具） |
| `EXECUTION_ERROR` | 工具内部异常（details 含 exception_type/traceback） |
| `CONFIG_ERROR` | 配置缺失或格式错误 |
| `REGISTRATION_ERROR` | 注册失败（名称冲突等） |
| `DISCOVERY_ERROR` | 模块发现/导入失败 |

## 下一步

- [工具开发指南](authoring_guide.md)：参数校验、类工具、异步、配置、dry-run 的完整模式
- [API 参考](api_reference.md)：所有公开类与函数

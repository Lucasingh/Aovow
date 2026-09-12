"""
工具基类与装饰器 —— 定义"工具"这一核心抽象。

awtf 支持三种工具形态（对用户难度递增，能力递增）：

1. **函数工具**：用 ``@tool`` 装饰一个普通函数，参数从类型注解自动推断。
   适合 90% 的场景——几行代码就是一个工具。
2. **类工具**：继承 :class:`ToolBase`，实现 ``run(ctx, **params)``，
   显式声明参数与元数据。适合需要状态/复杂校验/生命周期的工具。
3. **异步工具**：函数或 ``run`` 定义为 ``async def``，运行器自动事件循环调度。

工具元数据：name / version / description / tags / author，
用于注册、发现、自动文档与冲突检测。
"""

from __future__ import annotations

import abc
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from .context import ToolContext
from .parameters import Parameter, ParameterSet, infer_parameters


@dataclass
class ToolMeta:
    """工具元数据。"""

    name: str
    description: str = ""
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    author: str = ""
    category: str = "general"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tags": list(self.tags),
            "author": self.author,
            "category": self.category,
        }


class ToolBase(abc.ABC):
    """类工具基类。子类需设置类属性并实现 :meth:`run`。

    示例::

        class EchoTool(ToolBase):
            name = "echo"
            description = "回显输入"
            parameters = ParameterSet([Parameter("text", str, description="文本")])

            def run(self, ctx, text: str) -> str:
                ctx.info("echo: %s", text)
                return text
    """

    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    tags: Sequence[str] = ()
    author: str = ""
    category: str = "general"
    parameters: ParameterSet = ParameterSet()

    def __init__(self) -> None:
        if not getattr(self, "name", ""):
            raise ValueError(f"{type(self).__name__} 必须定义非空 name")
        description = self.description or _first_doc_line(type(self))
        self._meta = ToolMeta(
            name=self.name,
            description=description,
            version=self.version,
            tags=list(self.tags),
            author=self.author,
            category=self.category,
        )

    # ---------- 元信息 ----------

    @property
    def meta(self) -> ToolMeta:
        return self._meta

    @property
    def parameter_set(self) -> ParameterSet:
        return self.parameters

    def describe(self) -> Dict[str, Any]:
        """返回完整描述（元数据 + 参数 schema），用于自动文档/发现。"""
        return {
            **self._meta.to_dict(),
            "parameters": self.parameters.to_list(),
            "kind": "class",
            "async": inspect.iscoroutinefunction(self.run),
        }

    # ---------- 执行 ----------

    @abc.abstractmethod
    def run(self, ctx: ToolContext, **params: Any) -> Any:
        """工具逻辑（子类实现）。

        Args:
            ctx: 执行上下文（logger / config / metadata）。
            **params: 已校验转换后的参数。

        Returns:
            任意可 JSON 序列化的数据（会包进 ToolResult.data）。
        """
        raise NotImplementedError

    async def arun(self, ctx: ToolContext, **params: Any) -> Any:
        """异步执行入口；同步工具默认会把 :meth:`run` 包到线程池。"""
        import asyncio
        return await asyncio.to_thread(self.run, ctx, **params)

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"<Tool {self._meta.name} v{self._meta.version}>"


class FunctionTool(ToolBase):
    """把普通函数包装成工具。通常不直接使用，见 :func:`tool` 装饰器。"""

    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name: str,
        description: str = "",
        parameters: Optional[ParameterSet] = None,
        version: str = "1.0.0",
        tags: Sequence[str] = (),
        author: str = "",
        category: str = "general",
    ) -> None:
        self._func = func
        self._is_async = inspect.iscoroutinefunction(func)
        self.name = name
        self.description = description or _first_doc_line(func)
        self.version = version
        self.tags = list(tags)
        self.author = author
        self.category = category
        self.parameters = parameters or infer_parameters(func)
        super().__init__()

    def __call__(self, ctx: ToolContext, **params: Any) -> Any:
        """像普通函数一样直接调用（不走校验，便于在代码中复用）。"""
        if self._is_async:
            import asyncio
            return asyncio.run(self._func(ctx, **params))
        return self._func(ctx, **params)

    def run(self, ctx: ToolContext, **params: Any) -> Any:
        if self._is_async:
            # 同步入口调用 async 函数：由运行器统一调度；此处兜底
            import asyncio
            return asyncio.run(self._func(ctx, **params))
        return self._func(ctx, **params)

    async def arun(self, ctx: ToolContext, **params: Any) -> Any:
        if self._is_async:
            return await self._func(ctx, **params)
        import asyncio
        return await asyncio.to_thread(self._func, ctx, **params)

    def describe(self) -> Dict[str, Any]:
        d = super().describe()
        d["kind"] = "function"
        d["async"] = self._is_async
        return d


def tool(
    func: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[Sequence[Parameter]] = None,
    version: str = "1.0.0",
    tags: Sequence[str] = (),
    author: str = "",
    category: str = "general",
) -> Callable[..., Any]:
    """装饰器：把函数注册为工具（返回 :class:`FunctionTool` 实例）。

    两种用法::

        @tool
        def my_tool(ctx, x: int) -> int:
            return x + 1

        @tool(name="加一", tags=["math"])
        def add_one(ctx, x: int) -> int:
            ''':param x: 输入数字'''
            return x + 1

    被装饰的函数会变成 FunctionTool 实例——可直接 ``registry.register(func)``，
    也仍可像普通函数一样 ``func(ctx, x=1)`` 调用（实例 __call__ 透传）。
    """

    def _wrap(f: Callable[..., Any]) -> FunctionTool:
        tool_name = name or f.__name__
        pset = ParameterSet(parameters) if parameters else None
        return FunctionTool(
            f,
            name=tool_name,
            description=description or "",
            parameters=pset,
            version=version,
            tags=tags,
            author=author,
            category=category,
        )

    if func is not None and callable(func):
        # @tool 不带括号
        return _wrap(func)
    # @tool(...) 带参数
    return _wrap


def _first_doc_line(obj: Any) -> str:
    """取 docstring 的首个非空行作为默认描述。"""
    doc = inspect.getdoc(obj) or ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return ""

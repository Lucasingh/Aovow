"""
工具注册表与执行器 —— awtf 的核心链路。

端到端链路（单一真源）::

    工具定义(FunctionTool/ToolBase)
        → Registry.register（名称冲突检测 / 版本记录）
        → Registry.run(name, params)
            → ParameterSet.validate（类型转换 + 约束校验，聚合错误）
            → ToolContext 构造（logger/config/metadata）
            → 执行（同步直接调用；async 自动事件循环；可选日志捕获）
            → 异常包装为 ToolExecutionError（保留 traceback）
        → ToolResult（ok/data/error/duration/metadata/logs）

发现机制：
- :meth:`discover_module` 导入模块，自动收集模块内的 ToolBase 实例/子类；
- :meth:`discover_path` 扫描目录下 Python 文件并导入；
- :meth:`discover_entry_points` 读取 ``awtf.tools`` entry points
  （打包发布的工具可被自动发现）。
"""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
import pathlib
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

from .base import FunctionTool, ToolBase
from .context import ToolContext
from .errors import (
    ToolDiscoveryError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolRegistrationError,
    ToolValidationError,
)
from .logging_utils import LogCapture
from .result import ToolResult, format_traceback

# 可注册对象：ToolBase 实例、ToolBase 子类、被 @tool 装饰的函数（FunctionTool 实例）
Registerable = Union[ToolBase, type, Callable[..., Any]]

ENTRY_POINT_GROUP = "awtf.tools"


class ToolRegistry:
    """工具注册表：注册、发现、执行。

    线程安全说明：注册/发现通常在启动阶段单线程完成；run 为只读操作。
    多线程动态注册时请外部加锁。
    """

    def __init__(self, *, name: str = "default") -> None:
        self.name = name
        self._tools: Dict[str, ToolBase] = {}
        self._versions: Dict[str, str] = {}

    # ============================================================
    # 注册 / 注销
    # ============================================================

    def register(self, tool: Registerable, *, override: bool = False) -> ToolBase:
        """注册一个工具。

        Args:
            tool: FunctionTool 实例 / ToolBase 实例 / ToolBase 子类 / 被装饰函数。
            override: 同名工具已存在时是否覆盖；默认 False（抛冲突错误）。

        Raises:
            ToolRegistrationError: 对象不合法或名称冲突。
        """
        instance = self._coerce(tool)
        meta = instance.meta

        if meta.name in self._tools and not override:
            existing_ver = self._versions.get(meta.name, "?")
            raise ToolRegistrationError(
                f"工具名 '{meta.name}' 已存在（v{existing_ver}）；"
                f"如需覆盖请传 override=True，或更换名称/版本",
                tool=meta.name,
                details={"existing_version": existing_ver, "new_version": meta.version},
            )

        self._tools[meta.name] = instance
        self._versions[meta.name] = meta.version
        return instance

    def unregister(self, name: str) -> bool:
        """注销工具，返回是否曾存在。"""
        if name in self._tools:
            del self._tools[name]
            self._versions.pop(name, None)
            return True
        return False

    def tool(self, *, name: Optional[str] = None, override: bool = False,
             **meta: Any) -> Callable[[Callable[..., Any]], FunctionTool]:
        """装饰器：定义并注册函数工具到本注册表。

        用法::

            registry = ToolRegistry()

            @registry.tool(tags=["math"])
            def add(ctx, a: int, b: int = 1) -> int:
                return a + b
        """
        def _decorator(func: Callable[..., Any]) -> FunctionTool:
            from .base import tool as make_tool
            t = make_tool(func, name=name or func.__name__, **meta)
            self.register(t, override=override)
            return t
        return _decorator

    @staticmethod
    def _coerce(tool: Registerable) -> ToolBase:
        """把各种合法输入统一为 ToolBase 实例。"""
        if isinstance(tool, ToolBase):
            return tool
        if inspect.isclass(tool) and issubclass(tool, ToolBase):
            return tool()
        if callable(tool):
            raise ToolRegistrationError(
                f"函数 {getattr(tool, '__name__', tool)} 未使用 @tool 装饰；"
                "请先用 awtf.tool 装饰，或直接传 FunctionTool 实例"
            )
        raise ToolRegistrationError(f"无法注册的对象类型: {type(tool).__name__}")

    # ============================================================
    # 查询
    # ============================================================

    def get(self, name: str) -> ToolBase:
        """按名获取工具；不存在抛 :class:`ToolNotFoundError`。"""
        if name not in self._tools:
            raise ToolNotFoundError(name, available=sorted(self._tools.keys()))
        return self._tools[name]

    def has(self, name: str) -> bool:
        return name in self._tools

    def names(self) -> List[str]:
        return sorted(self._tools.keys())

    def list_tools(self, *, tag: Optional[str] = None,
                   category: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出工具元数据（可按 tag/category 过滤）。"""
        result = []
        for t in self._tools.values():
            d = t.describe()
            if tag and tag not in d.get("tags", []):
                continue
            if category and d.get("category") != category:
                continue
            result.append(d)
        return sorted(result, key=lambda d: d["name"])

    def describe(self, name: str) -> Dict[str, Any]:
        """返回单个工具的完整描述（自动文档用）。"""
        return self.get(name).describe()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    # ============================================================
    # 执行（核心链路）
    # ============================================================

    def run(
        self,
        name: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        capture_logs: bool = False,
        raise_on_error: bool = False,
    ) -> ToolResult:
        """执行工具，返回标准化 :class:`ToolResult`。

        Args:
            name: 工具名。
            params: 参数字典（原始输入，会做类型转换与校验）。
            config: 全局配置（工具可通过 ctx.section_config 读取）。
            metadata: 运行元数据（source / request_id / dry_run 等）。
            capture_logs: 是否捕获执行期间日志到 result.logs。
            raise_on_error: True 时错误直接抛出（默认包装为失败结果）。

        Returns:
            ToolResult：成功 data 为工具返回值；失败 error 为错误字典。
        """
        started = time.time()
        meta = dict(metadata or {})
        params = dict(params or {})

        # 1. 工具存在性
        try:
            tool = self.get(name)
        except ToolNotFoundError as e:
            if raise_on_error:
                raise
            return ToolResult.failure(name, e, started_at=started, metadata=meta)

        # 2. 参数校验（聚合错误）
        try:
            clean_params = tool.parameter_set.validate(params, tool=name)
        except ToolValidationError as e:
            if raise_on_error:
                raise
            return ToolResult.failure(name, e, started_at=started, metadata=meta)

        # 3. 构造上下文
        ctx = ToolContext.create(name, config=config, metadata=meta)

        # 4. 执行（可选日志捕获）
        cap = LogCapture(f"awtf.tools.{name}") if capture_logs else None
        try:
            if cap:
                cap.__enter__()
            data = self._invoke(tool, ctx, clean_params)
        except ToolError as e:
            # 业务可预期错误（工具内部主动抛出）
            if cap:
                cap.__exit__(None, None, None)
            if raise_on_error:
                raise
            return ToolResult.failure(name, e, started_at=started,
                                      metadata=meta, logs=cap.records if cap else [])
        except Exception as e:  # noqa: BLE001 - 执行器必须兜底所有异常
            err = ToolExecutionError(name, e, format_traceback(e))
            if cap:
                cap.__exit__(type(e), e, e.__traceback__)
            if raise_on_error:
                raise err from e
            return ToolResult.failure(name, err, started_at=started,
                                      metadata=meta, logs=cap.records if cap else [])
        else:
            if cap:
                cap.__exit__(None, None, None)
            return ToolResult.success(name, data, started_at=started,
                                      metadata=meta, logs=cap.records if cap else [])

    @staticmethod
    def _invoke(tool: ToolBase, ctx: ToolContext, params: Dict[str, Any]) -> Any:
        """同步/异步统一调度。"""
        is_async = bool(tool.describe().get("async"))
        if is_async:
            return _run_async(tool.arun(ctx, **params))
        return tool.run(ctx, **params)

    # ============================================================
    # 发现机制
    # ============================================================

    def discover_module(self, module: Union[str, Any]) -> List[str]:
        """导入模块并注册其中所有工具，返回注册的工具名列表。

        Args:
            module: 模块名字符串（"my_pkg.tools"）或已导入的模块对象。
        """
        if isinstance(module, str):
            try:
                mod = importlib.import_module(module)
            except ImportError as e:
                raise ToolDiscoveryError(f"无法导入模块 '{module}': {e}") from e
        else:
            mod = module

        found: List[str] = []
        for attr_name in dir(mod):
            obj = getattr(mod, attr_name)
            if isinstance(obj, ToolBase):
                self.register(obj)
                found.append(obj.meta.name)
            elif inspect.isclass(obj) and issubclass(obj, ToolBase) \
                    and obj is not ToolBase and obj.__module__ == mod.__name__:
                instance = self.register(obj)
                found.append(instance.meta.name)
        return found

    def discover_path(self, path: Union[str, pathlib.Path], *,
                      pattern: str = "*.py") -> List[str]:
        """扫描目录（或单个 .py 文件），导入并注册其中的工具。

        目录会被加入 sys.path，文件内可用常规 import。
        """
        p = pathlib.Path(path).expanduser()
        if not p.exists():
            raise ToolDiscoveryError(f"发现路径不存在: {p}", details={"path": str(p)})

        files: List[pathlib.Path]
        if p.is_file():
            files = [p]
            sys.path.insert(0, str(p.parent))
        else:
            files = sorted(p.glob(pattern))
            sys.path.insert(0, str(p))

        found: List[str] = []
        for f in files:
            if f.name.startswith("_"):
                continue
            mod_name = f"_awtf_dyn_{f.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, f)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            try:
                spec.loader.exec_module(mod)
            except Exception as e:  # noqa: BLE001
                raise ToolDiscoveryError(
                    f"导入工具文件失败 {f.name}: {e}",
                    details={"file": str(f)}) from e
            found.extend(self.discover_module(mod))
        return found

    def discover_entry_points(self, group: str = ENTRY_POINT_GROUP) -> List[str]:
        """发现通过 setuptools entry points 发布的工具。

        工具包在 pyproject.toml 声明::

            [project.entry-points."awtf.tools"]
            my_tool = "my_pkg.tools:register"
        """
        try:
            eps = importlib.metadata.entry_points()
            selected = eps.select(group=group) if hasattr(eps, "select") else [
                ep for ep in eps.get(group, [])  # type: ignore[union-attr]
            ]
        except Exception as e:  # noqa: BLE001
            raise ToolDiscoveryError(f"读取 entry points 失败: {e}") from e

        found: List[str] = []
        for ep in selected:
            loaded = ep.load()
            if isinstance(loaded, ToolBase):
                self.register(loaded)
                found.append(loaded.meta.name)
            elif isinstance(loaded, ToolRegistry):
                for t in list(loaded._tools.values()):
                    self.register(t)
                    found.append(t.meta.name)
            elif callable(loaded):
                # 工厂函数：返回 ToolBase / ToolRegistry / 可迭代
                result = loaded()
                self._absorb_factory_result(result, found)
        return found

    def _absorb_factory_result(self, result: Any, found: List[str]) -> None:
        if isinstance(result, ToolBase):
            self.register(result)
            found.append(result.meta.name)
        elif isinstance(result, ToolRegistry):
            for t in list(result._tools.values()):
                self.register(t)
                found.append(t.meta.name)
        elif isinstance(result, (list, tuple)):
            for item in result:
                self._absorb_factory_result(item, found)


def _run_async(coro: Any) -> Any:
    """在同步上下文中运行协程。

    无运行中的事件循环时用 ``asyncio.run``（自动建/销循环）；
    若已在事件循环中（少见，如 Jupyter），新建独立循环执行。
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================
# 模块级默认注册表（便捷使用）
# ============================================================

_default_registry: Optional[ToolRegistry] = None


def get_default_registry() -> ToolRegistry:
    """获取进程级默认注册表（单例）。"""
    global _default_registry
    if _default_registry is None:
        _default_registry = ToolRegistry(name="global")
    return _default_registry

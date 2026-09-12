"""
工具注册表

负责工具的注册、发现、懒加载和生命周期管理。
"""

import logging
from typing import Dict, List, Optional, Type, Iterator
from collections import OrderedDict

from .base_tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    工具注册表。

    管理所有已注册的工具，支持：
    - 按分类分组
    - 懒加载（工具实例在首次激活时才创建）
    - 激活状态追踪

    使用方式:
        registry = ToolRegistry()
        registry.register(MyTool)  # 注册工具类
        registry.activate("my_tool")  # 激活指定工具
    """

    def __init__(self):
        # 已注册的工具类 {tool_id: Type[BaseTool]}
        self._tool_classes: OrderedDict[str, Type[BaseTool]] = OrderedDict()
        # 已实例化的工具 {tool_id: BaseTool}
        self._tool_instances: Dict[str, BaseTool] = {}
        # 当前激活的工具
        self._active_tool: Optional[BaseTool] = None

    # ========== 注册 ==========

    def register(self, tool_cls: Type[BaseTool]):
        """
        注册工具类。

        工具在注册时不会实例化，仅在首次激活时创建。

        Args:
            tool_cls: 工具类（非实例）
        """
        # 创建临时实例获取 tool_id（不触发 widget 创建）
        temp = tool_cls.__new__(tool_cls)
        if not hasattr(temp, 'tool_id'):
            logger.error(f"工具类 {tool_cls.__name__} 未定义 tool_id，无法注册")
            return

        tool_id = temp.tool_id

        if tool_id in self._tool_classes:
            logger.warning(f"工具 {tool_id} 已注册，将被覆盖")

        self._tool_classes[tool_id] = tool_cls
        logger.info(f"工具已注册: {tool_id} ({temp.name})")

    def unregister(self, tool_id: str):
        """注销工具"""
        if tool_id in self._tool_classes:
            del self._tool_classes[tool_id]
        if tool_id in self._tool_instances:
            self._tool_instances[tool_id].on_close()
            del self._tool_instances[tool_id]
        logger.info(f"工具已注销: {tool_id}")

    # ========== 查询 ==========

    def get(self, tool_id: str) -> Optional[BaseTool]:
        """获取工具实例（懒加载）"""
        if tool_id not in self._tool_instances:
            tool_cls = self._tool_classes.get(tool_id)
            if tool_cls is None:
                logger.warning(f"工具不存在: {tool_id}")
                return None
            # 懒加载实例化
            self._tool_instances[tool_id] = tool_cls()
        return self._tool_instances[tool_id]

    def get_active(self) -> Optional[BaseTool]:
        """获取当前激活的工具"""
        return self._active_tool

    def list_all(self) -> List[BaseTool]:
        """列出所有已注册的工具（返回元数据，不触发加载）"""
        result = []
        for tool_id, tool_cls in self._tool_classes.items():
            temp = tool_cls.__new__(tool_cls)
            result.append(temp)
        return result

    def get_categories(self) -> Dict[str, List[BaseTool]]:
        """按分类分组获取工具列表"""
        categories: Dict[str, List[BaseTool]] = {}
        for tool in self.list_all():
            cat = tool.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(tool)
        return categories

    # ========== 激活管理 ==========

    def activate(self, tool_id: str) -> Optional[BaseTool]:
        """
        激活指定工具。

        会先停用当前工具，然后激活目标工具。
        """
        # 停用当前工具
        if self._active_tool:
            self._active_tool.on_deactivate()

        # 获取或创建目标工具
        tool = self.get(tool_id)
        if tool is None:
            return None

        # 激活新工具
        self._active_tool = tool
        tool.on_activate()
        logger.debug(f"工具已激活: {tool_id}")
        return tool

    def deactivate_current(self):
        """停用当前工具"""
        if self._active_tool:
            self._active_tool.on_deactivate()
            self._active_tool = None

    # ========== 生命周期 ==========

    def shutdown(self):
        """关闭所有工具，释放资源"""
        self.deactivate_current()
        for tool in self._tool_instances.values():
            try:
                tool.on_close()
            except Exception as e:
                logger.error(f"关闭工具 {tool.tool_id} 时出错: {e}")
        self._tool_instances.clear()
        self._tool_classes.clear()

    # ========== 遍历 ==========

    @property
    def tool_count(self) -> int:
        """已注册的工具数量"""
        return len(self._tool_classes)

    def __iter__(self) -> Iterator[str]:
        return iter(self._tool_classes.keys())

    def __contains__(self, tool_id: str) -> bool:
        return tool_id in self._tool_classes if isinstance(tool_id, str) else False

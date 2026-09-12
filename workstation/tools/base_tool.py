"""
工具基类

所有工具插件必须继承此基类并实现必要接口。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from PySide6.QtWidgets import QWidget


class BaseTool(ABC):
    """
    工具插件基类。

    每个工具需要提供：
    - tool_id: 唯一标识
    - name: 显示名称
    - icon: 图标标识（emoji 或路径）
    - category: 分类（用于侧边栏分组）
    - widget: 工具的主界面控件

    生命周期：
    1. __init__() - 工具实例化
    2. on_activate() - 用户切换到该工具时调用
    3. on_deactivate() - 用户切换到其他工具时调用
    4. on_close() - 应用关闭时调用
    """

    @property
    @abstractmethod
    def tool_id(self) -> str:
        """工具唯一标识符"""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """工具显示名称"""
        ...

    @property
    @abstractmethod
    def icon(self) -> str:
        """工具图标（emoji字符或图标文件路径）"""
        ...

    @property
    def category(self) -> str:
        """工具分类，默认为"通用" """
        return "通用"

    @property
    def description(self) -> str:
        """工具描述"""
        return ""

    @property
    @abstractmethod
    def widget(self) -> QWidget:
        """工具的主界面控件（懒加载，首次访问时创建）"""
        ...

    def on_activate(self):
        """当工具被激活（显示）时调用"""
        pass

    def on_deactivate(self):
        """当工具被停用（隐藏）时调用"""
        pass

    def on_close(self):
        """当应用关闭时调用，用于清理资源"""
        pass

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取工具专属配置"""
        from workstation.core.application import Application
        # 此处为简化实现，实际应通过依赖注入
        return default

    def __repr__(self):
        return f"<Tool: {self.tool_id} ({self.name})>"

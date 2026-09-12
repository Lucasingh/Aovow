"""
全局信号总线

基于 PySide6 信号/槽机制，实现模块间松耦合通信。
所有跨模块事件通过此总线传递，避免直接依赖。
"""

from PySide6.QtCore import QObject, Signal


class SignalBus(QObject):
    """
    全局事件总线，单例模式。

    所有模块通过订阅/发布信号进行通信，
    无需直接引用其他模块实例。

    使用方式:
        bus = SignalBus()
        bus.tool_activated.connect(my_handler)
        bus.tool_activated.emit("tool_id")
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 必须在 __init__ 前调用，QObject 需要正确的初始化
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            super().__init__()
            self._initialized = True

    # ---- 应用生命周期 ----
    app_started = Signal()
    """应用启动完成"""

    app_closing = Signal()
    """应用即将关闭"""

    # ---- 工具管理 ----
    tool_registered = Signal(str)
    """工具注册通知，携带 tool_id"""

    tool_activated = Signal(str)
    """工具被激活，携带 tool_id"""

    tool_deactivated = Signal(str)
    """工具被停用，携带 tool_id"""

    # ---- 导航 ----
    sidebar_toggled = Signal(bool)
    """侧边栏展开/收起，携带展开状态"""

    navigation_changed = Signal(str)
    """导航页面切换，携带目标页面标识"""

    # ---- 状态 ----
    status_message = Signal(str, int)
    """状态栏消息，携带消息文本和显示时长(ms)"""

    # ---- 主题 ----
    theme_changed = Signal(str)
    """主题切换，携带主题名称"""

    # ---- 响应式布局 ----
    responsive_changed = Signal()
    """窗口尺寸变化，子组件需更新响应式尺寸"""

    # ---- 性能监控 ----
    performance_update = Signal(dict)
    """性能数据更新，携带性能指标字典"""

    # ---- 认证 ----
    user_logged_in = Signal(dict)
    """用户登录成功，携带用户信息字典"""

    user_logged_out = Signal()
    """用户登出"""

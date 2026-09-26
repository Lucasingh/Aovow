"""
应用生命周期管理器

负责：
1. 初始化配置、服务、UI 组件
2. 协调各模块的启动和关闭顺序
3. 全局异常处理和优雅退出
"""

import sys
import logging
import traceback
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPalette, QColor

from .signals import SignalBus
from .services import ServiceManager

logger = logging.getLogger(__name__)


class Application:
    """
    工作站应用主控制器。

    管理从启动到关闭的完整生命周期，
    按序初始化各子系统并处理清理工作。

    使用方式:
        app = Application(sys.argv)
        app.run()
    """

    def __init__(self, argv: list):
        # ---- 基础属性 ----
        self._app: Optional[QApplication] = None
        self._main_window = None
        self._start_time = None
        self._project_root = Path(__file__).parent.parent

        # ---- 初始化信号总线（最早初始化） ----
        self.signals = SignalBus()

        # ---- 初始化服务管理器 ----
        self.services = ServiceManager()

        # ---- 创建 QApplication ----
        self._setup_qt_app(argv)

        # ---- 初始化各子系统引用 ----
        self.animation_manager = None
        self.tool_registry = None
        self.config_manager = None

    def _setup_qt_app(self, argv: list):
        """配置 Qt 应用基础设置"""
        # 启用高 DPI 缩放（Qt6 默认启用，显式声明以确保兼容）
        if hasattr(Qt.ApplicationAttribute, 'AA_EnableHighDpiScaling'):
            QApplication.setAttribute(
                Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True
            )
        if hasattr(Qt.ApplicationAttribute, 'AA_UseHighDpiPixmaps'):
            QApplication.setAttribute(
                Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True
            )

        self._app = QApplication(argv)
        self._app.setApplicationName("Aovow Workstation")
        self._app.setApplicationVersion("1.0.0")
        self._app.setOrganizationName("Aovow")

        # 设置默认字体
        font = QFont("Microsoft YaHei UI" if sys.platform == "win32" else "SF Pro Display", 10)
        self._app.setFont(font)

    def run(self):
        """启动应用主循环"""
        import time
        self._start_time = time.perf_counter()

        logger.info("正在启动 Aovow Workstation...")

        # 1. 加载配置
        self._init_config()

        # 2. 初始化动画管理器
        self._init_animation()

        # 3. 初始化工具注册表
        self._init_tools()

        # 4. 初始化主窗口（最后，依赖其他模块）
        self._init_ui()

        # 5. 连接关闭信号
        self._app.aboutToQuit.connect(self._on_closing)

        # 6. 通知启动完成
        elapsed = (time.perf_counter() - self._start_time) * 1000
        logger.info(f"启动完成，耗时 {elapsed:.1f}ms")
        self.signals.app_started.emit()
        self.signals.status_message.emit(f"就绪 - 启动耗时 {elapsed:.0f}ms", 5000)

        # 7. 进入事件循环
        try:
            sys.exit(self._app.exec())
        except Exception as e:
            logger.critical(f"应用异常退出: {e}")
            traceback.print_exc()

    def _init_config(self):
        """延迟加载配置模块"""
        from workstation.config.settings import ConfigManager
        self.config_manager = ConfigManager()
        self.config_manager.load()

    def _init_animation(self):
        """延迟加载动画模块"""
        from workstation.animation.manager import AnimationManager
        self.animation_manager = AnimationManager()

    def _init_tools(self):
        """延迟加载工具管理模块"""
        from workstation.tools.registry import ToolRegistry
        self.tool_registry = ToolRegistry()

        # 注册内置工具
        from workstation.tools.login_tool import LoginTool
        from workstation.tools.tutorial_tool import TutorialTool
        from workstation.tools.hello_world_tool import HelloWorldTool
        from workstation.tools.perf_monitor_tool import PerfMonitorTool
        from workstation.tools.deepseek_chat_tool import DeepSeekChatTool
        from workstation.tools.tool_designer_tool import ToolDesignerTool

        self.tool_registry.register(LoginTool)
        self.tool_registry.register(TutorialTool)
        self.tool_registry.register(HelloWorldTool)
        self.tool_registry.register(PerfMonitorTool)
        self.tool_registry.register(DeepSeekChatTool)
        self.tool_registry.register(ToolDesignerTool)

        # 通知侧边栏刷新
        self.signals.tool_registered.emit(LoginTool.tool_id)
        self.signals.tool_registered.emit(TutorialTool.tool_id)
        self.signals.tool_registered.emit(HelloWorldTool.tool_id)
        self.signals.tool_registered.emit(PerfMonitorTool.tool_id)
        self.signals.tool_registered.emit(DeepSeekChatTool.tool_id)
        self.signals.tool_registered.emit(ToolDesignerTool.tool_id)

        # 设计器生成的工具：启动时加载已有 + 运行时监听新工具
        self.signals.designer_tool_created.connect(self._register_designer_tool)
        self._load_designer_tools()

    def _load_designer_tools(self):
        """启动时加载设计器生成的工具（workstation/designer_tools/*.py）。"""
        from pathlib import Path
        from workstation.tools.tool_designer_tool import DESIGNER_DIR, camel_class
        import importlib.util

        DESIGNER_DIR.mkdir(parents=True, exist_ok=True)
        for f in sorted(DESIGNER_DIR.glob("*.py")):
            if f.name.startswith("_"):
                continue
            try:
                mod_name = f"designer_tools.{f.stem}"
                spec = importlib.util.spec_from_file_location(mod_name, f)
                mod = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = mod
                spec.loader.exec_module(mod)
                cls = getattr(mod, camel_class(f.stem))
                self.tool_registry.register(cls)
                self.signals.tool_registered.emit(cls.tool_id)
            except Exception as e:  # noqa: BLE001 —— 单个工具失败不影响启动
                logger.warning("设计器工具加载失败 %s: %s", f.name, e)

    def _register_designer_tool(self, tool_id: str):
        """运行时收到 designer_tool_created 信号后动态注册单个工具。"""
        from pathlib import Path
        from workstation.tools.tool_designer_tool import DESIGNER_DIR, camel_class
        import importlib.util

        f = DESIGNER_DIR / f"{tool_id}.py"
        if not f.exists():
            logger.warning("设计器工具文件不存在: %s", f)
            return
        try:
            mod_name = f"designer_tools.{tool_id}"
            spec = importlib.util.spec_from_file_location(mod_name, f)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            cls = getattr(mod, camel_class(tool_id))
            self.tool_registry.register(cls)
            self.signals.tool_registered.emit(cls.tool_id)
            logger.info("设计器工具已注册: %s", tool_id)
        except Exception as e:  # noqa: BLE001 —— 展示给用户而非崩溃
            logger.warning("设计器工具注册失败 %s: %s", tool_id, e)

    def _init_ui(self):
        """延迟加载并显示主窗口"""
        from workstation.ui.main_window import MainWindow
        self._main_window = MainWindow(
            signals=self.signals,
            animation_manager=self.animation_manager,
            tool_registry=self.tool_registry,
            config_manager=self.config_manager,
        )
        self._main_window.show()

    def _on_closing(self):
        """应用关闭前的清理工作"""
        logger.info("正在关闭应用...")
        self.signals.app_closing.emit()

        # 关闭所有服务
        self.services.shutdown()
        logger.info("应用已关闭")

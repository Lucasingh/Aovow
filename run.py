"""
Aovow Workstation 启动入口

使用方式:
    python run.py
    或
    python -m workstation
"""

import sys
import logging
from pathlib import Path

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def setup_logging(level: str = "INFO"):
    """配置日志系统"""
    log_format = "[%(asctime)s] %(levelname)-7s %(name)s: %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt="%H:%M:%S",
    )


def main():
    """主入口函数"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Aovow Workstation 正在启动...")

    from workstation.core.application import Application
    app = Application(sys.argv)
    app.run()


if __name__ == "__main__":
    main()

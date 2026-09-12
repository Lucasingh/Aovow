"""
日志工具 —— 统一的工具日志配置与按工具命名的 logger。

- :func:`setup_logging` 配置根 logger（控制台/文件），可重复调用；
- :func:`get_tool_logger` 返回 ``awtf.tools.<name>`` 命名 logger，
  工具内直接使用，无需关心配置；
- :class:`LogCapture` 是上下文管理器，可把一次工具执行期间的日志收集到
  内存（写入 :class:`~awtf.result.ToolResult`），便于上层展示。
"""

from __future__ import annotations

import logging
import pathlib
from typing import List, Optional

_ROOT_CONFIGURED = False
_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%H:%M:%S"


def setup_logging(
    level: str | int = logging.INFO,
    *,
    log_file: Optional[str | pathlib.Path] = None,
    force: bool = False,
) -> None:
    """配置 awtf 根 logger（控制台 + 可选文件）。

    Args:
        level: 日志级别（"DEBUG"/"INFO"/... 或 logging 常量）。
        log_file: 日志文件路径；None 表示仅控制台。
        force: 为 True 时清除已有 handler 重新配置。
    """
    global _ROOT_CONFIGURED
    root = logging.getLogger("awtf")
    if _ROOT_CONFIGURED and not force:
        root.setLevel(level)
        return

    if force:
        for h in list(root.handlers):
            root.removeHandler(h)

    root.setLevel(level)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file:
        path = pathlib.Path(log_file).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    root.propagate = False
    _ROOT_CONFIGURED = True


def get_tool_logger(tool_name: str) -> logging.Logger:
    """获取工具专属 logger（``awtf.tools.<tool_name>``）。"""
    return logging.getLogger(f"awtf.tools.{tool_name}")


class LogCapture(logging.Handler):
    """日志捕获器：把指定 logger 在执行期间产生的记录收集为字符串列表。

    用法::

        with LogCapture("awtf.tools.my_tool") as cap:
            result = registry.run("my_tool", ...)
        result.logs.extend(cap.records)
    """

    def __init__(self, logger_name: str = "awtf", level: int = logging.DEBUG) -> None:
        super().__init__(level)
        self.records: List[str] = []
        self._target = logging.getLogger(logger_name)
        self.setFormatter(logging.Formatter("[%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.records.append(self.format(record))
        except Exception:  # pragma: no cover - 日志绝不能打断主流程
            self.handleError(record)

    def __enter__(self) -> "LogCapture":
        self._target.addHandler(self)
        self._old_level = self._target.level
        if not self._target.isEnabledFor(self.level):
            self._target.setLevel(self.level)
        return self

    def __exit__(self, *exc: object) -> None:
        self._target.removeHandler(self)
        self._target.setLevel(self._old_level)

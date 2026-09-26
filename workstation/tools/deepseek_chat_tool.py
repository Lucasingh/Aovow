"""
DeepSeek 对话工具（工作站 PySide6 界面 + AWTF AI 数据层）

- 填 DeepSeek API Key（优先：界面输入 > DEEPSEEK_API_KEY/AOVOW_AI_API_KEY 环境变量
  > ~/.aovow/settings.yaml 的 ai.deepseek_api_key）
- 与 DeepSeek 流式对话：后台 QThread 读 SSE → Signal 增量渲染，界面不卡
- 模型可选 deepseek-chat / deepseek-reasoner
- 全程无 os.system，仅跨平台 API

数据层来自 AWTF：awtf.ai.stream_chat（零第三方依赖）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 确保 awtf 真包可导入（editable finder 会被 cwd namespace 抢占，显式引导真包父目录）
_AWTF_ROOT = Path(__file__).resolve().parent.parent.parent / "awtf"
if _AWTF_ROOT.is_dir() and str(_AWTF_ROOT) not in sys.path:
    sys.path.insert(0, str(_AWTF_ROOT))

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTextBrowser, QFrame,
)

from awtf.ai import DEFAULT_MODEL, MODELS, stream_chat

from workstation.tools.base_tool import BaseTool
from workstation.ui.styles import COLORS

# ~/.aovow/settings.yaml 里的 ai.deepseek_api_key
_SETTINGS_PATH = Path.home() / ".aovow" / "settings.yaml"


def _settings_api_key() -> str:
    """从 ~/.aovow/settings.yaml 读取 ai.deepseek_api_key（失败静默）。"""
    try:
        import yaml
        data = yaml.safe_load(_SETTINGS_PATH.read_text(encoding="utf-8")) or {}
        key = ((data.get("ai") or {}).get("deepseek_api_key") or "").strip()
        return key
    except Exception:
        return ""


def resolve_api_key(field_value: str) -> str:
    """API Key 优先级：界面输入 > 环境变量 > settings.yaml。"""
    if field_value.strip():
        return field_value.strip()
    for env in ("DEEPSEEK_API_KEY", "AOVOW_AI_API_KEY"):
        value = os.environ.get(env)
        if value and value.strip():
            return value.strip()
    return _settings_api_key()


class _ChatWorker(QThread):
    """后台流式线程：读 SSE，通过信号发回主线程（UI 更新只在主线程）。

    注意：信号名避开 QThread 内置信号（finished 等）。
    """

    chunk_received = Signal(str)
    done_received = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, api_key: str, messages: list, model: str, parent=None):
        super().__init__(parent)
        self._api_key = api_key
        self._messages = messages
        self._model = model

    def run(self):
        parts: list[str] = []
        try:
            for chunk in stream_chat(self._api_key, self._messages, model=self._model):
                if self.isInterruptionRequested():
                    break
                parts.append(chunk)
                self.chunk_received.emit(chunk)
            if not self.isInterruptionRequested():
                self.done_received.emit("".join(parts))
        except Exception as e:  # noqa: BLE001 —— 网络/API 错误回传 UI
            self.error_occurred.emit(str(e))


class DeepSeekChatTool(BaseTool):
    """DeepSeek 流式对话工具。"""

    tool_id = "deepseek_chat"
    name = "DeepSeek 对话"
    icon = "🤖"
    category = "AI"
    description = "填写 DeepSeek API Key，与 DeepSeek 流式对话"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._messages: list[dict] = []
        self._busy = False
        self._worker: _ChatWorker | None = None
        self._widget: QWidget | None = None
        self._send_btn: QPushButton | None = None

    @property
    def widget(self) -> QWidget:
        if self._widget is None:
            self._widget = self._build_widget()
        return self._widget

    def _build_widget(self) -> QWidget:
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        # 顶部：标题 + Key + 模型
        title = QLabel("🤖 DeepSeek 流式对话")
        title.setStyleSheet(f"font-size:18px;font-weight:700;color:{COLORS['fg_primary']};"
                            f"background:{COLORS['bg_base']};border:none;")
        root.addWidget(title)

        key_row = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText(
            "DeepSeek API Key（留空则用环境变量 / ~/.aovow/settings.yaml）")
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setStyleSheet(self._input_style())
        key_row.addWidget(QLabel("API Key"), 0)
        key_row.addWidget(self._key_input, 3)

        self._model_box = QComboBox()
        self._model_box.addItems(list(MODELS))
        self._model_box.setCurrentText(DEFAULT_MODEL)
        self._model_box.setStyleSheet(self._input_style())
        key_row.addWidget(QLabel("模型"), 0)
        key_row.addWidget(self._model_box, 1)
        root.addLayout(key_row)

        # 中部：聊天记录
        self._chat = QTextBrowser()
        self._chat.setOpenExternalLinks(False)
        self._chat.setStyleSheet(
            f"QTextBrowser{{background:{COLORS['bg_secondary']};color:{COLORS['fg_primary']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;"
            f"font-size:14px;padding:10px;}}")
        self._chat.append("👋 欢迎与 DeepSeek 对话！\n")
        root.addWidget(self._chat, 1)

        # 底部：输入 + 发送
        bottom = QFrame()
        bottom.setStyleSheet("background:transparent;border:none;")
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(0, 0, 0, 0)
        self._input = QLineEdit()
        self._input.setPlaceholderText("输入消息，回车发送")
        self._input.returnPressed.connect(self._send)
        self._input.setStyleSheet(self._input_style())
        self._send_btn = QPushButton("发送")
        self._send_btn.setStyleSheet(
            f"QPushButton{{background:{COLORS['accent']};color:#fff;"
            f"border:none;border-radius:8px;padding:8px 22px;font-weight:600;}}"
            f"QPushButton:disabled{{background:{COLORS['border']};}}")
        self._send_btn.clicked.connect(self._send)
        bl.addWidget(self._input, 1)
        bl.addWidget(self._send_btn)
        root.addWidget(bottom)

        return w

    # ---------- 交互 ----------

    def _send(self):
        if self._busy:
            return
        text = self._input.text().strip()
        if not text:
            return
        api_key = resolve_api_key(self._key_input.text())
        if not api_key:
            self._chat.append("\n[提示] 请填写 DeepSeek API Key，"
                              "或设置 DEEPSEEK_API_KEY 环境变量。\n")
            return

        self._chat.append(f"\n🧑 你：{text}\n")
        self._chat.append("🤖 DeepSeek：")
        self._messages.append({"role": "user", "content": text})
        self._input.clear()

        model = self._model_box.currentText()
        self._busy = True
        self._send_btn.setEnabled(False)

        self._worker = _ChatWorker(api_key, self._messages, model, self._widget)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.done_received.connect(self._on_done)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.start()

    def _on_chunk(self, chunk: str):
        self._chat.insertPlainText(chunk)
        sb = self._chat.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_done(self, full: str):
        self._busy = False
        self._send_btn.setEnabled(True)
        self._chat.insertPlainText("\n")
        if full:
            self._messages.append({"role": "assistant", "content": full})

    def _on_error(self, msg: str):
        self._busy = False
        self._send_btn.setEnabled(True)
        self._chat.append(f"\n[错误] {msg}\n")

    def on_activate(self):
        """激活（显示）时无需额外操作，懒加载 widget 即可。"""
        _ = self.widget

    def on_deactivate(self):
        """停用时停止流式线程。"""
        self.stop()

    def on_close(self):
        """应用关闭时清理。"""
        self.stop()

    def stop(self):
        """停止流式线程（QThread 不阻塞 UI）。"""
        if self._worker and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker.wait(1000)
            if self._worker.isRunning():
                self._worker.terminate()
                self._worker.wait()
            self._worker = None
        self._busy = False
        if self._send_btn is not None:
            self._send_btn.setEnabled(True)

    def _input_style(self) -> str:
        return (f"QLineEdit{{background:{COLORS['bg_secondary']};color:{COLORS['fg_primary']};"
                f"border:1px solid {COLORS['border']};border-radius:8px;"
                f"padding:6px 10px;font-size:13px;}}"
                f"QLineEdit:focus{{border:1px solid {COLORS['accent']};}}")

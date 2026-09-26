"""
DeepSeek 流式对话示例（基于 AWTF UI 组件库 + AWTF AI 模块）

功能：
- 填写 DeepSeek API Key（密码框，不落盘）与模型名
- 与 DeepSeek 对话，**流式输出**（SSE 边生成边渲染，不卡界面）
- 回车或按钮发送；清空会话；错误提示

实现要点：
- 请求零第三方依赖：awtf.ai.stream_chat（urllib 标准库 + SSE 逐行解析）
- 流式：后台线程读取 SSE → queue → 主线程 after 轮询 → TextArea 追加渲染
  （Tk 非线程安全，UI 更新只在主线程）
- UI 全部由 AWTF 组件构建：InputField/InputSpec/ButtonSpec/CardSpec/TextAreaSpec

运行（需要图形环境）：
    python examples/deepseek_chat_demo.py
"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from awtf.ai import DEFAULT_MODEL, stream_chat  # noqa: E402
from awtf.ui import (  # noqa: E402
    App,
    ButtonSpec,
    CardSpec,
    DividerSpec,
    IconSpec,
    InputField,
    InputSpec,
    LabelSpec,
    RowSpec,
    TextAreaSpec,
    show_message,
    MessageDialog,
)
from awtf.ui.tk_backend import AppWindow  # noqa: E402


class DeepSeekChat(AppWindow):
    """DeepSeek 聊天窗口：AWTF AppWindow 子类 + 流式调度。"""

    def __init__(self):
        app = App(
            title="DeepSeek 对话（AWTF UI 示例）",
            width=680, height=720,
            children=[
                RowSpec([
                    IconSpec("🤖", size=22),
                    LabelSpec("DeepSeek 流式对话", bold=True, size=16),
                ]),
                CardSpec(title="连接设置", children=[
                    InputSpec(InputField(
                        "api_key", label="DeepSeek API Key", kind="password",
                        required=True, placeholder="sk-...",
                        hint="仅保存在本窗口内存，关闭即清除")),
                    RowSpec([
                        LabelSpec("模型"),
                        InputSpec(InputField(
                            "model", label="", default=DEFAULT_MODEL,
                            placeholder=DEFAULT_MODEL)),
                    ]),
                ]),
                TextAreaSpec("chat", height=20, readonly=True,
                             text="👋 欢迎与 DeepSeek 对话！\n\n"
                                  "请在下方输入消息后回车或点发送。\n\n"),
                DividerSpec(),
                CardSpec(title="发送消息", children=[
                    InputSpec(
                        InputField("input", label="", required=True,
                                   placeholder="输入消息，回车发送"),
                        on_submit="on_send"),
                    RowSpec([
                        ButtonSpec("发送", on_click="on_send"),
                        ButtonSpec("清空会话", style="ghost", on_click="on_clear"),
                    ]),
                ]),
            ],
        )
        super().__init__(app, {
            "on_send": self.on_send,
            "on_clear": self.on_clear,
        })
        self._messages: list[dict] = []
        self._busy = False
        self._q: queue.Queue = queue.Queue()
        self.root.after(40, self._poll)

    # ---------- 交互 ----------

    def on_send(self, payload=None):
        if self._busy:
            return
        values = self.get_values()  # 始终从输入框取最新值（按钮回调不带 payload）
        text = (values.get("input") or "").strip()
        if not text:
            return
        api_key = (values.get("api_key") or "").strip()
        if not api_key:
            show_message(self.root, MessageDialog(
                "提示", "请先填写 DeepSeek API Key", level="warning"))
            return

        self.append_text("chat", f"\n🧑 你：{text}\n")
        self._messages.append({"role": "user", "content": text})
        self._inputs["input"].delete(0, "end")

        model = (values.get("model") or "").strip() or DEFAULT_MODEL
        self._busy = True
        threading.Thread(
            target=self._worker, args=(api_key, model),
            daemon=True).start()

    def on_clear(self, _payload=None):
        if self._busy:
            return
        self._messages.clear()
        text = self.text_areas.get("chat")
        if text is not None:
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", "👋 会话已清空，开始新一轮对话吧！\n\n")
            text.configure(state="disabled")

    # ---------- 流式 ----------

    def _worker(self, api_key: str, model: str):
        parts: list[str] = []
        try:
            for chunk in stream_chat(api_key, self._messages, model=model):
                parts.append(chunk)
                self._q.put(("chunk", chunk))
            self._q.put(("done", "".join(parts)))
        except Exception as e:  # noqa: BLE001 —— 网络/API 错误统一回传 UI
            self._q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                kind, data = self._q.get_nowait()
                if kind == "chunk":
                    self.append_text("chat", data)
                elif kind == "done":
                    self._busy = False
                    self.append_text("chat", "\n")
                    if data:
                        self._messages.append(
                            {"role": "assistant", "content": data})
                elif kind == "error":
                    self._busy = False
                    self.append_text(
                        "chat", f"\n[错误] {data}\n")
        except queue.Empty:
            pass
        self.root.after(40, self._poll)


if __name__ == "__main__":
    win = DeepSeekChat()
    win.root.mainloop()

"""
DeepSeek 大模型对话模块（AWTF AI 子包，零第三方依赖）

- ``stream_chat``：SSE 流式对话，逐块 yield 增量文本
- ``chat``：非流式一问一答，返回完整回复
- ``deepseek_ask``：AWTF 注册工具（可 CLI 运行）

API：https://api.deepseek.com/chat/completions（OpenAI 兼容）
模型：deepseek-chat（默认）/ deepseek-reasoner
API Key 优先级：显式传参 > 环境变量 ``DEEPSEEK_API_KEY`` / ``AOVOW_AI_API_KEY``
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Dict, Iterator, List, Optional

from awtf import Parameter, ToolContext, tool

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"
MODELS = ("deepseek-chat", "deepseek-reasoner")


def resolve_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """按优先级解析 API Key：显式传参 > DEEPSEEK_API_KEY > AOVOW_AI_API_KEY。"""
    if api_key and api_key.strip():
        return api_key.strip()
    for env in ("DEEPSEEK_API_KEY", "AOVOW_AI_API_KEY"):
        value = os.environ.get(env)
        if value and value.strip():
            return value.strip()
    return None


def _post(api_key: str, body: Dict) -> "urllib.request.addinfourl":
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    return urllib.request.urlopen(req, timeout=180)


def stream_chat(api_key: Optional[str], messages: List[Dict],
                model: str = DEFAULT_MODEL) -> Iterator[str]:
    """SSE 流式对话，逐块 yield 文本内容。

    Args:
        api_key: DeepSeek API Key（None 时尝试环境变量）。
        messages: [{role: user/assistant, content: str}, ...]。
        model: deepseek-chat 或 deepseek-reasoner。

    Yields:
        str：增量文本块。
    """
    api_key = resolve_api_key(api_key)
    if not api_key:
        raise ValueError("缺少 DeepSeek API Key：请传参或设置 DEEPSEEK_API_KEY 环境变量")
    body = {"model": model, "messages": messages, "stream": True}
    with _post(api_key, body) as resp:
        for raw in resp:  # SSE 按行读取
            line = raw.decode("utf-8", "ignore").strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            try:
                delta = json.loads(payload)["choices"][0]["delta"].get("content", "")
            except (KeyError, IndexError, json.JSONDecodeError):
                continue
            if delta:
                yield delta


def chat(api_key: Optional[str], messages: List[Dict],
         model: str = DEFAULT_MODEL) -> str:
    """非流式一问一答，返回完整回复文本。"""
    api_key = resolve_api_key(api_key)
    if not api_key:
        raise ValueError("缺少 DeepSeek API Key：请传参或设置 DEEPSEEK_API_KEY 环境变量")
    body = {"model": model, "messages": messages, "stream": False}
    with _post(api_key, body) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


@tool(
    name="deepseek_ask",
    description="向 DeepSeek 提问，返回完整回答（AWTF 聊天工具）",
    tags=["ai", "chat", "deepseek"],
    parameters=[
        Parameter("message", str, default=None, description="发给 DeepSeek 的问题"),
        Parameter("api_key", str, default=None,
                  description="DeepSeek API Key（缺省读 DEEPSEEK_API_KEY 环境变量）"),
        Parameter("model", str, default=DEFAULT_MODEL,
                  description=f"模型：{' / '.join(MODELS)}"),
    ],
)
def deepseek_ask(ctx: ToolContext, message: Optional[str] = None,
                 api_key: Optional[str] = None, model: str = DEFAULT_MODEL) -> dict:
    """AWTF 工具：向 DeepSeek 提问，返回完整回答。"""
    if not (message or "").strip():
        raise ValueError("message 不能为空")
    if model not in MODELS:
        raise ValueError(f"不支持的模型：{model}（可选 {MODELS}）")
    ctx.info("deepseek_ask 开始: model=%s len=%d", model, len(message))
    reply = chat(api_key, [{"role": "user", "content": message.strip()}], model=model)
    ctx.info("deepseek_ask 完成: reply_len=%d", len(reply))
    return {"reply": reply, "model": model}

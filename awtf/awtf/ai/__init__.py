"""AWTF AI 子包：大模型对话能力（零第三方依赖）。"""

from .deepseek import (
    DEFAULT_MODEL,
    DEEPSEEK_URL,
    MODELS,
    chat,
    deepseek_ask,
    resolve_api_key,
    stream_chat,
)

__all__ = [
    "DEFAULT_MODEL",
    "DEEPSEEK_URL",
    "MODELS",
    "chat",
    "deepseek_ask",
    "resolve_api_key",
    "stream_chat",
]

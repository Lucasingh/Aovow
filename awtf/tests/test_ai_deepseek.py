"""awtf.ai.deepseek 单元测试（mock HTTP，不依赖真实网络）。"""

import json
import unittest
from unittest import mock

from awtf.ai.deepseek import (
    DEFAULT_MODEL,
    MODELS,
    chat,
    deepseek_ask,
    resolve_api_key,
    stream_chat,
)

SSE_TEXTS = [
    'data: {"choices":[{"delta":{"content":"你"}}]}\n\n',
    'data: {"choices":[{"delta":{"content":"好"}}]}\n\n',
    'data: [DONE]\n\n',
]


def _fake_response(stream: bool):
    r = mock.MagicMock()
    r.__enter__.return_value = r
    r.__iter__.return_value = iter(x.encode("utf-8") for x in SSE_TEXTS)
    r.read.return_value = json.dumps(
        {"choices": [{"message": {"content": "你好"}}]}).encode("utf-8")
    return r


class TestResolveKey(unittest.TestCase):
    def test_explicit_first(self):
        with mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": "env"},
                             clear=True):
            assert resolve_api_key("explicit") == "explicit"

    def test_env_fallback(self):
        with mock.patch.dict("os.environ", {"DEEPSEEK_API_KEY": "env"},
                             clear=True):
            assert resolve_api_key("  ") == "env"

    def test_aovow_env(self):
        with mock.patch.dict("os.environ", {"AOVOW_AI_API_KEY": "aovow"},
                             clear=True):
            assert resolve_api_key(None) == "aovow"

    def test_none(self):
        assert resolve_api_key(None) is None


class TestStreamChat(unittest.TestCase):
    def test_stream_parse(self):
        with mock.patch("awtf.ai.deepseek._post",
                        return_value=_fake_response(True)):
            got = "".join(stream_chat("sk", [{"role": "user", "content": "hi"}]))
        assert got == "你好"

    def test_missing_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                list(stream_chat(None, []))


class TestChat(unittest.TestCase):
    def test_chat(self):
        with mock.patch("awtf.ai.deepseek._post",
                        return_value=_fake_response(False)):
            reply = chat("sk", [{"role": "user", "content": "hi"}])
        assert reply == "你好"


class TestTool(unittest.TestCase):
    def test_ask(self):
        with mock.patch("awtf.ai.deepseek._post",
                        return_value=_fake_response(False)):
            with mock.patch("awtf.ai.deepseek.resolve_api_key",
                            return_value="sk"):
                result = deepseek_ask(mock.MagicMock(), message="hi")
        assert result["reply"] == "你好"
        assert result["model"] == DEFAULT_MODEL

    def test_ask_empty_message(self):
        with self.assertRaises(ValueError):
            deepseek_ask(mock.MagicMock(), message="   ")

    def test_ask_bad_model(self):
        with self.assertRaises(ValueError):
            deepseek_ask(mock.MagicMock(), message="hi", model="gpt-x")


if __name__ == "__main__":
    unittest.main()

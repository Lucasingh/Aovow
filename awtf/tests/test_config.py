"""配置管理测试：分层合并、环境变量、JSON/YAML 文件、ToolConfig 视图。"""

from __future__ import annotations

import json
import pathlib

import pytest

from awtf import ToolConfigError, deep_merge, load_config, save_config
from awtf.config import ToolConfig


class TestDeepMerge:
    def test_flat_override(self):
        assert deep_merge({"a": 1, "b": 2}, {"b": 3}) == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"db": {"host": "localhost", "port": 3306}, "x": 1}
        override = {"db": {"port": 3307, "user": "root"}}
        merged = deep_merge(base, override)
        assert merged == {"db": {"host": "localhost", "port": 3307, "user": "root"}, "x": 1}

    def test_does_not_mutate_inputs(self):
        base = {"a": {"b": 1}}
        deep_merge(base, {"a": {"c": 2}})
        assert base == {"a": {"b": 1}}


class TestLoadConfig:
    def test_defaults_only(self):
        cfg = load_config(defaults={"app": {"name": "x"}})
        assert cfg["app"]["name"] == "x"

    def test_json_file(self, tmp_path: pathlib.Path):
        f = tmp_path / "cfg.json"
        f.write_text(json.dumps({"app": {"name": "from-file"}, "level": 2}), encoding="utf-8")
        cfg = load_config(f, defaults={"app": {"name": "default", "v": 1}})
        assert cfg["app"]["name"] == "from-file"
        assert cfg["app"]["v"] == 1  # 默认保留
        assert cfg["level"] == 2

    def test_missing_file_raises(self, tmp_path: pathlib.Path):
        with pytest.raises(ToolConfigError, match="不存在"):
            load_config(tmp_path / "nope.json")

    def test_bad_format_raises(self, tmp_path: pathlib.Path):
        f = tmp_path / "cfg.txt"
        f.write_text("xxx", encoding="utf-8")
        with pytest.raises(ToolConfigError, match="不支持"):
            load_config(f)

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AWTF__APP__NAME", "from-env")
        monkeypatch.setenv("AWTF__COUNT", "42")
        cfg = load_config(defaults={"app": {"name": "default"}})
        assert cfg["app"]["name"] == "from-env"
        assert cfg["count"] == 42  # 数字字符串自动解析

    def test_env_json_value(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("AWTF__LIST", "[1, 2, 3]")
        cfg = load_config()
        assert cfg["list"] == [1, 2, 3]


class TestToolConfigView:
    def test_section_get(self):
        cfg = ToolConfig({"my_tool": {"timeout": 30, "name": "x"}}, section="my_tool")
        assert cfg.get_int("timeout") == 30
        assert cfg.get_str("name") == "x"

    def test_required_missing(self):
        cfg = ToolConfig({}, section="my_tool")
        with pytest.raises(ToolConfigError, match="缺少必需配置"):
            cfg.get("api_key", required=True)

    def test_typed_getters(self):
        cfg = ToolConfig({"t": {"i": "5", "f": "1.5", "b": "yes", "s": 123}}, section="t")
        assert cfg.get_int("i") == 5
        assert cfg.get_float("f") == pytest.approx(1.5)
        assert cfg.get_bool("b") is True
        assert cfg.get_str("s") == "123"

    def test_bad_int_raises(self):
        cfg = ToolConfig({"t": {"i": "abc"}}, section="t")
        with pytest.raises(ToolConfigError, match="不是整数"):
            cfg.get_int("i")


class TestSave:
    def test_save_and_reload_json(self, tmp_path: pathlib.Path):
        f = tmp_path / "out.json"
        save_config(f, {"a": 1, "b": {"c": "中文"}})
        cfg = load_config(f)
        assert cfg["b"]["c"] == "中文"

    def test_yaml_without_pyyaml_falls_back(self, tmp_path: pathlib.Path, monkeypatch):
        # 保存为 .yaml 但模拟无 pyyaml 时降级为 .json
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("no yaml")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        f = tmp_path / "out.yaml"
        save_config(f, {"a": 1})
        # 降级后实际写了 out.json
        assert (tmp_path / "out.json").exists()

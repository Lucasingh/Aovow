"""CLI 测试：list/info/run/new/docs/doctor 子命令。"""

from __future__ import annotations

import json
import pathlib

import pytest

from awtf.cli import main

EXAMPLES = str(pathlib.Path(__file__).resolve().parent.parent / "examples")
TEXT_TOOLS = str(pathlib.Path(__file__).resolve().parent.parent / "examples" / "text_tools.py")


class TestList:
    def test_list_discovered(self, capsys):
        code = main(["list", "--discover", TEXT_TOOLS])
        out = capsys.readouterr().out
        assert code == 0
        assert "word_count" in out
        assert "text_case" in out

    def test_list_json(self, capsys):
        code = main(["list", "--discover", TEXT_TOOLS, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert any(t["name"] == "word_count" for t in data)

    def test_list_empty(self, capsys):
        code = main(["list"])
        out = capsys.readouterr().out
        assert "未发现" in out


class TestInfo:
    def test_info_text(self, capsys):
        code = main(["info", "word_count", "--discover", TEXT_TOOLS])
        out = capsys.readouterr().out
        assert code == 0
        assert "--text" in out
        assert "必填" in out

    def test_info_missing(self, capsys):
        code = main(["info", "nope", "--discover", TEXT_TOOLS])
        assert code == 2
        assert "未注册" in capsys.readouterr().err


class TestRun:
    def test_run_success_json(self, capsys):
        code = main(["run", "word_count", "--discover", TEXT_TOOLS,
                     "--text", "a b c", "--json"])
        out = capsys.readouterr().out
        assert code == 0
        data = json.loads(out)
        assert data["ok"] is True
        assert data["data"]["words"] == 3

    def test_run_discover_after_tool_name(self, capsys):
        # --discover 写在工具名之后（常见用法）
        code = main(["run", "word_count", "--text", "x y", "--discover", TEXT_TOOLS])
        out = capsys.readouterr().out
        assert code == 0
        assert json.loads(out)["data"]["words"] == 2

    def test_run_validation_failure_exit1(self, capsys):
        code = main(["run", "word_count", "--discover", TEXT_TOOLS])
        assert code == 1
        out = capsys.readouterr().out
        assert "VALIDATION_ERROR" in out

    def test_run_dry_run_flag(self, capsys, tmp_path):
        # 用脚手架生成一个支持 dry-run 的工具再运行
        code = main(["new", "cli_demo", "--dir", str(tmp_path), "--no-readme",
                     "--description", "CLI 测试"])
        assert code == 0
        capsys.readouterr()  # 清掉 new 命令的输出
        code = main(["run", "cli_demo", "--text", "hi", "--dry-run",
                     "--discover", str(tmp_path)])
        assert code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["data"]["would_do"].startswith("把")

    def test_run_numeric_param_parsing(self, capsys):
        code = main(["run", "text_case", "--text", "hello", "--mode", "upper",
                     "--discover", TEXT_TOOLS, "--json"])
        data = json.loads(capsys.readouterr().out)
        assert data["data"]["converted"] == "HELLO"


class TestNew:
    def test_new_creates_files(self, tmp_path):
        code = main(["new", "my_tool", "--dir", str(tmp_path),
                     "--description", "测试工具"])
        assert code == 0
        tool_file = tmp_path / "tools_my_tool.py"
        assert tool_file.exists()
        assert (tmp_path / "README.md").exists()
        content = tool_file.read_text(encoding="utf-8")
        assert "name=\"my_tool\"" in content

    def test_new_refuses_overwrite(self, tmp_path):
        main(["new", "dup", "--dir", str(tmp_path), "--no-readme"])
        code = main(["new", "dup", "--dir", str(tmp_path), "--no-readme"])
        assert code == 2

    def test_generated_tool_imports_and_runs(self, tmp_path):
        main(["new", "gen_tool", "--dir", str(tmp_path), "--no-readme"])
        from awtf import ToolRegistry
        reg = ToolRegistry()
        reg.discover_path(tmp_path)
        result = reg.run("gen_tool", {"text": "生成", "repeat": 2})
        assert result.ok
        assert result.data["repeat"] == 2


class TestDocsAndDoctor:
    def test_docs_markdown(self, capsys):
        code = main(["docs", "word_count", "--discover", TEXT_TOOLS])
        out = capsys.readouterr().out
        assert code == 0
        assert "## word_count" in out
        assert "| text |" in out

    def test_doctor(self, capsys):
        code = main(["doctor"])
        out = capsys.readouterr().out
        assert code == 0
        assert "Python" in out

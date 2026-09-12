"""
命令行界面 —— ``python -m awtf <command>``。

子命令：
    list     列出已注册工具（--discover 路径可先发现工具）
    info     查看工具详情（参数 schema / 元数据 / 文档）
    run      运行工具，参数用 --key value 传入，结果默认 JSON 输出
    new      脚手架：生成新工具文件
    doctor   环境自检（Python 版本 / 可选依赖 / 发现路径）
    docs     输出工具的 Markdown 文档

设计：CLI 是 awtf 的"薄壳"，所有逻辑走 Registry 真实链路，
不绕过校验/异常处理（与经验教训一致）。
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .errors import ToolError
from .logging_utils import setup_logging
from .registry import ToolRegistry


# ============================================================
# 工具发现辅助
# ============================================================

def _build_registry(discover: Optional[str], entry_points: bool) -> ToolRegistry:
    registry = ToolRegistry(name="cli")
    if discover:
        import pathlib
        p = pathlib.Path(discover)
        if p.exists() and (p.is_dir() or p.suffix == ".py"):
            registry.discover_path(p)
        else:
            registry.discover_module(discover)
    if entry_points:
        try:
            registry.discover_entry_points()
        except ToolError as e:
            print(f"⚠ entry points 发现失败: {e.message}", file=sys.stderr)
    return registry


_KNOWN_FLAGS = {"--dry-run", "--verbose", "-v", "--json", "--entry-points"}
_BOOL_FLAGS = {"--dry-run": "dry_run", "--verbose": "verbose", "-v": "verbose",
               "--json": "json", "--entry-points": "entry_points"}


def _extract_discover_flags(tokens: List[str]):
    """从 REMAINDER token 中捞出 CLI 自身的开关/选项。

    返回 (discover, entry_points, bool_flags集合, 剩余工具参数)。
    """
    discover: Optional[str] = None
    entry_points = False
    bool_flags: set = set()
    leftover: List[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--discover":
            i += 1
            if i < len(tokens):
                discover = tokens[i]
        elif tok.startswith("--discover="):
            discover = tok.split("=", 1)[1]
        elif tok in _BOOL_FLAGS:
            bool_flags.add(_BOOL_FLAGS[tok])
            if tok == "--entry-points":
                entry_points = True
        else:
            leftover.append(tok)
        i += 1
    return discover, entry_points, bool_flags, leftover


def _parse_run_params(pairs: List[str]) -> Dict[str, Any]:
    """把 ``--key value`` 形式的参数解析为字典，值按 JSON 尝试解析。

    REMAINDER 会把工具名之后的所有 token 都收进来，
    因此先剔除 CLI 自身的开关（--dry-run 等）。
    """
    pairs = [t for t in pairs if t not in _KNOWN_FLAGS]
    params: Dict[str, Any] = {}
    i = 0
    while i < len(pairs):
        item = pairs[i]
        if not item.startswith("--"):
            raise SystemExit(f"无法识别的参数: {item}（参数需用 --key value 形式）")
        key = item[2:]
        if "=" in key:
            key, raw = key.split("=", 1)
        else:
            i += 1
            if i >= len(pairs):
                raise SystemExit(f"参数 --{key} 缺少值")
            raw = pairs[i]
        try:
            params[key] = json.loads(raw)
        except json.JSONDecodeError:
            params[key] = raw  # 普通字符串
        i += 1
    return params


# ============================================================
# 子命令实现
# ============================================================

def cmd_list(args: argparse.Namespace) -> int:
    registry = _build_registry(args.discover, args.entry_points)
    tools = registry.list_tools(tag=args.tag, category=args.category)
    if not tools:
        print("（未发现任何工具。用 --discover <目录/文件> 加载，或 awtf new 创建）")
        return 0
    if args.json:
        print(json.dumps(tools, ensure_ascii=False, indent=2))
        return 0

    # 表格输出
    name_w = max(len(t["name"]) for t in tools)
    for t in tools:
        tags = f" [{', '.join(t['tags'])}]" if t["tags"] else ""
        print(f"  {t['name']:<{name_w}}  v{t['version']:<8} {t['description']}{tags}")
    print(f"\n共 {len(tools)} 个工具")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    registry = _build_registry(args.discover, args.entry_points)
    try:
        desc = registry.describe(args.name)
    except ToolError as e:
        print(f"错误: {e.message}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(desc, ensure_ascii=False, indent=2))
        return 0

    print(f"工具: {desc['name']}  (v{desc['version']}, {desc['kind']}"
          f"{', async' if desc['async'] else ''})")
    if desc.get("author"):
        print(f"作者: {desc['author']}")
    if desc.get("category") and desc["category"] != "general":
        print(f"分类: {desc['category']}")
    if desc.get("tags"):
        print(f"标签: {', '.join(desc['tags'])}")
    print(f"说明: {desc['description']}")
    print("\n参数:")
    if not desc["parameters"]:
        print("  （无参数）")
    for p in desc["parameters"]:
        req = "必填" if p["required"] else f"可选(默认 {p['default']!r})"
        line = f"  --{p['name']} <{p['type']}>  {req}"
        if p["choices"]:
            line += f"  取值: {p['choices']}"
        if p["min"] is not None or p["max"] is not None:
            line += f"  范围: {p['min']}~{p['max']}"
        print(line)
        if p["description"]:
            print(f"      {p['description']}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    # REMAINDER 会吞掉工具名之后的 CLI 开关（--discover/--dry-run 等），这里捞回来
    discover, entry_points, bool_flags, leftover = _extract_discover_flags(args.params)
    discover = discover or args.discover
    entry_points = entry_points or args.entry_points
    # 被吞掉的 bool 开关合并回 argparse 命名空间
    for flag in bool_flags:
        setattr(args, flag, True)

    setup_logging("DEBUG" if args.verbose else "WARNING")
    registry = _build_registry(discover, entry_points)
    params = _parse_run_params(leftover)
    metadata = {"source": "cli"}
    if args.dry_run:
        metadata["dry_run"] = True

    result = registry.run(
        args.name,
        params,
        config=None,
        metadata=metadata,
        capture_logs=args.verbose,
    )

    if args.json or not sys.stdout.isatty():
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        # 人类可读输出
        if result.ok:
            print("✅ 成功" + (f"  ({result.duration_ms:.0f}ms)" if result.duration_ms else ""))
            print(json.dumps(result.data, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"❌ 失败 [{result.error.get('code')}]: {result.error.get('message')}")
            for field, msg in (result.error.get("details", {}).get("field_errors") or {}).items():
                print(f"   - {field}: {msg}")
            if args.verbose and result.error.get("details", {}).get("traceback"):
                print("\n--- traceback ---")
                print(result.error["details"]["traceback"])

    if result.logs and args.verbose:
        print("\n--- 日志 ---", file=sys.stderr)
        for line in result.logs:
            print(line, file=sys.stderr)

    return 0 if result.ok else 1


def cmd_new(args: argparse.Namespace) -> int:
    from .templates import scaffold
    try:
        tool_path, readme_path = scaffold(
            args.name, args.dir or ".",
            with_readme=not args.no_readme,
            description=args.description or "在这里描述工具用途",
        )
    except FileExistsError as e:
        print(f"错误: {e}", file=sys.stderr)
        return 2
    print(f"✅ 已生成工具文件: {tool_path}")
    if readme_path:
        print(f"   说明文档: {readme_path}")
    print("\n下一步:")
    print(f"  1. 编辑 {tool_path.name} 实现你的逻辑")
    print(f"  2. 试运行: python -m awtf run {args.name} --text 你好 --discover .")
    return 0


def cmd_docs(args: argparse.Namespace) -> int:
    registry = _build_registry(args.discover, args.entry_points)
    tools = [args.name] if args.name else registry.names()
    docs = [_render_markdown(registry, n) for n in tools]
    print("\n\n".join(docs))
    return 0


def _render_markdown(registry: ToolRegistry, name: str) -> str:
    try:
        d = registry.describe(name)
    except ToolError as e:
        return f"<!-- {e.message} -->"
    lines = [f"## {d['name']}", "", d["description"], "",
             f"- 版本: {d['version']} | 类型: {d['kind']} | 异步: {'是' if d['async'] else '否'}"]
    if d["tags"]:
        lines.append(f"- 标签: {', '.join(d['tags'])}")
    lines += ["", "| 参数 | 类型 | 必填 | 默认值 | 说明 |", "|------|------|------|--------|------|"]
    for p in d["parameters"]:
        lines.append(
            f"| {p['name']} | {p['type']} | {'是' if p['required'] else '否'} "
            f"| {'' if p['required'] else p['default']} | {p['description']} |")
    return "\n".join(lines)


def cmd_doctor(_args: argparse.Namespace) -> int:
    print(f"AWTF v{__version__}")
    print(f"Python: {sys.version.split()[0]}  ({sys.executable})")
    for opt in ("yaml", "pytest"):
        try:
            __import__(opt)
            print(f"  [✓] {opt}")
        except ImportError:
            print(f"  [ ] {opt}（可选，未安装）")
    print("环境自检完成。")
    return 0


# ============================================================
# 入口
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="awtf",
        description="AWTF —— 用 Python 代码设计、搭建自己的工具与程序的框架",
    )
    parser.add_argument("--version", action="version", version=f"awtf {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_discover(p: argparse.ArgumentParser) -> None:
        p.add_argument("--discover", help="先从目录/.py文件/模块名发现工具")
        p.add_argument("--entry-points", action="store_true", help="同时发现 entry points 工具")

    p_list = sub.add_parser("list", help="列出工具")
    add_discover(p_list)
    p_list.add_argument("--tag", help="按标签过滤")
    p_list.add_argument("--category", help="按分类过滤")
    p_list.add_argument("--json", action="store_true", help="JSON 输出")
    p_list.set_defaults(func=cmd_list)

    p_info = sub.add_parser("info", help="查看工具详情")
    add_discover(p_info)
    p_info.add_argument("name", help="工具名")
    p_info.add_argument("--json", action="store_true")
    p_info.set_defaults(func=cmd_info)

    p_run = sub.add_parser("run", help="运行工具")
    add_discover(p_run)
    p_run.add_argument("name", help="工具名")
    p_run.add_argument("params", nargs=argparse.REMAINDER, help="参数：--key value")
    p_run.add_argument("--dry-run", action="store_true", help="演练模式")
    p_run.add_argument("--verbose", "-v", action="store_true", help="显示日志与 traceback")
    p_run.add_argument("--json", action="store_true", help="强制 JSON 输出")
    p_run.set_defaults(func=cmd_run)

    p_new = sub.add_parser("new", help="生成新工具脚手架")
    p_new.add_argument("name", help="工具名")
    p_new.add_argument("--dir", help="输出目录（默认当前目录）")
    p_new.add_argument("--description", help="工具用途描述")
    p_new.add_argument("--no-readme", action="store_true", help="不生成 README")
    p_new.set_defaults(func=cmd_new)

    p_docs = sub.add_parser("docs", help="输出 Markdown 文档")
    add_discover(p_docs)
    p_docs.add_argument("name", nargs="?", help="工具名（省略则全部）")
    p_docs.set_defaults(func=cmd_docs)

    p_doctor = sub.add_parser("doctor", help="环境自检")
    p_doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ToolError as e:
        print(f"错误 [{e.code}]: {e.message}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

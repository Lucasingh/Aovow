"""
示例：用 Python API 运行工具（发现 -> 注册 -> 执行 -> 结果处理）。

运行：
    cd awtf
    python examples/run_demo.py
"""

from __future__ import annotations

import json
import pathlib
import sys

# 确保能导入未安装的 awtf
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from awtf import ToolRegistry, setup_logging  # noqa: E402


def main() -> None:
    setup_logging("INFO")
    examples_dir = pathlib.Path(__file__).resolve().parent

    registry = ToolRegistry(name="demo")
    # 发现 examples 目录下所有工具
    discovered = registry.discover_path(examples_dir)
    print(f"已发现 {len(discovered)} 个工具: {discovered}\n")

    # 1. 正常调用
    print("=== word_count ===")
    result = registry.run("word_count", {"text": "hello awtf world hello"})
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))

    # 2. 参数校验失败（聚合错误）
    print("\n=== 校验失败演示 ===")
    result = registry.run("text_case", {"text": "Hello", "mode": "WRONG"})
    print("ok:", result.ok, "| error:", result.error["message"])

    # 3. dry-run
    print("\n=== organize_dir（dry-run）===")
    result = registry.run(
        "organize_dir",
        {"dir": str(examples_dir)},
        metadata={"dry_run": True},
        capture_logs=True,
    )
    print("ok:", result.ok)
    print("分类:", result.data["categories"])
    print("日志:", result.logs)

    # 4. 异步工具
    print("\n=== sleep_sort（异步）===")
    result = registry.run("sleep_sort", {"numbers": [3, 1, 2]})
    print("ok:", result.ok, "| data:", result.data)

    # 5. raise_for_status 用法
    print("\n=== 错误即异常（raise_for_status）===")
    result = registry.run("not_exist", {})
    try:
        result.raise_for_status()
    except Exception as e:
        print("捕获:", e)


if __name__ == "__main__":
    main()

"""
示例：类工具 + 配置读取 + dry-run（文件整理工具）。

演示 ToolBase 子类形态、ctx.section_config 读取配置、
dry-run 演练模式、path 类型参数。

运行：
    python -m awtf info organize_dir --discover examples/file_tools.py
    python -m awtf run organize_dir --dir . --dry-run --discover examples/file_tools.py
"""

from __future__ import annotations

import pathlib
from collections import Counter

from awtf import Parameter, ParameterSet, ToolBase, ToolContext, ToolConfigError


class OrganizeDirTool(ToolBase):
    """按扩展名把目录中的文件归类到子文件夹。"""

    name = "organize_dir"
    description = "按文件扩展名归类整理目录"
    version = "1.0.0"
    tags = ["files", "automation"]
    category = "file"

    parameters = ParameterSet([
        Parameter("dir", "path", description="目标目录", min_length=1),
        Parameter("dry_run_default", bool, default=False,
                  description="占位（实际 dry-run 由 ctx.dry_run 控制）"),
        Parameter("recursive", bool, default=False, description="是否递归子目录"),
    ])

    # 扩展名 -> 子文件夹名
    EXT_MAP = {
        ".jpg": "images", ".jpeg": "images", ".png": "images", ".gif": "images",
        ".pdf": "documents", ".doc": "documents", ".docx": "documents",
        ".txt": "documents", ".md": "documents",
        ".mp3": "audio", ".wav": "audio",
        ".mp4": "video", ".mov": "video",
        ".zip": "archives", ".tar": "archives", ".gz": "archives",
        ".py": "code", ".js": "code", ".json": "code",
    }

    def run(self, ctx: ToolContext, dir: pathlib.Path,
            dry_run_default: bool = False, recursive: bool = False) -> dict:
        target = pathlib.Path(dir)
        if not target.exists() or not target.is_dir():
            raise ToolConfigError(f"目录不存在或不是目录: {target}",
                                  details={"dir": str(target)})

        glob = target.rglob("*") if recursive else target.iterdir()
        files = [f for f in glob if f.is_file()]

        plan: dict[str, list[str]] = {}
        unknown: list[str] = []
        for f in files:
            folder = self.EXT_MAP.get(f.suffix.lower(), "others")
            plan.setdefault(folder, []).append(f.name)
            if folder == "others" and f.suffix:
                unknown.append(f.suffix)

        moved = 0
        actions = []
        if not ctx.dry_run:
            for folder, names in plan.items():
                dest_dir = target / folder
                dest_dir.mkdir(exist_ok=True)
                for name in names:
                    src = target / name
                    if src.exists() and src.parent == target:
                        src.rename(dest_dir / name)
                        actions.append(f"{name} -> {folder}/")
                        moved += 1

        ctx.info("organize_dir: %d 个文件，%d 个分类（dry_run=%s）",
                 len(files), len(plan), ctx.dry_run)
        return {
            "dir": str(target),
            "total_files": len(files),
            "categories": {k: len(v) for k, v in sorted(plan.items())},
            "moved": moved if not ctx.dry_run else 0,
            "dry_run": ctx.dry_run,
            "actions_preview": actions[:20] if actions else
                               [f"{n} -> {k}/" for k, v in plan.items() for n in v[:3]],
            "unknown_extensions": dict(Counter(unknown)),
        }

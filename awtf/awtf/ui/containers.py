"""
容器组件：卡片、列表、表格、分隔线。

- 卡片：标题 + 内容区（含边框/内边距），可放任意子组件。
- 列表：纯文本/可选项列表，支持单选回调。
- 表格：多列表格，支持表头、行选择、整行取值。
数据层实现排序/选择逻辑，渲染后端只负责绘制。
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, List, Optional, Sequence

from .widgets import Component


@dataclasses.dataclass
class CardSpec:
    """卡片容器。"""

    title: str = ""
    children: List[Component] = dataclasses.field(default_factory=list)
    padding: int = 12
    border: bool = True
    elevated: bool = True


@dataclasses.dataclass
class ListSpec:
    """列表。

    Attributes:
        items: 选项文本列表。
        multi_select: 是否多选。
        height: 可见行数（后端渲染滚动区）。
        on_select: 选择回调名；payload 为选中索引列表。
        selected: 初始选中索引列表。
    """

    items: List[str] = dataclasses.field(default_factory=list)
    multi_select: bool = False
    height: int = 8
    on_select: Optional[str] = None
    selected: List[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class TableSpec:
    """表格。

    Attributes:
        columns: 列名列表。
        rows: 数据行（每行长度与列数一致）。
        height: 可见行数。
        selectable: 是否可选行。
        on_select: 选择回调名；payload 为选中行（dict: {列名: 值}）。
    """

    columns: List[str] = dataclasses.field(default_factory=list)
    rows: List[List[Any]] = dataclasses.field(default_factory=list)
    height: int = 10
    selectable: bool = False
    on_select: Optional[str] = None

    def __post_init__(self) -> None:
        for row in self.rows:
            if len(row) != len(self.columns):
                raise ValueError(
                    f"行数据长度 {len(row)} 与列数 {len(self.columns)} 不一致: {row}")

    def row_dict(self, index: int) -> Dict[str, Any]:
        """取第 index 行为 {列名: 值}。"""
        row = self.rows[index]
        return {self.columns[i]: row[i] for i in range(len(self.columns))}

    def sort_rows(self, column_index: int, reverse: bool = False) -> None:
        """按列原地排序（数值优先，其次字符串）。"""
        self.rows.sort(
            key=lambda r: _sort_key(r[column_index]),
            reverse=reverse,
        )


def _sort_key(value: Any):
    """排序键：数字在前，字符串次之，None 最后。"""
    if value is None:
        return (2, 0)
    if isinstance(value, (int, float)):
        return (0, value)
    return (1, str(value))

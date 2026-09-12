"""
示例：文本处理工具集（函数工具 + 显式 Parameter）。

运行：
    python -m awtf list --discover examples/text_tools.py
    python -m awtf run word_count --text "hello world hello" --discover examples/text_tools.py
"""

from __future__ import annotations

from awtf import Parameter, ToolContext, tool


@tool(
    name="word_count",
    description="统计文本的词数与字符数",
    tags=["text", "stats"],
    parameters=[
        Parameter("text", str, description="待统计文本", min_length=1),
        Parameter("language", str, default="en", choices=["en", "zh"],
                  description="语言：en 按空格分词，zh 按字符计"),
    ],
)
def word_count(ctx: ToolContext, text: str, language: str = "en") -> dict:
    """统计文本词数/字符数。

    Args:
        text: 待统计文本
        language: en 按空格分词；zh 按中文字符计
    """
    ctx.info("word_count: %d chars, language=%s", len(text), language)
    if language == "zh":
        # 中文字符数
        words = [c for c in text if "\u4e00" <= c <= "\u9fff"]
        count = len(words)
    else:
        count = len(text.split())
    return {"words": count, "chars": len(text), "language": language}


@tool(
    name="text_case",
    description="文本大小写转换",
    tags=["text"],
    parameters=[
        Parameter("text", str, description="输入文本"),
        Parameter("mode", str, default="upper",
                  choices=["upper", "lower", "title", "swap"],
                  description="转换模式"),
    ],
)
def text_case(ctx: ToolContext, text: str, mode: str = "upper") -> dict:
    ctx.debug("text_case mode=%s", mode)
    if mode == "upper":
        out = text.upper()
    elif mode == "lower":
        out = text.lower()
    elif mode == "title":
        out = text.title()
    else:
        out = text.swapcase()
    return {"original": text, "converted": out, "mode": mode}


@tool(
    name="find_all",
    description="查找关键词在文本中的所有出现位置",
    tags=["text", "search"],
)
def find_all(ctx: ToolContext, text: str, keyword: str) -> dict:
    """查找关键词位置。

    Args:
        text: 被搜索的文本
        keyword: 关键词
    """
    if not keyword:
        raise ValueError("keyword 不能为空字符串")
    positions = []
    start = 0
    while True:
        idx = text.find(keyword, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    ctx.info("find_all: %s 命中 %d 次", keyword, len(positions))
    return {"keyword": keyword, "count": len(positions), "positions": positions}

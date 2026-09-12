"""
示例：异步工具（async def）。

异步工具与同步工具用法完全一致——注册表自动检测协程函数，
执行时调度事件循环。适合并发 HTTP 请求、异步 IO 等场景。

运行：
    python -m awtf run fetch_demo --urls "https://example.com" \
        --discover examples/async_tools.py
"""

from __future__ import annotations

import asyncio

from awtf import Parameter, ToolContext, tool


@tool(
    name="sleep_sort",
    description="异步演示：按数值睡眠后排序返回（验证并发调度）",
    tags=["async", "demo"],
    parameters=[
        Parameter("numbers", list, description="数字列表，如 [3,1,2]"),
    ],
)
async def sleep_sort(ctx: ToolContext, numbers: list) -> dict:
    """每个数字 sleep 对应秒数（缩小 100 倍），按完成顺序返回。"""
    ctx.info("sleep_sort: %s", numbers)

    async def delayed(n: float) -> float:
        await asyncio.sleep(n / 100.0)
        return n

    results = await asyncio.gather(*(delayed(float(n)) for n in numbers))
    return {"input": numbers, "sorted": sorted(results), "completed_order": list(results)}


@tool(
    name="fetch_demo",
    description="异步并发抓取 URL 的状态码（纯标准库，无第三方依赖）",
    tags=["async", "network"],
)
async def fetch_demo(ctx: ToolContext, urls: list, timeout: float = 10.0) -> dict:
    """并发请求多个 URL，返回状态码与耗时。

    Args:
        urls: URL 列表
        timeout: 单请求超时秒数
    """
    import urllib.request

    async def check(url: str) -> dict:
        loop = asyncio.get_event_loop()

        def _get() -> dict:
            try:
                with urllib.request.urlopen(url, timeout=timeout) as resp:
                    return {"url": url, "status": resp.status, "ok": True}
            except Exception as e:  # noqa: BLE001 - 网络错误需要逐个返回
                return {"url": url, "status": None, "ok": False, "error": str(e)[:120]}

        ctx.info("fetching %s", url)
        return await loop.run_in_executor(None, _get)

    results = await asyncio.gather(*(check(u) for u in urls))
    ok_count = sum(1 for r in results if r.get("ok"))
    return {"total": len(results), "ok": ok_count, "failed": len(results) - ok_count,
            "results": results}

"""Makes the MCP traffic visible: which server, which tool with which arguments, what came back (shown by ui.py).

Set MCP_RAW=1 to show the full response text instead of a short summary.
"""
import json
import os
import time
from urllib.parse import urlparse

from common import mcp_servers
from ui import ui


def _short(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + f"... (+{len(text) - limit} chars)"


def describe(text: str, limit: int = 3) -> tuple[str, list[str]]:
    """Short summary of a tool response: a headline and up to `limit` rows (title, price, stock/place)."""
    if os.environ.get("MCP_RAW"):
        return text, []
    try:
        data = json.loads(text)
    except ValueError:
        return _describe_text(text, limit)
    lists = [(k, v) for k, v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict)] \
        if isinstance(data, dict) else []
    if not lists:
        return _short(text, 100), []
    key, items = lists[0]
    total = data.get("total_count")
    headline = f"{len(items)} {key}" + (f" (of {total})" if total and total != len(items) else "")
    rows = []
    for item in items[:limit]:
        price = f"{item['price']} EUR" if item.get("price") is not None else "-"
        rows.append(f"{price:>8}  {item.get('title') or item.get('name')}  ({item.get('locality', '')})")
    return headline, rows


def _describe_text(text: str, limit: int) -> tuple[str, list[str]]:
    """Alza answers with markdown lines like '- **Title** . code: `x` . 519 EUR . in stock . ...'."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    headline = lines[0].replace("**", "") if lines else "empty"
    rows = []
    for ln in lines:
        if ln.startswith("- **"):
            parts = [p.strip().replace("**", "") for p in ln[2:].split(" \u00b7 ")]
            price = next((p for p in parts if "EUR" in p), "-")
            stock = next((p for p in parts if "stock" in p or "sklad" in p.lower()), "")
            rows.append(f"{price:>10}  {parts[0]}  {stock}")
    return _short(headline, 80), rows[:limit]


def register(src: str, tool_names: list[str]) -> None:
    """Called once a server is connected (initialize + tools/list): remember its tools for the UI."""
    ui.tools[src] = tool_names


def begin_scouts(sources: list[str]) -> None:
    ui.begin_scouts({src: str(urlparse(mcp_servers()[src]["url"]).port) for src in sources})


def show_servers() -> None:
    ui.servers({src: str(urlparse(cfg["url"]).port) for src, cfg in mcp_servers().items()})


def log_call(source: str, tool: str, args: dict) -> None:
    ui.call(source, tool, args)


def log_result(source: str, text: str, seconds: float) -> None:
    ui.result(source, *describe(text), seconds)


def text_of(result) -> str:
    """Text of a tool result: CallToolResult (content blocks) or ToolMessage / plain string."""
    content = getattr(result, "content", result)
    if isinstance(content, list):
        return "\n".join(getattr(c, "text", None) or c.get("text", "") if not isinstance(c, str) else c for c in content)
    return str(content)


async def langgraph_interceptor(request, handler):
    """langchain-mcp-adapters tool_interceptor: wraps every MCP tool call of the graph."""
    log_call(request.server_name, request.name, request.args)
    started = time.perf_counter()
    result = await handler(request)
    log_result(request.server_name, text_of(result), time.perf_counter() - started)
    return result


def wrap_crewai_tools(source: str, tools: list) -> list:
    """Same for CrewAI: wrap the _run method of every MCP tool of one server."""
    for tool in tools:
        def traced(*args, _run=tool._run, _name=tool.name, **kwargs):
            log_call(source, _name, kwargs)
            started = time.perf_counter()
            result = _run(*args, **kwargs)
            log_result(source, text_of(result), time.perf_counter() - started)
            return result
        object.__setattr__(tool, "_run", traced)
    return tools

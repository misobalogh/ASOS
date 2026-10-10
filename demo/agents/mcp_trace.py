"""Makes the MCP traffic visible: which server (address:port), which tool with which arguments, what came back.

Set MCP_RAW=1 to print the full response text instead of a short summary, MCP_SHOW_HOST=1 to show the real host.
"""
import json
import os
import time
from urllib.parse import urlparse

from common import log, mcp_servers

ARROW_OUT, ARROW_IN = "-->", "<--"


def _short(text: str, limit: int = 200) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + f"... (+{len(text) - limit} chars)"


def _target(source: str) -> str:
    """host:port of the server; the host is masked (the demo runs on a projector), MCP_SHOW_HOST=1 shows it."""
    url = urlparse(mcp_servers()[source]["url"])
    return url.netloc if os.environ.get("MCP_SHOW_HOST") else f"x.x.x.x:{url.port}"


def describe(text: str, rows: int = 3) -> str:
    """One-line summary of a tool response: item count and the first few items (title/name, price, stock)."""
    if os.environ.get("MCP_RAW"):
        return text
    try:
        data = json.loads(text)
    except ValueError:
        return _short(text)
    lists = [(k, v) for k, v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict)] \
        if isinstance(data, dict) else []
    if not lists:
        return f"{len(text)} chars: " + _short(text)
    key, items = lists[0]
    total = data.get("total_count")
    head = f"{len(items)} {key}" + (f" (total {total})" if total and total != len(items) else "")
    lines = []
    for item in items[:rows]:
        parts = [str(item[f]) for f in ("title", "name", "price", "availability", "locality") if item.get(f) is not None]
        lines.append(" | ".join(parts))
    return head + ": " + " ;; ".join(lines) + (" ;; ..." if len(items) > rows else "")


def banner(source: str, tool_names: list[str]) -> None:
    """Printed once per server: where it lives and what it offers (the result of initialize + tools/list)."""
    log("mcp", f"{source:5} http://{_target(source)}/mcp  {len(tool_names)} tools: {', '.join(tool_names)}")


def log_call(source: str, tool: str, args: dict) -> None:
    log(f"{source}_scout", f"{ARROW_OUT} http://{_target(source)}/mcp  tools/call {tool} "
        + _short(json.dumps({k: v for k, v in args.items() if v is not None}, ensure_ascii=False), 160))


def log_result(source: str, text: str, seconds: float) -> None:
    log(f"{source}_scout", f"{ARROW_IN} {seconds:.1f} s  {describe(text)}")


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

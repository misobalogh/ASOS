#!/usr/bin/env python3
"""Pre-demo check of the Bazos and Alza MCP servers. Run it 10 minutes before the talk.

Reads the server URLs and tokens from the Claude Code user config (~/.claude.json), so no secret is stored here.
It also warms up the Alza server (the first search after a restart can come back empty).
"""
import json
import os
import re
import sys
import time
import urllib.request

SERVERS = {"bazos-chronos": ("search_listings", {"query": "RTX 4070", "section": "PC", "price_max": 600, "limit": 3}),
           "alza": ("search_products", {"query": "RTX 4070", "limit": 3})}


def post(url, token, body, sid=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
    if sid:
        headers["Mcp-Session-Id"] = sid
    with urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), headers), timeout=120) as r:
        text = r.read().decode()
        match = re.search(r"data: (.*)", text)
        return r.headers.get("Mcp-Session-Id"), json.loads(match.group(1) if match else text or "null")


def check(name, cfg, tool, args):
    url, token = cfg["url"], cfg["headers"]["Authorization"].replace("Bearer ", "")
    sid, _ = post(url, token, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "preflight", "version": "1"}}})
    post(url, token, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    _, tools = post(url, token, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, sid)
    n_tools = len(tools["result"]["tools"])
    count = 0
    for attempt in range(3):
        _, res = post(url, token, {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": tool, "arguments": args}}, sid)
        sc = res["result"].get("structuredContent") or {}
        items = sc.get("listings") or sc.get("products") or (sc.get("result") or {}).get("listings") or []
        count = len(items)
        if count:
            break
        time.sleep(3)
    status = "OK " if count else "FAIL"
    print(f"{status} {name}: {n_tools} tools, {tool} returned {count} items (attempts: {attempt + 1})")
    return count > 0


def main():
    servers = json.load(open(os.path.expanduser("~/.claude.json"))).get("mcpServers", {})
    ok = True
    for name, (tool, args) in SERVERS.items():
        if name not in servers:
            print(f"FAIL {name}: not configured in ~/.claude.json (see demo/README.md)")
            ok = False
            continue
        try:
            ok &= check(name, servers[name], tool, args)
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc}")
            ok = False
    if "alza" in servers:
        try:
            cfg = servers["alza"]
            token = cfg["headers"]["Authorization"].replace("Bearer ", "")
            sid, _ = post(cfg["url"], token, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "preflight", "version": "1"}}})
            post(cfg["url"], token, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
            _, res = post(cfg["url"], token, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
                "name": "search_products", "arguments": {"query": "macbook air", "discount": "isic", "limit": 1}}}, sid)
            has_isic = bool((res["result"].get("structuredContent") or {}).get("products"))
            print(("OK  " if has_isic else "WARN") + " alza ISIC session " + ("works" if has_isic else "missing/expired: run chronos-mcp/scripts/refresh-alza-session.sh"))
        except Exception as exc:  # noqa: BLE001
            print(f"WARN alza ISIC check failed: {exc}")
    sys.exit(0 if ok else 1)


main()

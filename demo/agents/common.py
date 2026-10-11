"""Shared pieces of the demo: configuration, the plan schema, helpers and the interactive question loop."""
import json
import logging
import os
import sys
import warnings
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from ui import ui

os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
EXAMPLE_QUERY = "RTX 4070 alebo podobny vykon do 600 EUR, nova alebo z bazaru"
SOURCES = ("bazos", "alza")
MCP_NAMES = {"bazos": "bazos-chronos", "alza": "alza"}  # source -> server name in ~/.claude.json


class Plan(BaseModel):
    """Output of the router."""
    sources: list[str] = Field(description="subset of ['bazos', 'alza']: used goods -> bazos, new goods -> alza")
    product: str = Field(description="short product search phrase")
    budget_eur: int


def mcp_servers() -> dict[str, dict]:
    """MCP server URLs and tokens from the Claude Code user config, so no secret is stored in the repo."""
    with open(os.path.expanduser("~/.claude.json")) as f:
        cfg = json.load(f)["mcpServers"]
    return {src: {"url": cfg[name]["url"], "headers": cfg[name]["headers"]} for src, name in MCP_NAMES.items()}


def valid_sources(plan: Plan) -> list[str]:
    """Keep only known sources; if the router returned none, ask both."""
    return [s for s in plan.sources if s in SOURCES] or list(SOURCES)


def format_findings(findings: dict[str, str]) -> str:
    return "\n\n".join(f"## {src.upper()}\n{text}" for src, text in findings.items())


def log(who: str, text: str) -> None:
    ui.say(who, text)


def questions():
    """Yield the questions to answer: the one given on the command line, otherwise ask in a loop until 'q'."""
    if len(sys.argv) > 1:
        yield " ".join(sys.argv[1:])
        return
    ui.welcome(EXAMPLE_QUERY)
    while True:
        try:
            text = ui.ask(EXAMPLE_QUERY)
        except (EOFError, KeyboardInterrupt):
            return
        if text.lower() in ("q", "quit", "exit"):
            return
        yield text or EXAMPLE_QUERY

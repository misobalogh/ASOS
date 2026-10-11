"""Terminal UI of the demo (rich): colored actor badges, one live column per scout, the final answer as a real table.

State lives in this module; the frameworks only call the small API below (say, begin_scouts, call, result,
scout_done, report), so LangGraph and CrewAI look exactly the same. All methods are thread-safe (CrewAI scouts run
in threads).
"""
import threading
from dataclasses import dataclass, field

from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

COLORS = {"user": "white", "router": "blue", "bazos": "dark_orange", "alza": "green", "analyst": "magenta",
          "reporter": "cyan", "mcp": "grey50"}
HISTORY_LINES = 6  # finished calls of a scout are collapsed to one line each; only the latest ones are kept


@dataclass
class Column:
    port: str = ""
    history: list[str] = field(default_factory=list)  # one line per finished call
    current: dict | None = None  # {"tool", "args", "result": (headline, rows) | None, "secs"}
    done: bool = False


class UI:
    def __init__(self):
        self.console = Console(highlight=False)
        self.lock = threading.RLock()
        self.tools: dict[str, list[str]] = {}  # source -> tool names (known after connecting)
        self.cols: dict[str, Column] = {}
        self.live: Live | None = None

    # --- plain lines ---------------------------------------------------------------------------------------------
    def badge(self, who: str) -> Text:
        color = COLORS.get(who.split("_")[0], "white")
        return Text(f" {who.upper().replace('_SCOUT', ''):9}", style=f"bold white on {color}")

    def say(self, who: str, text: str) -> None:
        with self.lock:
            self.console.print(self.badge(who), Text(text))

    def ask(self) -> str:
        return self.console.input("\n[bold]Question>[/] ").strip()

    def question(self, text: str) -> None:
        self.console.print(Rule(Text(text, style="bold"), style="grey50"))

    def info(self, text: str) -> None:
        self.console.print(Text(text, style="grey62"))

    def servers(self, ports: dict[str, str]) -> None:
        """The MCP servers the agents can reach: where they are and what they offer."""
        table = Table(title="MCP servers (read-only)", title_style="bold", header_style="bold", expand=False)
        for name in ("server", "address", "tools"):
            table.add_column(name)
        for src, port in ports.items():
            names = self.tools.get(src, [])
            shown = ", ".join(names[:4]) + (f", ... (+{len(names) - 4})" if len(names) > 4 else "")
            table.add_row(Text(src, style=f"bold {COLORS[src]}"), f"http://x.x.x.x:{port}/mcp", f"{len(names)}: {shown}")
        self.console.print(table)

    # --- scouts: one live column per source ------------------------------------------------------------------------
    def begin_scouts(self, ports: dict[str, str]) -> None:
        with self.lock:
            self.close()
            self.cols = {src: Column(port=port) for src, port in ports.items()}
            self.live = Live(get_renderable=self.render, console=self.console, refresh_per_second=8,
                             vertical_overflow="visible")
            self.live.start()

    def call(self, src: str, tool: str, args: dict) -> None:
        with self.lock:
            col = self.cols.get(src)
            if col is None:
                return
            self._collapse(col)
            col.current = {"tool": tool, "args": {k: v for k, v in args.items() if v not in (None, [], {}, "")}, "result": None}

    def result(self, src: str, headline: str, rows: list[str], secs: float) -> None:
        with self.lock:
            col = self.cols.get(src)
            if col and col.current:
                col.current.update(result=(headline, rows), secs=secs)

    def scout_done(self, src: str) -> None:
        with self.lock:
            if src in self.cols:
                self.cols[src].done = True
            if self.cols and all(c.done for c in self.cols.values()):
                self.close()

    def close(self) -> None:
        with self.lock:
            if self.live:
                self.live.stop()
                self.live = None

    def _collapse(self, col: Column) -> None:
        cur = col.current
        if cur:
            args = " ".join(f"{v}" if k in ("query", "q") else f"<={v}" for k, v in cur["args"].items()
                            if k in ("query", "q") or "max_price" in k or k == "price_max")
            outcome = cur["result"][0] if cur["result"] else "?"
            col.history.append(f"{cur['tool']}  {args}  ->  {outcome}")
            col.current = None

    def render(self):
        with self.lock:
            grid = Table.grid(expand=True, padding=(0, 1))
            panels = []
            for src, col in self.cols.items():
                color = COLORS.get(src, "white")
                n = len(self.tools.get(src, []))
                title = f"[bold {color}]{src.upper()}[/]  :{col.port}" + (f"  [dim]{n} tools[/]" if n else "")
                grid.add_column(ratio=1)
                panels.append(Panel(Group(*self._lines(col)), title=title, title_align="left", border_style=color,
                                    padding=(0, 1)))
            grid.add_row(*panels)
            return grid

    def _lines(self, col: Column) -> list:
        lines = [Text(h, style="grey50", no_wrap=True, overflow="ellipsis") for h in col.history[-HISTORY_LINES:]]
        cur = col.current
        if cur:
            lines.append(Text(f"--> {cur['tool']}", style="bold"))
            for key, value in cur["args"].items():
                lines.append(Text(f"      {key}: {value}", style="grey70", no_wrap=True, overflow="ellipsis"))
            if cur["result"]:
                headline, rows = cur["result"]
                lines.append(Text(f"<-- {cur['secs']:.1f} s  {headline}", style="bold", no_wrap=True,
                                  overflow="ellipsis"))
                lines.extend(Text(f"      {row}", no_wrap=True, overflow="ellipsis") for row in rows)
            else:
                lines.append(Spinner("dots", text=" waiting for the server ...", style="yellow"))
        if col.done:
            lines.append(Text("done", style="bold green"))
        return lines or [Spinner("dots", text=" connecting ...", style="yellow")]

    # --- final answer ----------------------------------------------------------------------------------------------
    def report(self, markdown: str) -> None:
        self.close()
        self.console.print(Panel(Markdown(markdown), title="[bold cyan]REPORTER[/]", title_align="left",
                                 border_style="cyan", padding=(1, 2)))


ui = UI()

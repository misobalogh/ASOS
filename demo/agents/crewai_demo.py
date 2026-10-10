"""Price scout in CrewAI: a Flow (router -> bazos || alza -> analyst -> reporter), each step is a small Crew.

Run:  uv run python crewai_demo.py ["your question"]     (without an argument it asks interactively)
"""
import asyncio
import os

import prompts
from common import (
    MODEL,
    Plan,
    format_findings,
    log,
    mcp_servers,
    questions,
    valid_sources,
)
from crewai import LLM, Agent, Crew, Task
from crewai.flow.flow import Flow, and_, listen, start
from crewai_tools import MCPServerAdapter
from pydantic import BaseModel, Field

llm = LLM(model=f"gemini/{MODEL}", api_key=os.environ["GEMINI_API_KEY"])


# --- helpers -----------------------------------------------------------------------------------------------------------
def run_crew(role: str, rules: str, task: str, tools: list | None = None, output=None):
    """One agent doing one task. rules = backstory (standing instruction), task = the concrete job."""
    agent = Agent(role=role, goal=role, backstory=rules, tools=tools or [], llm=llm, max_iter=8)
    job = Task(description=task, expected_output="Answer as requested above.", agent=agent, output_pydantic=output)
    return Crew(agents=[agent], tasks=[job]).kickoff()


def run_scout(source: str, plan: Plan, query: str) -> str:
    """A scout sees only the tools of its own MCP server (opened for the duration of the run)."""
    cfg = mcp_servers()[source]
    params = {"url": cfg["url"], "transport": "streamable-http", "headers": cfg["headers"]}
    task = prompts.SCOUT_TASK.format(source=source, product=plan.product, budget=plan.budget_eur, query=query)
    with MCPServerAdapter(params) as tools:
        return run_crew(f"{source} scout", prompts.SCOUT_RULES, task, tools=list(tools)).raw


# --- flow --------------------------------------------------------------------------------------------------------------
class State(BaseModel):
    query: str = ""
    plan: Plan | None = None
    findings: dict[str, str] = Field(default_factory=dict)
    analysis: str = ""
    report: str = ""


class PriceScoutFlow(Flow[State]):
    @start()
    def router(self):
        task = prompts.ROUTER_TASK.format(query=self.state.query)
        plan = run_crew("router", prompts.ROUTER_RULES, task, output=Plan).pydantic
        plan.sources = valid_sources(plan)
        log("router", f"sources -> {plan.sources}, product={plan.product!r}, budget={plan.budget_eur} EUR")
        self.state.plan = plan

    async def _scout(self, source: str):
        if source in self.state.plan.sources:
            log(f"{source}_scout", "mcp.call ...")
            text = await asyncio.to_thread(run_scout, source, self.state.plan, self.state.query)
            self.state.findings[source] = text
            log(f"{source}_scout", "done")

    @listen(router)
    async def bazos_scout(self):
        await self._scout("bazos")

    @listen(router)
    async def alza_scout(self):
        await self._scout("alza")

    @listen(and_(bazos_scout, alza_scout))
    def analyst(self):
        log("analyst", "comparing price, condition, warranty")
        task = prompts.ANALYST_TASK.format(query=self.state.query, findings=format_findings(self.state.findings))
        self.state.analysis = run_crew("analyst", prompts.ANALYST_RULES, task).raw

    @listen(analyst)
    def reporter(self):
        log("reporter", "writing the recommendation")
        task = prompts.REPORTER_TASK.format(
            findings=format_findings(self.state.findings), analysis=self.state.analysis)
        self.state.report = run_crew("reporter", prompts.REPORTER_RULES, task).raw


def main():
    for query in questions():
        log("user", query)
        flow = PriceScoutFlow(suppress_flow_events=True)
        try:
            flow.kickoff(inputs={"query": query})
            print("\n" + flow.state.report)
        except Exception as exc:  # e.g. Gemini free tier limit (429): keep the loop alive
            print(f"\nFAILED: {type(exc).__name__}: {str(exc)[:300]}")


main()

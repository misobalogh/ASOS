"""Price scout as a LangGraph graph: router -> (bazos || alza) -> analyst -> reporter.

Run:  uv run python langgraph_demo.py ["your question"]     (without an argument it asks interactively)
"""
import asyncio
import operator
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.types import Send

import prompts
import mcp_trace as trace
from common import MODEL, SOURCES, Plan, format_findings, log, mcp_servers, questions, valid_sources

llm = ChatGoogleGenerativeAI(model=MODEL, max_retries=6)  # retries cover the free tier limit (429)


# --- state shared by all nodes -----------------------------------------------------------------------------------------
class State(TypedDict):
    query: str
    plan: Plan
    findings: Annotated[dict[str, str], operator.or_]  # each scout adds its own key, merged after the parallel step
    analysis: str
    report: str


async def ask(rules: str, task: str) -> str:
    """One plain LLM call: standing instruction + concrete task."""
    res = await llm.ainvoke([SystemMessage(rules), HumanMessage(task)])
    return res.text


# --- nodes -------------------------------------------------------------------------------------------------------------
async def router(state: State):
    plan = await llm.with_structured_output(Plan).ainvoke(
        [SystemMessage(prompts.ROUTER_RULES), HumanMessage(prompts.ROUTER_TASK.format(query=state["query"]))])
    plan.sources = valid_sources(plan)
    log("router", f"sources -> {plan.sources}, product={plan.product!r}, budget={plan.budget_eur} EUR")
    return {"plan": plan}


def fan_out(state: State):
    """Conditional edge: start one scout per chosen source, in parallel."""
    return [Send(f"{src}_scout", state) for src in state["plan"].sources]


def make_scout(source: str, tools: list):
    """A scout is a small ReAct agent that sees only the tools of its own MCP server."""
    agent = create_react_agent(llm, tools, prompt=prompts.SCOUT_RULES)

    async def scout(state: State):
        log(f"{source}_scout", "mcp.call ...")
        task = prompts.SCOUT_TASK.format(
            source=source, product=state["plan"].product, budget=state["plan"].budget_eur, query=state["query"])
        res = await agent.ainvoke({"messages": [HumanMessage(task)]})
        log(f"{source}_scout", f"done, {len(res['messages'])} messages")
        return {"findings": {source: res["messages"][-1].text}}

    return scout


async def analyst(state: State):
    log("analyst", "comparing price, condition, warranty")
    task = prompts.ANALYST_TASK.format(query=state["query"], findings=format_findings(state["findings"]))
    return {"analysis": await ask(prompts.ANALYST_RULES, task)}


async def reporter(state: State):
    log("reporter", "writing the recommendation")
    task = prompts.REPORTER_TASK.format(findings=format_findings(state["findings"]), analysis=state["analysis"])
    return {"report": await ask(prompts.REPORTER_RULES, task)}


# --- graph -------------------------------------------------------------------------------------------------------------
async def build_graph():
    client = MultiServerMCPClient(
        {src: {**cfg, "transport": "streamable_http"} for src, cfg in mcp_servers().items()},
        tool_interceptors=[trace.langgraph_interceptor])
    g = StateGraph(State)
    g.add_node("router", router)
    g.add_node("analyst", analyst)
    g.add_node("reporter", reporter)
    for src in SOURCES:
        tools = await client.get_tools(server_name=src)  # connects: initialize + tools/list
        trace.banner(src, [t.name for t in tools])
        g.add_node(f"{src}_scout", make_scout(src, tools))
        g.add_edge(f"{src}_scout", "analyst")
    g.add_edge(START, "router")
    g.add_conditional_edges("router", fan_out, [f"{src}_scout" for src in SOURCES])
    g.add_edge("analyst", "reporter")
    g.add_edge("reporter", END)
    return g.compile()


async def main():
    app = await build_graph()
    for query in questions():
        log("user", query)
        try:
            out = await app.ainvoke({"query": query, "findings": {}})
            print("\n" + out["report"])
        except Exception as exc:  # e.g. Gemini quota: keep the loop alive
            print(f"\nFAILED: {type(exc).__name__}: {str(exc)[:300]}")


asyncio.run(main())

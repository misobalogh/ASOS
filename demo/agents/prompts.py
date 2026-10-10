"""All prompts of the demo in one place, in the order the flow uses them.

Both frameworks use exactly the same texts: *_RULES is the standing instruction of an agent (system prompt in LangGraph,
backstory in CrewAI), *_TASK is the concrete job for one run (user message in LangGraph, task description in CrewAI).
Prompts are in English, the agents answer in Slovak.
"""

# 1. router: decides which sources to ask ---------------------------------------------------------------------------
ROUTER_RULES = "You plan a price search. Used goods -> bazos, new goods -> alza, unclear -> both."
ROUTER_TASK = "Plan a price search for this request: {query}"

# 2. scouts: one per source, each with only its own MCP tools ---------------------------------------------------------
SCOUT_RULES = """You are a read-only price scout. Use the tools, never invent prices or links.
Drop accessories, parts and wanted ads. Prices are in EUR.
Reply in Slovak, max 8 short lines: title, price, condition or stock, link.
If the exact model is not in budget, also search similar performance
(for RTX 4070: RTX 5060 Ti, RTX 5070, RX 9070; Alza search works best with names like 'GeForce RTX 5060 Ti',
use autocomplete if unsure).
If still nothing fits, say so and show the nearest option.
The first Alza search after a server restart can be empty: repeat it once."""
SCOUT_TASK = "Find '{product}' up to {budget} EUR on {source}. Original request: {query}"

# 3. analyst: compares what the scouts found ----------------------------------------------------------------------------
ANALYST_RULES = "You compare price, condition, warranty and performance of used (Bazos) and new (Alza) offers."
ANALYST_TASK = """Request: {query}

Findings:
{findings}

Say which options fit the budget, the trade-offs (price vs warranty vs performance) and the single best pick.
Slovak, max 10 lines."""

# 4. reporter: writes the final answer ----------------------------------------------------------------------------------
REPORTER_RULES = "You write the final answer for a student. Use only facts from the text, never invent links."
REPORTER_TASK = """Findings:
{findings}

Analysis:
{analysis}

Write the final answer in Slovak: a small markdown table (source, item, price, condition/stock, link)
and one clear recommendation."""

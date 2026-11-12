import asyncio
import inspect
import time

from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, START, END
from app.graph.state import GraphState
from app.config import get_settings
from app.agents import mock, openai_agents
from app.finance.validation import validate_plan
from app.observability import report


def observed(name, fn):
    async def execute(state):
        started = time.perf_counter()
        await report("node_started", name, message=f"{name} started")
        try:
            result = await fn(state) if inspect.iscoroutinefunction(fn) else await asyncio.to_thread(fn, state)
            await report("node_completed", name,
                         {"duration_ms": round((time.perf_counter() - started) * 1000, 2)},
                         f"{name} completed")
            return result
        except Exception:
            await report("node_failed", name, message=f"{name} failed")
            raise
    def execute_sync(state):
        if inspect.iscoroutinefunction(fn):
            raise RuntimeError("OpenAI graphs require ainvoke")
        return fn(state)
    return RunnableLambda(execute_sync, afunc=execute)


def build_graph(mode: str = "mock"):
    if mode not in ("mock", "openai"):
        raise ValueError("AGENT_MODE must be 'mock' or 'openai'")
    agents = mock if mode == "mock" else openai_agents

    def review_sync(state):
        return {"validation": validate_plan(state, agents.validation_agent(state)["validation"])}

    async def review_async(state):
        value = await agents.validation_agent(state)
        return {"validation": validate_plan(state, value["validation"])}

    def revise_sync(state):
        result = agents.operations_agent(state)
        return {**result, "revision_count": state.get("revision_count", 0) + 1}

    async def revise_async(state):
        result = await agents.operations_agent(state)
        return {**result, "revision_count": state.get("revision_count", 0) + 1}

    builder = StateGraph(GraphState)
    nodes = {
        "coordinator": mock.coordinator,
        "market": agents.market_agent,
        "competitors": agents.competitor_agent,
        "operations": agents.operations_agent,
        "finance": agents.finance_agent,
        "validation": review_sync if mode == "mock" else review_async,
        "revision": revise_sync if mode == "mock" else revise_async,
        "assemble": mock.assemble_plan,
    }
    for name, fn in nodes.items():
        builder.add_node(name, observed(name, fn))
    builder.add_edge(START, "coordinator")
    builder.add_edge("coordinator", "market")
    builder.add_edge("coordinator", "competitors")
    builder.add_edge(["market", "competitors"], "operations")
    builder.add_edge("operations", "finance")
    builder.add_edge("finance", "validation")
    builder.add_conditional_edges("validation", lambda state:
        "revision" if state["validation"].revision_required and state.get("revision_count", 0) < 1 else "assemble")
    builder.add_edge("revision", "finance")
    builder.add_edge("assemble", END)
    return builder.compile()


graph = build_graph(get_settings().agent_mode)

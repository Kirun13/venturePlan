"""Real agents use OpenAI Responses API structured output. No credentials are sent to the browser."""
from datetime import datetime, timezone
from urllib.parse import urlparse
import logging
from openai import AsyncOpenAI
from app.config import get_settings
from app.observability import report
from app.schemas.models import ResearchSource
from app.graph.state import GraphState
from app.schemas.models import MarketResult, CompetitorResult, OperationsResult, ValidationResult
from app.finance.calculations import calculate_finances
from app.agents.mock import coordinator, assemble_plan

logger = logging.getLogger(__name__)

PROMPTS = {
    "market": "You are a market research analyst. Analyze target audience, demand and market assumptions. Do not invent facts, citations, or statistics. If evidence is unavailable, clearly mark uncertainty. Return the requested structured fields. Write in Russian.",
    "competitors": "You are a competitor research analyst. Only name competitors you can substantiate from provided information or verified search. Otherwise leave competitors empty. Explain positioning and assumptions. Do not fabricate sources. Write in Russian.",
    "operations": "You are an operations planner. Produce a practical launch sequence, staffing, startup and monthly fixed costs, and unit variable costs in the user's currency. All prices without independent evidence must be explicitly labeled as estimates in assumptions. Avoid claiming cost estimates are verified. Write in Russian.",
    "validation": "You are a critical business-plan reviewer. Identify risks, conflicting assumptions, missing evidence, and financial inconsistencies. Return is_consistent false if material contradictions exist. Do not invent facts. Write in Russian.",
}

def _client():
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when AGENT_MODE=openai")
    return AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout, max_retries=settings.openai_max_retries)

async def _structured(schema, role: str, context: dict, web: bool = False):
    settings = get_settings()
    import json
    params = dict(model=settings.openai_model, instructions=PROMPTS[role], input=json.dumps(context, ensure_ascii=False, default=str), text_format=schema, store=False, max_output_tokens=settings.openai_max_output_tokens)
    # Search can be enabled only for research agents. Sources in output must be genuine.
    if web and settings.openai_web_search:
        params["tools"] = [{"type": "web_search"}]
    async with _client() as client:
        result = await client.responses.parse(**params)
    usage = result.usage
    await report("usage", role, {
        "model": result.model, "input_tokens": usage.input_tokens if usage else 0,
        "output_tokens": usage.output_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
    }, "Provider usage recorded")
    if result.output_parsed is None:
        raise RuntimeError(f"No structured response from {role} agent (refusal or incomplete response)")
    parsed = result.output_parsed
    if hasattr(parsed, "sources"):
        # Only provider annotations qualify as citations. Model-generated URLs alone do not.
        citations = {}
        if web and settings.openai_web_search:
            for item in result.output:
                for content in getattr(item, "content", []) or []:
                    for annotation in getattr(content, "annotations", []) or []:
                        url = getattr(annotation, "url", "")
                        if getattr(annotation, "type", "") == "url_citation" and urlparse(url).scheme in ("http", "https") and urlparse(url).hostname:
                            citations[url] = ResearchSource(url=url, title=getattr(annotation, "title", url),
                                retrieved_at=datetime.now(timezone.utc).isoformat())
        parsed.sources = list(citations)
        parsed.source_details = list(citations.values())
        if not citations:
            parsed.assumptions.append("No provider-cited evidence was returned; treat these findings as unverified")
    return parsed

async def market_agent(state: GraphState) -> dict:
    idea = state["idea"]
    result = await _structured(MarketResult, "market", {"business_idea": idea.model_dump()}, web=True)
    return {"market": result}

async def competitor_agent(state: GraphState) -> dict:
    result = await _structured(CompetitorResult, "competitors", {"business_idea": state["idea"].model_dump()}, web=True)
    return {"competitors": result}

async def operations_agent(state: GraphState) -> dict:
    result = await _structured(OperationsResult, "operations", {
        "business_idea": state["idea"].model_dump(),
        "market": state["market"].model_dump(),
        "competitors": state["competitors"].model_dump(),
        "review_feedback": state["validation"].model_dump() if state.get("validation") else None,
        "revision_instruction": "Reconsider unsupported costs in light of the review. Do not force affordability or invent evidence.",
    })
    return {"operations": result}

def finance_agent(state: GraphState) -> dict:
    result = calculate_finances(state["idea"], state["operations"])
    # Finance is deterministic; this is not a mock or an LLM arithmetic estimate.

    return {"finance": result}

async def validation_agent(state: GraphState) -> dict:
    result = await _structured(ValidationResult, "validation", {
        "idea": state["idea"].model_dump(), "market": state["market"].model_dump(),
        "competitors": state["competitors"].model_dump(), "operations": state["operations"].model_dump(),
        "finance": state["finance"].model_dump(),
    })
    if state["finance"].startup_costs > state["idea"].initial_budget:
        result.warnings.append("Startup costs exceed initial budget")
        result.is_consistent = False
    if state["finance"].break_even_units is None:
        result.warnings.append("Break-even undefined: non-positive unit contribution margin")
        result.is_consistent = False
    return {"validation": result}

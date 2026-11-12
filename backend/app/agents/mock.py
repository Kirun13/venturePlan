from app.graph.state import GraphState
from app.finance.calculations import calculate_finances
from app.schemas.models import (
    MarketResult, CompetitorResult, OperationsResult, CostItem,
    ValidationResult, BusinessPlan,
)


def coordinator(state: GraphState) -> dict:
    # Input validation occurs in FastAPI/Pydantic before the graph is invoked.
    return {}


def market_agent(state: GraphState) -> dict:
    idea = state["idea"]
    return {"market": MarketResult(
        audience=idea.target_audience,
        demand_summary=f"Mock market analysis for {idea.name} in {idea.region}.",
        assumptions=["Demand has not been researched"],
    )}


def competitor_agent(state: GraphState) -> dict:
    return {"competitors": CompetitorResult(
        competitors=[],
        positioning="Competitor research pending; no verified competitors yet.",
        assumptions=["No external search performed"],
    )}


def operations_agent(state: GraphState) -> dict:
    return {"operations": OperationsResult(
        launch_steps=["Validate demand", "Arrange resources", "Launch pilot"],
        startup_costs=[CostItem(name="Equipment (mock)", amount=500000)],
        monthly_fixed_costs=[CostItem(name="Rent (mock)", amount=150000)],
        variable_cost_per_unit=500,
        staffing=["Owner/operator"],
        assumptions=["All costs are placeholders in the input currency"],
    )}


def finance_agent(state: GraphState) -> dict:
    return {"finance": calculate_finances(state["idea"], state["operations"])}


def validation_agent(state: GraphState) -> dict:
    idea = state["idea"]
    finance = state["finance"]
    warnings = ["Mock analysis: no market or competitor evidence has been collected"]
    if finance.startup_costs > idea.initial_budget:
        warnings.append("Startup costs exceed initial budget")
    if finance.break_even_units is None:
        warnings.append("Unit contribution margin is non-positive; break-even is undefined")
    return {"validation": ValidationResult(
        risks=["Demand uncertainty", "Unverified operating costs"],
        warnings=warnings,
        is_consistent=not any("exceed" in w or "undefined" in w for w in warnings),
    )}


def assemble_plan(state: GraphState) -> dict:
    return {"plan": BusinessPlan(
        idea=state["idea"], market=state["market"],
        competitors=state["competitors"], operations=state["operations"],
        finance=state["finance"], validation=state["validation"],
        revision_count=state.get("revision_count", 0),
    )}

from app.graph.workflow import graph
from app.schemas.models import BusinessIdeaInput, BusinessPlan


def sample_idea():
    return BusinessIdeaInput(
        name="Coffee kiosk", description="A small takeaway coffee kiosk near an office district",
        region="Astana, Kazakhstan", target_audience="Office workers",
        initial_budget=2000000, unit_price=1500, estimated_monthly_units=1000,
    )


def test_graph_completes():
    result = graph.invoke({"idea": sample_idea()})
    plan = BusinessPlan.model_validate(result["plan"])
    assert plan.market.audience == "Office workers"
    assert plan.finance.monthly_revenue == 1500000
    assert plan.finance.monthly_profit == 850000
    assert plan.finance.break_even_units == 150
    assert plan.validation.is_consistent


def test_insufficient_budget_flagged():
    idea = sample_idea().model_copy(update={"initial_budget": 100000})
    plan = graph.invoke({"idea": idea})["plan"]
    assert not plan.validation.is_consistent

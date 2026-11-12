import asyncio
from types import SimpleNamespace as NS
from pydantic import ValidationError
import pytest

from app.agents import openai_agents
from app.config import get_settings
from app.graph.workflow import build_graph
from app.observability import event_sink
from app.schemas.models import BusinessIdeaInput, MarketResult


def idea(**updates):
    return BusinessIdeaInput(name="Coffee kiosk", description="Takeaway coffee for office workers",
                             target_audience="Office workers", initial_budget=2000000,
                             unit_price=1500, estimated_monthly_units=1000).model_copy(update=updates)


def test_financial_scenarios_and_payback():
    plan = build_graph("mock").invoke({"idea": idea()})["plan"]
    assert [s.monthly_units for s in plan.finance.scenarios] == [700, 1000, 1300]
    assert [s.monthly_profit for s in plan.finance.scenarios] == [550000, 850000, 1150000]
    assert plan.finance.payback_months == 0.59
    assert plan.finance.budget_gap == 0


def test_revision_is_bounded_and_does_not_hide_inconsistency():
    plan = build_graph("mock").invoke({"idea": idea(initial_budget=100000, unit_price=400)})["plan"]
    assert plan.revision_count == 1
    assert not plan.validation.is_consistent
    assert plan.finance.budget_gap == 400000
    assert plan.finance.payback_months is None
    assert plan.finance.break_even_units is None
    assert plan.validation.issues


def test_non_finite_money_rejected():
    with pytest.raises(ValidationError):
        BusinessIdeaInput.model_validate({**idea().model_dump(), "initial_budget": float("inf")})


@pytest.mark.parametrize("search", [True, False])
def test_only_provider_citations_are_kept_and_usage_is_recorded(monkeypatch, search):
    monkeypatch.setattr(get_settings(), "openai_web_search", search)
    calls = []
    class FakeClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def parse(self, **params):
            calls.append(params)
            return NS(model="configured-model", usage=NS(input_tokens=10, output_tokens=5, total_tokens=15),
                      output_parsed=MarketResult(audience="Workers", demand_summary="Assumed demand",
                                                sources=["https://invented.test"]),
                      output=[NS(content=[NS(annotations=[NS(type="url_citation", url="https://evidence.test/page", title="Evidence"),
                                                           NS(type="url_citation", url="javascript:alert(1)", title="Unsafe")])])])
        @property
        def responses(self):
            return self
    monkeypatch.setattr(openai_agents, "_client", FakeClient)
    async def scenario():
        events = []
        async def sink(kind, node, details, message):
            events.append((kind, details))
        token = event_sink.set(sink)
        try:
            result = await openai_agents._structured(MarketResult, "market", {}, web=True)
        finally:
            event_sink.reset(token)
        assert result.sources == (["https://evidence.test/page"] if search else [])
        assert bool(result.source_details) == search
        assert events[0][1]["total_tokens"] == 15
        assert ("tools" in calls[0]) == search
        assert calls[0]["store"] is False
    asyncio.run(scenario())

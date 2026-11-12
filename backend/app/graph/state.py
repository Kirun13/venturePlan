from typing import TypedDict
from app.schemas.models import (
    BusinessIdeaInput, MarketResult, CompetitorResult,
    OperationsResult, FinanceResult, ValidationResult, BusinessPlan,
)


class GraphState(TypedDict, total=False):
    idea: BusinessIdeaInput
    market: MarketResult
    competitors: CompetitorResult
    operations: OperationsResult
    finance: FinanceResult
    validation: ValidationResult
    plan: BusinessPlan
    revision_count: int

from typing import Literal
from pydantic import BaseModel, Field, model_validator


class BusinessIdeaInput(BaseModel):
    model_config = {"allow_inf_nan": False}
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(min_length=10, max_length=2000)
    region: str = Field(default="Astana, Kazakhstan", min_length=2)
    target_audience: str = Field(min_length=3)
    initial_budget: float = Field(gt=0)
    currency: Literal["KZT", "USD", "EUR"] = "KZT"
    unit_price: float = Field(gt=0)
    estimated_monthly_units: int = Field(gt=0)


class ResearchSource(BaseModel):
    url: str
    title: str
    retrieved_at: str


class MarketResult(BaseModel):
    audience: str
    demand_summary: str
    assumptions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    source_details: list[ResearchSource] = Field(default_factory=list)


class CompetitorResult(BaseModel):
    competitors: list[str]
    positioning: str
    assumptions: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    source_details: list[ResearchSource] = Field(default_factory=list)


class CostItem(BaseModel):
    model_config = {"allow_inf_nan": False}
    name: str
    amount: float = Field(ge=0)


class OperationsResult(BaseModel):
    model_config = {"allow_inf_nan": False}
    launch_steps: list[str]
    startup_costs: list[CostItem]
    monthly_fixed_costs: list[CostItem]
    variable_cost_per_unit: float = Field(ge=0)
    staffing: list[str]
    assumptions: list[str] = Field(default_factory=list)


class FinanceScenario(BaseModel):
    name: str
    monthly_units: int
    monthly_revenue: float
    monthly_profit: float
    payback_months: float | None


class FinanceResult(BaseModel):
    currency: str
    monthly_revenue: float
    monthly_fixed_costs: float
    monthly_variable_costs: float
    monthly_profit: float
    startup_costs: float
    break_even_units: int | None
    assumptions: list[str] = Field(default_factory=list)
    budget_gap: float = 0
    payback_months: float | None = None
    scenarios: list[FinanceScenario] = Field(default_factory=list)


class ValidationResult(BaseModel):
    risks: list[str]
    warnings: list[str]
    is_consistent: bool
    issues: list[str] = Field(default_factory=list)
    revision_required: bool = False


class BusinessPlan(BaseModel):
    idea: BusinessIdeaInput
    market: MarketResult
    competitors: CompetitorResult
    operations: OperationsResult
    finance: FinanceResult
    validation: ValidationResult
    status: Literal["draft"] = "draft"
    revision_count: int = 0

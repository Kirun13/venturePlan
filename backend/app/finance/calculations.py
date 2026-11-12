from math import ceil
from app.schemas.models import BusinessIdeaInput, OperationsResult, FinanceResult, FinanceScenario


def calculate_finances(idea: BusinessIdeaInput, operations: OperationsResult) -> FinanceResult:
    fixed = sum(item.amount for item in operations.monthly_fixed_costs)
    startup = sum(item.amount for item in operations.startup_costs)
    revenue = idea.unit_price * idea.estimated_monthly_units
    variable = operations.variable_cost_per_unit * idea.estimated_monthly_units
    profit = revenue - variable - fixed
    margin = idea.unit_price - operations.variable_cost_per_unit
    scenarios = []
    for name, factor in (("conservative", 0.7), ("base", 1.0), ("optimistic", 1.3)):
        units = round(idea.estimated_monthly_units * factor)
        scenario_profit = units * margin - fixed
        scenarios.append(FinanceScenario(
            name=name, monthly_units=units, monthly_revenue=units * idea.unit_price,
            monthly_profit=scenario_profit,
            payback_months=round(startup / scenario_profit, 2) if scenario_profit > 0 else None))
    return FinanceResult(
        currency=idea.currency, monthly_revenue=revenue, monthly_fixed_costs=fixed,
        monthly_variable_costs=variable, monthly_profit=profit, startup_costs=startup,
        break_even_units=ceil(fixed / margin) if margin > 0 else None,
        budget_gap=max(0, startup - idea.initial_budget),
        payback_months=round(startup / profit, 2) if profit > 0 else None,
        scenarios=scenarios,
        assumptions=["Price and base sales volume are supplied by the user",
                     "Operating costs are estimates unless supported by independent evidence",
                     "Scenario volumes are 70%, 100% and 130% of base volume",
                     "Constant unit price and costs; excludes taxes, financing and ramp-up"],
    )

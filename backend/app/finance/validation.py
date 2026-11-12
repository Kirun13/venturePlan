from app.schemas.models import ValidationResult


def validate_plan(state, review: ValidationResult) -> ValidationResult:
    """Combine model review with rules that cannot be overridden by the model."""
    idea, finance = state["idea"], state["finance"]
    warnings = list(review.warnings)
    issues = []
    if finance.startup_costs > idea.initial_budget:
        issues.append("Startup costs exceed initial budget")
    if finance.break_even_units is None:
        issues.append("Unit contribution margin is non-positive; break-even is undefined")
    if finance.monthly_profit <= 0:
        warnings.append("Base scenario is not profitable; payback is unavailable")
    for section in ("market", "competitors"):
        if not state[section].sources:
            warnings.append(f"No provider-cited sources for {section}; treat findings as assumptions")
    warnings = list(dict.fromkeys(warnings + issues))
    return review.model_copy(update={
        "warnings": warnings, "issues": list(dict.fromkeys(review.issues + issues)),
        "is_consistent": review.is_consistent and not issues,
        "revision_required": bool(issues) or review.revision_required,
    })

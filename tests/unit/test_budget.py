"""Budget approvals use exact integer kopeks, not agent arithmetic."""

import pytest

from engineering_gateway.domain.budget import BudgetGate, BudgetLine, BudgetPlan


def test_budget_gate_counts_quantity_and_contingency_at_limit() -> None:
    plan = BudgetPlan(
        lines=(
            BudgetLine(
                id="part-1", description="Flight controller", quantity=2,
                unit_cost_kopeks=4_500_000, source_uri="git:cost-estimate",
            ),
        ),
        contingency_kopeks=1_000_000,
    )
    decision = BudgetGate(10_000_000).require_within_limit(plan)
    assert decision.accepted
    assert decision.total_kopeks == 10_000_000
    with pytest.raises(ValueError, match="exceeds limit"):
        BudgetGate(9_999_999).require_within_limit(plan)


def test_duplicate_ids_cannot_double_count_a_cost_line() -> None:
    line = BudgetLine(
        id="part-1", description="Part", quantity=1,
        unit_cost_kopeks=1, source_uri="git:cost-estimate",
    )
    with pytest.raises(ValueError, match="unique"):
        BudgetPlan(lines=(line, line))

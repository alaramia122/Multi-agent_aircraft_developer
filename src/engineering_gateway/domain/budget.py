"""Deterministic project cost gate, expressed in integer kopeks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BudgetLine(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    unit_cost_kopeks: int = Field(ge=0)
    source_uri: str = Field(min_length=1)

    @property
    def total_kopeks(self) -> int:
        return self.quantity * self.unit_cost_kopeks


class BudgetPlan(BaseModel):
    """Versioned cost inputs with provenance for each line item."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    currency: Literal["RUB"] = "RUB"
    lines: tuple[BudgetLine, ...] = Field(min_length=1)
    contingency_kopeks: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def unique_line_ids(self) -> BudgetPlan:
        ids = [line.id for line in self.lines]
        if len(ids) != len(set(ids)):
            raise ValueError("budget line IDs must be unique")
        return self

    @property
    def total_kopeks(self) -> int:
        return sum(line.total_kopeks for line in self.lines) + self.contingency_kopeks


@dataclass(frozen=True)
class BudgetDecision:
    limit_kopeks: int
    total_kopeks: int

    @property
    def accepted(self) -> bool:
        return self.total_kopeks <= self.limit_kopeks


class BudgetGate:
    def __init__(self, limit_kopeks: int):
        if limit_kopeks <= 0:
            raise ValueError("budget limit must be positive")
        self.limit_kopeks = limit_kopeks

    def evaluate(self, plan: BudgetPlan) -> BudgetDecision:
        return BudgetDecision(self.limit_kopeks, plan.total_kopeks)

    def require_within_limit(self, plan: BudgetPlan) -> BudgetDecision:
        decision = self.evaluate(plan)
        if not decision.accepted:
            raise ValueError(
                f"cost estimate {decision.total_kopeks} kopeks exceeds "
                f"limit {decision.limit_kopeks} kopeks"
            )
        return decision

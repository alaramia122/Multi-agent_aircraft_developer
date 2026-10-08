"""Stable contracts for the AI engineering-agent boundary.

The Gateway remains authoritative for authorization, validation, reconciliation and
approval. These models describe what an agent may receive and return; they do not
execute an LLM or grant engineering permissions.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AgentRole(StrEnum):
    CHIEF_ENGINEER = "chief_engineer"
    REQUIREMENTS = "requirements"
    SYSTEM_ARCHITECT = "system_architect"
    SAFETY = "safety"
    SOFTWARE_ARCHITECT = "software_architect"
    VERIFICATION = "verification"
    CONFIGURATION = "configuration"
    REVIEWER = "reviewer"
    COST = "cost"


class AgentTaskKind(StrEnum):
    ANALYZE = "analyze"
    PROPOSE = "propose"
    REVIEW = "review"


class AgentTaskState(StrEnum):
    REQUESTED = "requested"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class AgentContextRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID | None = None
    baseline_id: UUID | None = None
    change_request_id: UUID | None = None
    source_versions: tuple[str, ...] = ()


class AgentTask(BaseModel):
    """Versioned, bounded task envelope sent from orchestration to an agent."""

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default="1.0", pattern=r"^1\.0$")
    task_id: UUID
    role: AgentRole
    kind: AgentTaskKind
    objective: str = Field(min_length=1, max_length=12000)
    context: AgentContextRef
    allowed_tool_ids: tuple[str, ...] = ()
    inputs: dict[str, Any] = Field(default_factory=dict)


class AgentProposal(BaseModel):
    """Agent result; it is a proposal/evidence package, never an approval."""

    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(default="1.0", pattern=r"^1\.0$")
    task_id: UUID
    role: AgentRole
    state: AgentTaskState
    summary: str = Field(min_length=1, max_length=12000)
    proposed_elements: tuple[dict[str, Any], ...] = ()
    proposed_relations: tuple[dict[str, Any], ...] = ()
    evidence_refs: tuple[str, ...] = ()
    requested_tool_ids: tuple[str, ...] = ()
    blocking_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AgentContextRef",
    "AgentProposal",
    "AgentRole",
    "AgentTask",
    "AgentTaskKind",
    "AgentTaskState",
]

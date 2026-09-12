"""Immutable baseline registry primitives."""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ExternalSystemVersion(BaseModel):
    """Version/reference of an authoritative external engineering system."""

    model_config = ConfigDict(extra="forbid")
    system: str = Field(min_length=1)
    version: str = Field(min_length=1)


class Baseline(BaseModel):
    """Immutable engineering baseline identity and reproducibility references."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1)
    git_repository: str = Field(min_length=1)
    git_commit: str = Field(min_length=1)
    git_tag: str | None = None
    external_versions: tuple[ExternalSystemVersion, ...] = ()
    profile_id: str | None = Field(default=None, min_length=1)
    profile_version: str | None = Field(default=None, min_length=1)


class BaselineRegistry:
    """In-memory registry with immutable baseline identities."""

    def __init__(self) -> None:
        self._baselines: dict[UUID, Baseline] = {}

    async def register(self, baseline: Baseline) -> Baseline:
        existing = self._baselines.get(baseline.id)
        if existing is not None and existing != baseline:
            raise ValueError(f"baseline '{baseline.id}' already exists and is immutable")
        self._baselines[baseline.id] = baseline
        return baseline

    async def get(self, baseline_id: UUID) -> Baseline | None:
        return self._baselines.get(baseline_id)

    async def list(self) -> list[Baseline]:
        return [self._baselines[key] for key in sorted(self._baselines, key=str)]

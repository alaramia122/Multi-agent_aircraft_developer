from uuid import uuid4

import pytest
from pydantic import ValidationError

from engineering_gateway.domain.baselines import Baseline, BaselineRegistry, ExternalSystemVersion


def make_baseline() -> Baseline:
    return Baseline(
        name="baseline-1",
        git_repository="example/project",
        git_commit="0123456789abcdef",
        git_tag="v1.0.0",
        external_versions=(
            ExternalSystemVersion(system="strictdoc", version="rev-1"),
            ExternalSystemVersion(system="capella", version="model-1"),
        ),
    )


def test_baseline_is_immutable() -> None:
    baseline = make_baseline()

    with pytest.raises(ValidationError):
        baseline.name = "changed"


@pytest.mark.asyncio
async def test_registry_round_trip_and_deterministic_listing() -> None:
    registry = BaselineRegistry()
    first = make_baseline()
    second = make_baseline().model_copy(update={"id": uuid4(), "name": "baseline-2"})

    await registry.register(second)
    await registry.register(first)

    assert await registry.get(first.id) == first
    assert await registry.list() == sorted([first, second], key=lambda item: str(item.id))


@pytest.mark.asyncio
async def test_registry_rejects_different_duplicate_identity() -> None:
    registry = BaselineRegistry()
    baseline = make_baseline()
    await registry.register(baseline)
    conflicting = baseline.model_copy(update={"name": "changed"})

    with pytest.raises(ValueError, match="immutable"):
        await registry.register(conflicting)


@pytest.mark.asyncio
async def test_registry_is_idempotent_for_same_baseline() -> None:
    registry = BaselineRegistry()
    baseline = make_baseline()

    await registry.register(baseline)
    await registry.register(baseline)

    assert await registry.list() == [baseline]

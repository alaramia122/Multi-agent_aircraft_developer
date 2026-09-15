"""Tests for Gateway composition-root boundary validation."""

from __future__ import annotations

import pytest

from engineering_gateway.infrastructure.adapter_composition import ExternalAdapterSet
from engineering_gateway.infrastructure.gateway_context import governed_gateway_context


@pytest.mark.asyncio
async def test_governed_context_rejects_ambiguous_adapter_inputs_before_opening_database() -> None:
    """The two adapter composition modes are mutually exclusive at the boundary."""
    with pytest.raises(ValueError, match="either adapter_set or external_adapters, not both"):
        async with governed_gateway_context(
            object(),
            external_adapters=(),
            adapter_set=ExternalAdapterSet(),
        ):
            raise AssertionError("the context must reject ambiguous adapter inputs")

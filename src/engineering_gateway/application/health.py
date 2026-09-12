"""Application-level health service placeholder."""

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthService:
    """Service boundary reserved for dependency checks in later stages."""

    async def check(self) -> bool:
        return True

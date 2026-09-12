"""Profile registry implementations."""

from engineering_gateway.domain.profiles import StandardProfile


class InMemoryStandardProfileRegistry:
    """Deterministic registry used by the application and tests.

    Persistence is intentionally a separate concern; this implementation provides
    the first executable registry boundary before PostgreSQL profile persistence.
    """

    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], StandardProfile] = {}

    async def register(self, profile: StandardProfile) -> None:
        key = (profile.id, profile.version)
        existing = self._profiles.get(key)
        if existing is not None and existing != profile:
            raise ValueError(f"profile '{profile.id}@{profile.version}' already exists")
        self._profiles[key] = profile

    async def get(self, profile_id: str, version: str) -> StandardProfile | None:
        return self._profiles.get((profile_id, version))

    async def list(self) -> list[StandardProfile]:
        return [self._profiles[key] for key in sorted(self._profiles)]

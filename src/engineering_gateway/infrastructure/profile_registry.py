"""Profile registry implementations."""

from engineering_gateway.application.profile_engine import StandardProfileEngine
from engineering_gateway.domain.profiles import StandardProfile


class InMemoryStandardProfileRegistry:
    """Deterministic registry with explicit active-profile selection."""

    def __init__(self) -> None:
        self._profiles: dict[tuple[str, str], StandardProfile] = {}
        self._active: set[tuple[str, str]] = set()

    async def register(self, profile: StandardProfile) -> None:
        StandardProfileEngine.validate_profile(profile)
        key = (profile.id, profile.version)
        existing = self._profiles.get(key)
        if existing is not None and existing != profile:
            raise ValueError(f"profile '{profile.id}@{profile.version}' already exists")
        self._profiles[key] = profile

    async def activate(self, profile_id: str, version: str) -> StandardProfile:
        profile = await self.get(profile_id, version)
        if profile is None:
            raise ValueError(f"profile '{profile_id}@{version}' was not found")
        StandardProfileEngine.validate_profile(profile)
        self._active.add((profile_id, version))
        return profile

    async def deactivate(self, profile_id: str, version: str) -> None:
        self._active.discard((profile_id, version))

    async def is_active(self, profile_id: str, version: str) -> bool:
        return (profile_id, version) in self._active

    async def get_active(self) -> list[StandardProfile]:
        return [self._profiles[key] for key in sorted(self._active) if key in self._profiles]

    async def get(self, profile_id: str, version: str) -> StandardProfile | None:
        return self._profiles.get((profile_id, version))

    async def list(self) -> list[StandardProfile]:
        return [self._profiles[key] for key in sorted(self._profiles)]

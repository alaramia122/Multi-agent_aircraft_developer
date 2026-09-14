"""Load executable Standard Profiles from JSON documents."""

from __future__ import annotations

import json
from pathlib import Path

from engineering_gateway.domain.profiles import StandardProfile


def load_profile(path: str | Path) -> StandardProfile:
    """Load and validate one Standard Profile from a UTF-8 JSON file."""
    profile_path = Path(path)
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"Standard Profile file not found: {profile_path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid Standard Profile JSON in '{profile_path}': {exc.msg}") from exc

    try:
        return StandardProfile.model_validate(payload)
    except Exception as exc:
        raise ValueError(f"Invalid Standard Profile in '{profile_path}': {exc}") from exc


__all__ = ["load_profile"]

"""Load declarative Standard Profiles from version-controlled JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from engineering_gateway.domain.profiles import StandardProfile


class StandardProfileLoadError(ValueError):
    """Raised when a profile file cannot be loaded or validated."""


def load_standard_profile(path: str | Path) -> StandardProfile:
    """Load and validate one Standard Profile from a JSON document.

    The file is treated as configuration/provenance input. It is not modified by
    the loader and the returned domain object remains subject to normal registry
    validation and activation rules.
    """

    profile_path = Path(path)
    try:
        raw = profile_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StandardProfileLoadError(f"cannot read profile '{profile_path}'") from exc
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StandardProfileLoadError(f"profile '{profile_path}' contains invalid JSON") from exc
    if not isinstance(document, dict):
        raise StandardProfileLoadError(f"profile '{profile_path}' must contain a JSON object")
    try:
        return StandardProfile.model_validate(document)
    except ValueError as exc:
        raise StandardProfileLoadError(f"profile '{profile_path}' is invalid: {exc}") from exc


__all__ = ["StandardProfileLoadError", "load_standard_profile"]

"""Read a content-bearing engineering artifact from an exact Git commit."""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit


class ArtifactError(ValueError):
    """The source is absent, mutable, or does not match its declared content hash."""


def read_git_artifact(source_uri: str | None, repository: Path, *, suffix: str) -> bytes:
    """Resolve git-artifact://<commit>/<path>#sha256=<hex> without a checkout.

    The repository is deployment configuration, never selected by an element. Git
    object identity and the independently declared SHA-256 both become provenance.
    """
    if not source_uri:
        raise ArtifactError("a content-bearing Git artifact source_uri is required")
    parts = urlsplit(source_uri)
    commit = parts.netloc
    relative = unquote(parts.path.lstrip("/"))
    if (
        parts.scheme != "git-artifact" or parts.query
        or not re.fullmatch(r"[0-9a-f]{40}", commit)
        or not re.fullmatch(r"sha256=[0-9a-f]{64}", parts.fragment)
        or not relative.startswith("engineering/")
        or not relative.endswith(suffix)
        or any(part in ("", ".", "..") for part in relative.split("/"))
        or any(ord(character) < 32 for character in relative)
    ):
        raise ArtifactError("invalid immutable engineering artifact URI")
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "show", f"{commit}:{relative}"],
            capture_output=True, check=False, timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ArtifactError("Git artifact lookup failed") from exc
    if result.returncode or not result.stdout:
        raise ArtifactError("Git artifact is missing or empty")
    if hashlib.sha256(result.stdout).hexdigest() != parts.fragment[7:]:
        raise ArtifactError("Git artifact content hash mismatch")
    return result.stdout

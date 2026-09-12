"""Local Git adapter implementation for reproducible repository references."""

from pathlib import Path
import subprocess


class LocalGitAdapter:
    """Git adapter backed by the local Git CLI.

    The adapter deliberately performs only repository operations. Baseline approval,
    authorization and audit decisions remain Gateway responsibilities.
    """

    system_name = "git"

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds

    async def get_commit(self, repository: str, commit: str) -> str | None:
        """Return the resolved commit SHA when the object exists in the repository."""
        output = self._run(repository, "rev-parse", "--verify", f"{commit}^{{commit}}")
        return output if output is not None else None

    async def create_tag(self, repository: str, commit: str, tag: str) -> None:
        """Create a lightweight tag for an existing commit.

        Existing tags are never moved implicitly. Git itself rejects an already existing
        tag, preserving baseline immutability at the repository boundary.
        """
        if not tag or tag.startswith("-"):
            raise ValueError("tag must be a non-empty Git reference name")
        if self._run(repository, "rev-parse", "--verify", f"{commit}^{{commit}}") is None:
            raise ValueError(f"commit '{commit}' does not exist")
        self._run_required(repository, "tag", tag, commit)

    def _run(self, repository: str, *args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "-C", str(Path(repository)), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def _run_required(self, repository: str, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(Path(repository)), *args],
                check=False,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("Git command timed out") from exc
        except OSError as exc:
            raise RuntimeError("Git executable could not be started") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or "unknown Git error"
            raise RuntimeError(f"Git command failed: {detail}")
        return result.stdout.strip()


__all__ = ["LocalGitAdapter"]

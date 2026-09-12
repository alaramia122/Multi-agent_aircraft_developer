"""Local Git adapter implementation for reproducible repository references."""

from pathlib import Path
import subprocess

from engineering_gateway.domain.adapters import GitSnapshot


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

    async def get_snapshot(self, repository: str, ref: str = "HEAD") -> GitSnapshot:
        """Resolve a repository ref to a reproducible commit snapshot."""
        commit = self._run_required(repository, "rev-parse", "--verify", f"{ref}^{{commit}}")
        tag = self._run(repository, "describe", "--exact-match", "--tags", commit)
        return GitSnapshot(repository=str(Path(repository).resolve()), commit=commit, tag=tag)

    async def create_tag(self, repository: str, tag: str, commit: str) -> GitSnapshot:
        """Create a lightweight tag without moving an existing reference."""
        if not tag or tag.startswith("-"):
            raise ValueError("tag must be a non-empty Git reference name")
        resolved_commit = self._run(repository, "rev-parse", "--verify", f"{commit}^{{commit}}")
        if resolved_commit is None:
            raise ValueError(f"commit '{commit}' does not exist")
        self._run_required(repository, "tag", tag, resolved_commit)
        return GitSnapshot(
            repository=str(Path(repository).resolve()),
            commit=resolved_commit,
            tag=tag,
        )

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

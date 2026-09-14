"""Local Git adapter implementation for reproducible repository references."""

import subprocess
from pathlib import Path

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

    async def is_ancestor(self, repository: str, ancestor_commit: str, descendant_ref: str) -> bool:
        """Return whether ``ancestor_commit`` is an ancestor of ``descendant_ref``.

        Git's ``merge-base --is-ancestor`` uses exit status 1 for a valid negative
        answer, so the status must be handled separately from command failures.
        """
        returncode, stderr = self._run_status(
            repository,
            "merge-base",
            "--is-ancestor",
            ancestor_commit,
            descendant_ref,
        )
        if returncode == 0:
            return True
        if returncode == 1:
            return False
        detail = stderr.strip() or "unknown Git error"
        raise RuntimeError(f"Git ancestry check failed: {detail}")

    async def create_tag(self, repository: str, tag: str, commit: str) -> GitSnapshot:
        """Create an immutable lightweight tag, idempotently.

        Repeating the operation for the same tag and commit succeeds. An existing
        tag pointing elsewhere is never moved and is rejected explicitly.
        """
        if not tag or tag.startswith("-"):
            raise ValueError("tag must be a non-empty Git reference name")
        resolved_commit = self._run(repository, "rev-parse", "--verify", f"{commit}^{{commit}}")
        if resolved_commit is None:
            raise ValueError(f"commit '{commit}' does not exist")

        existing_commit = self._run(
            repository,
            "rev-parse",
            "--verify",
            f"refs/tags/{tag}^{{commit}}",
        )
        if existing_commit is not None:
            if existing_commit != resolved_commit:
                raise RuntimeError(f"Git tag '{tag}' already exists at a different commit")
            return GitSnapshot(
                repository=str(Path(repository).resolve()),
                commit=resolved_commit,
                tag=tag,
            )

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

    def _run_status(self, repository: str, *args: str) -> tuple[int, str]:
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
        return result.returncode, result.stderr

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

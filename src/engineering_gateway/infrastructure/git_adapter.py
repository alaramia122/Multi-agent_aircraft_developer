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

    def __init__(
        self, timeout_seconds: float = 30.0, repository_root: str | None = None
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds
        self._repository_root = Path(repository_root).resolve() if repository_root else None

    def _checked_repository(self, repository: str) -> str:
        resolved = Path(repository).resolve()
        if self._repository_root is not None and resolved != self._repository_root:
            raise ValueError("Git repository is outside the configured engineering artifact root")
        return str(resolved)

    async def get_snapshot(self, repository: str, ref: str = "HEAD") -> GitSnapshot:
        """Resolve a repository ref to a reproducible commit snapshot."""
        commit = self._run_required(
            repository, "rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"
        )
        tag = self._run(repository, "describe", "--exact-match", "--tags", commit)
        return GitSnapshot(repository=str(Path(repository).resolve()), commit=commit, tag=tag)

    async def is_ancestor(self, repository: str, ancestor_commit: str, descendant_ref: str) -> bool:
        """Return whether ``ancestor_commit`` is an ancestor of ``descendant_ref``.

        Git's ``merge-base --is-ancestor`` uses exit status 1 for a valid negative
        answer, so the status must be handled separately from command failures.
        """
        ancestor = self._run_required(
            repository,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{ancestor_commit}^{{commit}}",
        )
        descendant = self._run_required(
            repository,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"{descendant_ref}^{{commit}}",
        )
        returncode, stderr = self._run_status(
            repository, "merge-base", "--is-ancestor", ancestor, descendant
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
        tag pointing elsewhere is never moved and is rejected explicitly. A race
        between two creators is resolved by re-reading the tag after the create
        command fails.
        """
        self._validate_tag_name(repository, tag)
        resolved_commit = self._run(
            repository, "rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}"
        )
        if resolved_commit is None:
            raise ValueError(f"commit '{commit}' does not exist")

        existing_commit = self._run(
            repository,
            "rev-parse",
            "--verify",
            "--end-of-options",
            f"refs/tags/{tag}^{{commit}}",
        )
        if existing_commit is not None:
            return self._snapshot_for_existing_tag(repository, tag, resolved_commit, existing_commit)

        try:
            self._run_required(repository, "tag", tag, resolved_commit)
        except RuntimeError:
            # Another process may have published the same immutable tag between the
            # read above and the create. Re-read before surfacing the original error.
            raced_commit = self._run(
                repository,
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"refs/tags/{tag}^{{commit}}",
            )
            if raced_commit is not None:
                return self._snapshot_for_existing_tag(repository, tag, resolved_commit, raced_commit)
            raise

        return GitSnapshot(
            repository=str(Path(repository).resolve()),
            commit=resolved_commit,
            tag=tag,
        )

    def _snapshot_for_existing_tag(
        self, repository: str, tag: str, resolved_commit: str, existing_commit: str
    ) -> GitSnapshot:
        if existing_commit != resolved_commit:
            raise RuntimeError(f"Git tag '{tag}' already exists at a different commit")
        return GitSnapshot(
            repository=str(Path(repository).resolve()),
            commit=resolved_commit,
            tag=tag,
        )

    def _validate_tag_name(self, repository: str, tag: str) -> None:
        if not tag or tag.startswith("-"):
            raise ValueError("tag must be a non-empty Git reference name")
        try:
            self._run_required(repository, "check-ref-format", f"refs/tags/{tag}")
        except RuntimeError as exc:
            raise ValueError(f"invalid Git tag name: {tag}") from exc

    def _run(self, repository: str, *args: str) -> str | None:
        """Run an optional-result Git command.

        A non-zero Git exit status means the requested object/description is absent
        and is represented by ``None``. Process-level failures are different: a
        timeout or inability to start Git must not be mistaken for an absent ref,
        otherwise callers could take an unsafe create/race-recovery path.
        """
        try:
            result = subprocess.run(
                ["git", "-C", self._checked_repository(repository), *args],
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
            return None
        return result.stdout.strip()

    def _run_status(self, repository: str, *args: str) -> tuple[int, str]:
        try:
            result = subprocess.run(
                ["git", "-C", self._checked_repository(repository), *args],
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
                ["git", "-C", self._checked_repository(repository), *args],
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

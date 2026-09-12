"""StrictDoc adapter backed by the official StrictDoc CLI JSON export."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from engineering_gateway.domain.adapters import ExternalVersion
from engineering_gateway.domain.models import ElementKind, EngineeringElement


class StrictDocAdapterError(RuntimeError):
    """Raised when StrictDoc cannot export or the export is malformed."""


class LocalStrictDocAdapter:
    """Read requirements from a local StrictDoc project.

    SDoc parsing remains the responsibility of StrictDoc. The Gateway consumes the
    documented JSON export and maps only stable requirement identity into the
    canonical reference model.
    """

    system_name = "strictdoc"

    def __init__(self, project_path: str | Path, timeout_seconds: float = 60.0) -> None:
        self._project_path = Path(project_path)
        if not self._project_path.exists():
            raise ValueError(f"StrictDoc project does not exist: {self._project_path}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout_seconds = timeout_seconds

    async def get_element(self, external_id: str) -> EngineeringElement | None:
        if not external_id:
            raise ValueError("external_id must be non-empty")
        return await asyncio.to_thread(self._get_element, external_id)

    async def get_version(self) -> ExternalVersion:
        digest = await asyncio.to_thread(self._project_digest)
        return ExternalVersion(system=self.system_name, version=f"sha256:{digest}")

    def _get_element(self, external_id: str) -> EngineeringElement | None:
        for document in self._export_documents():
            found = self._find_requirement(document, external_id)
            if found is not None:
                return self._to_element(found)
        return None

    def _export_documents(self) -> list[dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="engineering-gateway-strictdoc-") as temp_dir:
            output_dir = Path(temp_dir)
            command = [
                "strictdoc",
                "export",
                str(self._project_path),
                "--formats=json",
                f"--output-dir={output_dir}",
            ]
            try:
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=self._timeout_seconds,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise StrictDocAdapterError("StrictDoc CLI could not be executed") from exc
            if result.returncode != 0:
                detail = result.stderr.strip() or result.stdout.strip() or "unknown StrictDoc error"
                raise StrictDocAdapterError(f"StrictDoc export failed: {detail}")

            index_path = output_dir / "json" / "index.json"
            if not index_path.is_file():
                raise StrictDocAdapterError(f"StrictDoc JSON export not found: {index_path}")
            try:
                payload = json.loads(index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise StrictDocAdapterError("StrictDoc JSON export is unreadable") from exc

        documents = payload.get("DOCUMENTS")
        if not isinstance(documents, list):
            raise StrictDocAdapterError("StrictDoc JSON export has no DOCUMENTS list")
        return [document for document in documents if isinstance(document, dict)]

    @staticmethod
    def _find_requirement(
        document: dict[str, Any], external_id: str
    ) -> dict[str, Any] | None:
        def visit(node: Any) -> dict[str, Any] | None:
            if not isinstance(node, dict):
                return None
            if node.get("_NODE_TYPE") == "REQUIREMENT" and node.get("UID") == external_id:
                return node
            children = node.get("NODES", [])
            if isinstance(children, list):
                for child in children:
                    found = visit(child)
                    if found is not None:
                        return found
            return None

        return visit(document)

    def _to_element(self, node: dict[str, Any]) -> EngineeringElement:
        uid = node.get("UID")
        if not isinstance(uid, str) or not uid:
            raise StrictDocAdapterError("StrictDoc requirement has no UID")
        title = node.get("TITLE") or uid
        if not isinstance(title, str):
            title = uid
        return EngineeringElement(
            kind=ElementKind.REQUIREMENT,
            type_id="strictdoc.requirement",
            name=title,
            external_system=self.system_name,
            external_id=uid,
            source_uri=f"strictdoc://{self._project_path.resolve()}#{uid}",
        )

    def _project_digest(self) -> str:
        digest = hashlib.sha256()
        files = sorted(self._project_path.rglob("*.sdoc"))
        if not files:
            raise StrictDocAdapterError(f"No .sdoc files found in {self._project_path}")
        for path in files:
            relative = path.relative_to(self._project_path).as_posix().encode()
            digest.update(relative)
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
        return digest.hexdigest()


__all__ = ["LocalStrictDocAdapter", "StrictDocAdapterError"]

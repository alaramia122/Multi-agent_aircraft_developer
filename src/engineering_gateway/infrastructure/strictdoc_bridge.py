"""Isolated StrictDoc workspace writer for bridge protocol v1.

Run with ``python -m engineering_gateway.infrastructure.strictdoc_bridge`` from a
small executable wrapper. Workspace and Git artifact roots are deployment inputs.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from engineering_gateway.infrastructure.immutable_artifact import read_git_artifact
from engineering_gateway.infrastructure.strictdoc_adapter import LocalStrictDocAdapter


def _digest(project: Path) -> str:
    return f"sha256:{LocalStrictDocAdapter(project)._project_digest()}"


def _export(project: Path) -> list[dict[str, Any]]:
    return LocalStrictDocAdapter(project)._export_documents()


def _requirements(documents: list[dict[str, Any]], uid: str) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("_NODE_TYPE") == "REQUIREMENT" and node.get("UID") == uid:
                found.append(node)
            for child in node.get("NODES", []):
                walk(child)

    for document in documents:
        walk(document)
    return found


def _all_requirements(documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("_NODE_TYPE") == "REQUIREMENT":
                found.append(node)
            for child in node.get("NODES", []):
                walk(child)

    for document in documents:
        walk(document)
    return found


def _json_file(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("invalid workspace manifest")
    return value


def _save_manifest(path: Path, manifest: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    os.replace(temporary, path)


def _workspace(root: Path, payload: dict[str, Any]) -> Path:
    workspace_id = str(UUID(payload["workspace_id"]))
    return root / workspace_id


def _verify_workspace(directory: Path, manifest: dict[str, Any], repository: Path) -> str:
    project = directory / "project"
    expected = manifest.get("elements")
    if not isinstance(expected, dict):
        raise ValueError("invalid workspace element manifest")
    actual = {path.name for path in project.glob("gateway-*.sdoc")}
    if actual != {f"gateway-{element_id}.sdoc" for element_id in expected}:
        raise ValueError("workspace files differ from the manifest")
    documents = _export(project)
    for element_id, record in expected.items():
        if not isinstance(record, dict):
            raise ValueError("invalid workspace element record")
        path = project / f"gateway-{element_id}.sdoc"
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("workspace artifact changed after publication")
        if read_git_artifact(record["source_uri"], repository, suffix=".sdoc") != path.read_bytes():
            raise ValueError("workspace artifact provenance does not match Git")
        matches = _requirements(documents, record["uid"])
        if len(matches) != 1 or matches[0].get("TITLE") != record["title"]:
            raise ValueError("published StrictDoc requirement cannot be read back")
    # Bind source identity and every exact Git artifact reference into the
    # durable version, as well as the saved SDoc content.
    encoded = json.dumps({"sdoc_version": _digest(project), "manifest": manifest},
                         sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def handle(request: dict[str, Any], *, root: Path, repository: Path) -> dict[str, Any]:
    """Perform one operation while holding a process-safe workspace lock."""
    if request.get("protocol") != 1 or not isinstance(request.get("payload"), dict):
        raise ValueError("unsupported bridge request")
    operation = request.get("operation")
    source = Path(request["project_path"]).resolve(strict=True)
    payload = request["payload"]
    if not source.is_dir() or not source.exists():
        raise ValueError("StrictDoc source project is missing")
    if operation == "get_version":
        return {"version": _digest(source)}
    if operation == "get_element":
        raise ValueError("get_element is provided by the official StrictDoc export adapter")
    if operation not in {"create_workspace", "apply_element", "apply_relation", "get_workspace_version"}:
        raise ValueError("unsupported bridge operation")

    directory = _workspace(root, payload)
    root.mkdir(parents=True, exist_ok=True)
    with (root / f"{directory.name}.lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        manifest_path = directory / "manifest.json"
        if operation == "create_workspace":
            version, change_hash = payload["source_version"], payload["change_set_hash"]
            if not re.fullmatch(r"[0-9a-f]{64}", change_hash):
                raise ValueError("invalid change-set hash")
            if manifest_path.exists():
                manifest = _json_file(manifest_path)
                if (manifest["source_version"], manifest["change_set_hash"]) != (version, change_hash):
                    raise ValueError("workspace already exists for a different source or change-set")
                _verify_workspace(directory, manifest, repository)
                return {}
            if _digest(source) != version:
                raise ValueError("StrictDoc source version is stale")
            if any(path.is_symlink() for path in source.rglob("*")):
                raise ValueError("source project contains symlinks")
            temporary = Path(tempfile.mkdtemp(prefix="strictdoc-workspace-", dir=root))
            try:
                shutil.copytree(source, temporary / "project")
                if _digest(temporary / "project") != version:
                    raise ValueError("StrictDoc source changed during workspace creation")
                _export(temporary / "project")
                _save_manifest(temporary / "manifest.json", {
                    "source_version": version, "change_set_hash": change_hash, "elements": {},
                })
                os.replace(temporary, directory)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
            return {}

        if not manifest_path.is_file():
            raise ValueError("workspace has not been created")
        manifest = _json_file(manifest_path)
        if operation == "get_workspace_version":
            return {"version": _verify_workspace(directory, manifest, repository)}
        if operation == "apply_relation":
            raise ValueError("native StrictDoc relation mapping is not configured; refusing publication")

        element = payload["element"]
        if element.get("external_system") != "strictdoc" or element.get("kind") != "requirement":
            raise ValueError("only StrictDoc requirements can be published")
        element_id = str(UUID(element["id"]))
        uid, title = element["external_id"], element["name"]
        content = read_git_artifact(element.get("source_uri"), repository, suffix=".sdoc")
        with tempfile.TemporaryDirectory(prefix="strictdoc-artifact-") as candidate_dir:
            (Path(candidate_dir) / "candidate.sdoc").write_bytes(content)
            requirements = _all_requirements(_export(Path(candidate_dir)))
            if (
                len(requirements) != 1 or requirements[0].get("UID") != uid
                or requirements[0].get("TITLE") != title
                or not isinstance(requirements[0].get("STATEMENT"), str)
                or not requirements[0]["STATEMENT"].strip()
            ):
                raise ValueError("Git artifact must contain one complete matching requirement")
        project = directory / "project"
        output = project / f"gateway-{element_id}.sdoc"
        record = {"uid": uid, "title": title, "sha256": hashlib.sha256(content).hexdigest(),
                  "source_uri": element["source_uri"]}
        prior = manifest["elements"].get(element_id)
        if prior is not None and prior != record:
            raise ValueError("element already published with different content or provenance")
        if output.exists() and output.read_bytes() != content:
            raise ValueError("workspace artifact conflicts with requested content")
        if not output.exists():
            output.write_bytes(content)
        try:
            matches = _requirements(_export(project), uid)
            if len(matches) != 1 or matches[0].get("TITLE") != title:
                raise ValueError("artifact must contain exactly the matching requirement UID and TITLE")
            manifest["elements"][element_id] = record
            _save_manifest(manifest_path, manifest)
            _verify_workspace(directory, manifest, repository)
        except Exception:
            if prior is None:
                manifest["elements"].pop(element_id, None)
                output.unlink(missing_ok=True)
            raise
        return {}


def main() -> None:
    operation = None
    try:
        request = json.load(sys.stdin)
        operation = request.get("operation")
        root = Path(os.environ["ENGINEERING_STRICTDOC_WORKSPACES_ROOT"]).resolve()
        repository = Path(os.environ["ENGINEERING_ARTIFACT_REPOSITORY"]).resolve(strict=True)
        response = handle(request, root=root, repository=repository)
        print(json.dumps({"protocol": 1, "operation": operation, "ok": True, **response}))
    except Exception as exc:
        print(json.dumps({"protocol": 1, "operation": operation, "ok": False,
                          "error": str(exc)}))


if __name__ == "__main__":
    main()

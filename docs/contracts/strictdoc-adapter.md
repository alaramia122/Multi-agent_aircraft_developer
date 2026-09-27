# StrictDoc adapter

The Gateway treats StrictDoc as an authoritative external requirements system. It does not implement an SDoc parser and does not copy the full StrictDoc data model into PostgreSQL.

## Integration boundary

`LocalStrictDocAdapter` uses the official `strictdoc export --formats=json` command and consumes the generated `json/index.json`. StrictDoc therefore remains responsible for SDoc parsing and validation.

The adapter maps only:

- StrictDoc `REQUIREMENT` nodes with a `UID` -> canonical `EngineeringElement`;
- `UID` -> `external_id`;
- `TITLE` -> canonical `name` (falling back to UID);
- `strictdoc.requirement` -> canonical `type_id`;
- local project path + UID -> `source_uri`.

Requirement text, rationale, status, custom fields and full relations remain authoritative in StrictDoc and are not duplicated by the canonical model.

## Version

`get_version()` returns a deterministic SHA-256 digest of all `.sdoc` files in the project tree. This is a content version, not a substitute for Git history or a Gateway baseline.

## Runtime prerequisite

The host running the adapter must have a compatible StrictDoc installation and its `strictdoc` executable available on `PATH`. The adapter intentionally does not embed or reimplement the StrictDoc parser.

## Native workspace writer (isolated implementation)

`engineering_gateway.infrastructure.strictdoc_bridge` implements protocol v1
for requirement elements. Set `STRICTDOC__WORKSPACE_MUTATIONS_ENABLED=true`,
`STRICTDOC__WORKSPACE_BRIDGE_EXECUTABLE` to the executable
`scripts/strictdoc-workspace-bridge`, and provide:

- `ENGINEERING_STRICTDOC_WORKSPACES_ROOT`: writable directory for isolated copies;
- `ENGINEERING_ARTIFACT_REPOSITORY`: local Git repository containing source artifacts.

The source StrictDoc project may be read-only. Its `.sdoc` digest must equal the
source baseline version passed to `create_workspace`. An element's `source_uri`
must point to a complete, content-bearing SDoc document in an exact Git commit:

```text
git-artifact://<40-character-commit>/engineering/requirements/REQ-1.sdoc#sha256=<64-character-digest>
```

The bridge copies the committed bytes verbatim and verifies that official
`strictdoc export --formats=json` reads exactly one requirement with the
element's UID, title, and nonempty statement. It does not compose a statement from the canonical
name. Repeated calls with the same workspace and change-set read back the
saved files; changed content, source versions and hashes fail closed. The
workspace version is a SHA-256 digest over its persisted `.sdoc` version and
manifest, including the exact Git commit and artifact hashes. Each readback
also compares the saved bytes with the referenced Git object.

Native `apply_relation` is deliberately rejected until the mapping of Gateway
relations to StrictDoc's document grammar is defined and tested. This writer is
not yet wired into staging and does not establish complete MVP traceability.

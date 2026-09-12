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

## Scope of this stage

This adapter is read-only. Workspace mutation and controlled write-back belong to the later L2 workspace integration and must remain behind Gateway authorization, change-control and audit gates.

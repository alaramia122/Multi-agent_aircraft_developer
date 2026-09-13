# Testing strategy

## Unit

Pure domain rules and deterministic validation are tested without databases or external systems.

## Deterministic Validation Engine

Validation is a pure deterministic operation over a canonical graph, a versioned Standard Profile, and explicitly supplied authoritative evidence. The engine must not infer governance facts from LLM output or hidden element metadata.

The validation suite covers:

- element type existence and `ElementKind` consistency;
- duplicate Gateway identity and duplicate external identity;
- dangling relations and duplicate relations;
- profile-defined relation endpoint constraints;
- required and forbidden traceability rules;
- required verification relations;
- profile-defined attributes: requiredness, unknown attributes and scalar types;
- lifecycle state membership;
- lifecycle transition legality when an explicit transition is supplied;
- required artifact presence from explicit adapter evidence;
- stable validation ordering;
- stable SHA-256 validation fingerprint across equivalent input ordering.

Lifecycle and artifact checks use explicit evidence inputs. The canonical element remains a reference/identity model and is not expanded into a duplicate of an external engineering system.

## Contract

Port behavior is tested against fake/in-memory implementations and shared fixtures. These tests protect the boundary between the Gateway and adapters.

## Integration

Adapter tests run against controlled StrictDoc, Capella, OpenProject and Git environments where available. No production credentials are used in CI.

## End-to-end

The vertical slices must demonstrate:

- requirement -> architecture traceability;
- Change Request -> controlled modification;
- deterministic traceability-gap detection;
- human-only approval;
- approved-baseline immutability;
- baseline reproducibility from Git commit/tag;
- complete audit trail.

## Required negative tests

Security/governance tests must prove that an AI identity cannot execute approval and that approved objects cannot be modified outside a new change context.

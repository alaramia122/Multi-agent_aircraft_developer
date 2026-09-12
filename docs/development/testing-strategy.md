# Testing strategy

## Unit

Pure domain rules and deterministic validation are tested without databases or external systems.

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

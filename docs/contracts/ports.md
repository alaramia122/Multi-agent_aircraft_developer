# Infrastructure port contract

The Gateway uses ports to isolate the domain/application layers from external technologies.

## Required adapter families

- `StrictDocAdapter`: read requirements and requirement traceability from the authoritative StrictDoc project. Controlled publication/write-back and ReqIF exchange are separate L2 capabilities and are not part of the current local adapter contract.
- `CapellaAdapter`: system/function/component/interface/allocation references and workspace-scoped element/relation publication through a versioned headless bridge.
- `OpenProjectAdapter`: Change Request work packages and their workflow status at the OpenProject API boundary.
- `GitAdapter`: branches/refs, commits, tags and baseline evidence.

## Cross-cutting ports

- canonical element/reference repository;
- profile repository;
- validation result repository;
- baseline registry;
- audit sink;
- object storage;
- identity/authorization provider.

## Contract requirements

Ports must:

1. use stable typed request/response models;
2. expose domain/application semantics, not vendor wire formats;
3. distinguish not-found, conflict, authorization and external-service failures;
4. support correlation IDs for auditability;
5. never provide an approval operation to an AI identity.

## External adapter implementation boundary

The current Gateway milestone requires the adapter boundaries to be executable and testable, but does not claim that production external systems are installed in the repository's CI environment.

The concrete adapter scope is therefore explicit:

- StrictDoc is a read adapter over the official CLI JSON export;
- Capella is a read/workspace adapter over the versioned JSON bridge protocol;
- OpenProject is a read/change-request adapter over API v3 with optimistic locking and idempotent creation support;
- Git is a local CLI adapter for reproducible baseline evidence.

Future mutation capabilities that require a different external protocol or stronger deployment assumptions must be added as explicit versioned contracts rather than silently broadening an existing adapter.

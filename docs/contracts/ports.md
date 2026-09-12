# Infrastructure port contract

The Gateway uses ports to isolate the domain/application layers from external technologies.

## Required adapter families

- `StrictDocAdapter`: requirements, relations, publication and ReqIF-oriented exchange.
- `CapellaAdapter`: system/function/component/interface/allocation references.
- `OpenProjectAdapter`: Change Request, Problem Report, Review/Task and workflow state.
- `GitAdapter`: branches, commits, tags and baseline evidence.

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

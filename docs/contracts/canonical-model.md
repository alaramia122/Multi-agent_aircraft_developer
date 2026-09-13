# Canonical Engineering Model Contract

## Purpose

The Gateway canonical model provides stable identity and cross-system traceability. It is
not a replacement for StrictDoc, Capella, OpenProject or Git and must not become a copy
of their engineering models.

## Element

`EngineeringElement` contains:

- Gateway UUID;
- profile-defined broad kind;
- profile-defined `type_id`;
- human-readable name;
- authoritative external system identifier;
- external object identifier;
- optional source URI.

## Relation

`EngineeringRelation` is a directed edge with:

- source element UUID;
- typed `RelationType`;
- target element UUID.

Relations are first-class Gateway graph data because traceability and deterministic
validation operate on them.

## Traceability Graph

`TraceabilityGraph` is a read/query layer over canonical elements and relations. It does
not own or duplicate engineering content. It provides:

- directional outgoing/incoming edge queries;
- directed reachability and ancestor queries;
- deterministic evaluation of profile traceability rules;
- structured traceability-gap diagnostics.

The graph exposes six deterministic gap categories:

1. `missing_required` — a required edge has no valid match;
2. `forbidden_present` — an edge explicitly forbidden by a profile is present;
3. `wrong_relation_type` — the expected target type is connected using another relation;
4. `wrong_target_type` — the expected relation reaches an incompatible target type;
5. `dangling_source` — an edge source is absent from the canonical graph;
6. `dangling_target` — an edge target is absent from the canonical graph.

A traceability rule is satisfied only by an edge matching all three dimensions: source
profile type, relation type and target profile type. Traversal is directional and ignores
non-canonical dangling endpoints rather than fabricating external elements.

## Persistence boundary

PostgreSQL stores Gateway references, graph relations and later Gateway governance data.
The schema must not store a second authoritative copy of the engineering content held by
external systems.

## Invariants

1. External identity is unique by `(external_system, external_id)`.
2. A relation may reference only existing canonical elements.
3. Duplicate identical edges are rejected by the database uniqueness constraint.
4. Source systems remain authoritative for their own object content.
5. Profile-specific semantics belong to the Standard Profile Engine, not to this model.
6. Traceability diagnostics are deterministic and do not depend on LLM output.

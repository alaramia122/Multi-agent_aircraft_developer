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

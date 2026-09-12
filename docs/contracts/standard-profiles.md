# Standard Profile Contract

## Purpose

A Standard Profile is a declarative description of engineering semantics and governance rules consumed by the Engineering Gateway. It is configuration, not executable compliance logic.

The Gateway core must not contain standard-specific branches such as `if arp4754a` or `if do178c`. A profile can be replaced or composed without modifying the core domain services.

## Definition categories

- `element_types` — semantic element types and their attributes.
- `relations` — allowed directed relation endpoints and relation type.
- `lifecycles` — states and allowed state transitions.
- `artifacts` — artifacts required for an element type.
- `traceability` — required or optional traceability edges.
- `verification` — declarative verification constraints.
- `metadata` — non-governance descriptive metadata.

## Composition

Profiles are composed by stable definition identifiers. A definition may be contributed by more than one profile only when the complete definitions are identical. Conflicting definitions are rejected deterministically; no implicit override order exists.

Composition therefore supports combinations such as an engineering-process profile plus a software-assurance profile without embedding either standard into Gateway code.

The composition result records the exact `profile_id@version` identities of its source profiles in `metadata.composed_from`. The source versions, rather than only profile IDs, are part of the reproducibility boundary.

## Validation boundary

Pydantic models provide structural validation. `StandardProfileEngine` performs semantic validation, including:

- references to known element types;
- relation endpoint consistency;
- lifecycle element-type uniqueness and transition consistency;
- artifact references;
- consistency between traceability rules and relation definitions;
- consistency between verification rules and verification relation definitions;
- uniqueness of all definition identifiers.

The profile engine does not decide whether an actual project complies with a profile. That belongs to the deterministic Validation Engine, which evaluates canonical project state against an activated profile.

## Activation

Registration and activation are separate operations. A profile must first be registered as an immutable `(id, version)` definition. Activation runs semantic validation again and records that the exact version is eligible for project validation.

Multiple profile versions may coexist and may be active simultaneously. A workspace stores the exact profile ID and version used for its approval preparation, so later activation/deactivation cannot silently change an existing workflow.

## Example

`profiles/examples/verification-baseline.json` is intentionally illustrative and is **not** a normative interpretation of ARP4754A, DO-178C, ARP4761, or any other standard.

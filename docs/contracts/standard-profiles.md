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

## Validation boundary

Pydantic models provide structural validation. `StandardProfileEngine` performs semantic validation, including references to known element types and consistency between traceability rules and relation definitions.

The profile engine does not decide whether an actual project complies with a profile. That belongs to the later deterministic Validation Engine, which evaluates canonical project state against an activated profile.

## Example

`profiles/examples/verification-baseline.json` is intentionally illustrative and is **not** a normative interpretation of ARP4754A, DO-178C, ARP4761, or any other standard.

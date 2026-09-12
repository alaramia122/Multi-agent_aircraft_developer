# Traceability and Validation Contract

## Traceability graph

The Gateway maintains a directed graph of canonical element identities and typed relations. It stores only the references required for cross-system navigation and governance; authoritative engineering content remains in the external system.

A required traceability rule means every matching source element must have at least one edge with the declared relation type to the declared target type. A non-required traceability rule is interpreted as a forbidden edge and is reported when such an edge exists.

## Deterministic validation

`DeterministicValidationEngine` evaluates canonical state against an activated Standard Profile without an LLM. At minimum it detects:

- unknown element types;
- dangling relation endpoints;
- relations forbidden by the profile;
- missing required traceability;
- forbidden traceability rules violated by existing edges.

Validation findings are deterministic and machine-readable. LLM agents may analyze or propose remediation, but they are not the source of compliance truth.

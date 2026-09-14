# Infrastructure acceptance and verification matrix

| Acceptance invariant | Verification | Current implementation evidence |
|---|---|---|
| Standard Profiles can be activated | Unit tests for profile registry/activation | `tests/unit/test_standard_profile_activation.py` |
| Requirement can be represented through StrictDoc | ARP4754A and DO-178C integration slices use StrictDoc external identities | `tests/integration/test_arp4754a_governed_workflow.py`, `tests/integration/test_do_178c_vertical_slice.py` |
| Requirement can be mapped to Capella | Governed reconciliation asserts target-system routing for allocation | ARP4754A integration slice |
| Change Request is controlled through OpenProject | Adapter tests and governed workspace flow bind Change Request to workspace | `tests/unit/test_openproject_adapter.py`, `tests/unit/test_gateway_service.py` |
| Cross-tool graph is represented | Canonical elements/relations retain external-system identities and relation types | domain model + integration slices |
| At least five traceability gap types are available | Explicit tests cover all six diagnostic categories | `tests/unit/test_traceability_gap_types.py` |
| AI identity cannot APPROVE | Unit tests reject AI L3 attempts and audit denial | `tests/unit/test_gateway_service.py` |
| Approved baseline cannot be directly modified | Workspace state and baseline lifecycle tests enforce controlled flow | `tests/unit/test_gateway_service.py`, baseline tests |
| Baseline is reproducible from Git commit/tag | Git snapshot/ancestry/tag tests plus baseline registry | `tests/unit/test_git_adapter.py`, `tests/unit/test_baselines.py` |
| State-changing and denied actions are auditable | Gateway tests verify audit records; independent audit session protects failure/denial evidence | `tests/unit/test_gateway_service.py`, audit infrastructure |
| Profile can be replaced without Gateway-core branching | Profile engine consumes declarative `StandardProfile`; ARP4754A and DO-178C are external profile data | `application/profile_engine.py`, `profiles/*/profile.json` |
| DO-178C lifecycle traceability is executable | Profile defines HLR/LLR/verification lifecycles and traceability; integration test executes governed slice | `profiles/do-178c/1.0/profile.json`, `tests/integration/test_do_178c_vertical_slice.py` |
| Vector Store is not authoritative | Gateway persistence model stores metadata/references; canonical model is authoritative only as a reference graph, external systems remain authoritative | architecture documentation |

## CI quality gate

The repository CI executes:

1. project installation;
2. Ruff linting;
3. mypy type checking;
4. pytest.

The latest completed CI run for commit `70c7434af06e9299f6d78defed8a05764b86898e` passed all four stages. Subsequent commits are expected to be verified by their own workflow runs before the branch is considered green.

## Test interpretation

A passing unit test demonstrates the Gateway contract implemented by the test double or deterministic component. Integration tests additionally verify composition across the Gateway and adapter boundaries. They do not claim that external tools are available in CI unless an actual external-tool environment is configured.

## Remaining integration hardening

The infrastructure is ready for the next phase, but production deployment still requires concrete bridge executables/configuration for StrictDoc and Capella and real service credentials/endpoints for OpenProject. These are deployment concerns, not substitutes for deterministic Gateway validation.

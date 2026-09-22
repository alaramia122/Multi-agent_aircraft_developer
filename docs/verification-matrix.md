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
| Complete MVP-1 chain is executable | Versioned ARP4754A profile covers aircraft/system functions, requirements, architecture allocation, safety, verification and evidence | `profiles/arp4754a/2.0/profile.json`, `tests/integration/test_complete_mvp_profiles.py` |
| Complete MVP-2 chain is executable | Versioned DO-178C profile covers system input, HLR, software architecture, LLR, source, executable, verification result and evidence | `profiles/do-178c/2.0/profile.json`, `tests/integration/test_complete_mvp_profiles.py` |
| MCP can supply complete deterministic validation evidence | MCP tests prove attributes, artifacts, lifecycle states and transitions reach validation and approval preparation | `tests/unit/test_mcp_server.py` |
| Vector Store is not authoritative | Gateway persistence model stores metadata/references; external systems remain authoritative | architecture documentation |

## CI quality gate

The repository CI executes:

1. project installation;
2. Ruff linting;
3. mypy type checking;
4. pytest.

The latest completed verification run on `main` before the complete-profile change is run `35732060251` for commit `14449b96091470c1398ce1685200d30cefc71abb`. Both `quality` and `staging` succeeded. The complete-profile change is accepted only after its own PR and post-merge CI succeed.

- Ruff: passed;
- mypy: passed;
- pytest, including PostgreSQL integration: passed;
- staging smoke job: passed.

## Test interpretation

A passing unit test demonstrates the Gateway contract implemented by the test double or deterministic component. Integration tests additionally verify composition across the Gateway and adapter boundaries. They do not claim that external tools are available in CI unless an actual external-tool environment is configured.

The verified suite includes the previously deferred reconciliation replay-idempotency test. Replaying the same workspace change-set does not invoke the external reconciler twice and is recorded as an idempotent success.

## Remaining deployment concerns

The infrastructure contract is complete for the pre-AI-Studio phase. Production deployment still requires concrete bridge executables/configuration for StrictDoc and Capella, real OpenProject endpoints/credentials, database migration execution, and deployment-level identity provisioning for the MCP endpoint. These are deployment/integration concerns rather than missing deterministic Gateway logic.

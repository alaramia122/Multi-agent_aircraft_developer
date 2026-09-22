# Project completion assessment and plan - 2026-09-22

## Purpose and evidence baseline

This document compares the repository with the v0.2 technical specification for the multi-agent aircraft developer. It distinguishes implemented source contracts from deployed external systems and from the future Yandex AI Studio layer.

Evidence used for the assessment:

- technical specification v0.2, sections 1-27 and acceptance criteria;
- repository `main` at `cc377edc90ea27317212a56fce60caf6ac3d4617`;
- merged Production Identity PR #7;
- CI run `35731205869`: `quality` and `staging` succeeded;
- 52 Python source files (about 6.8k lines) and 64 Python test files (about 8.4k lines);
- executable ARP4754A and DO-178C vertical-slice profiles;
- source-level inspection of domain, application, persistence, adapters, MCP, configuration, migrations and deployment documentation.

The percentages below are engineering maturity estimates, not test-coverage metrics.

## Executive assessment

| Scope | Estimated maturity | Assessment |
|---|---:|---|
| Engineering Gateway core contract | 85-90% | The canonical model, profiles engine, deterministic validation, governance, persistence, reconciliation, adapters and MCP boundary are implemented and extensively tested. |
| Repository-level MVP-0 infrastructure | 70-75% | Gateway and adapter boundaries exist, but production identity and external tools are not deployed together. Object Storage has configuration/readiness only. |
| Full system described by the technical specification | 45-50% | The entire AI Studio layer, RAG, Cost/Budget and real cross-system E2E are absent. Existing standard profiles are deliberately minimal slices, not full lifecycle profiles. |
| Production deployability | 30-40% | Core container/CI/readiness exists. Real IdP, StrictDoc, Capella bridge, OpenProject, object storage, monitoring, backup and operational evidence are not configured or proven. |

The repository is therefore a strong Gateway foundation, but it is not yet the completed multi-agent system from the technical specification. Statements that the complete project is finished would be incorrect.

## Compliance map

| Technical-specification area | Verified implementation | Remaining gap | Status |
|---|---|---|---|
| Canonical Engineering Element/Relation/Graph | Domain model, persistence and graph validation | None for the current Gateway boundary | Complete |
| Standard Profile Engine | Registration, activation, composition, conflict rejection and provenance | Profiles cover only minimal vertical slices | Partial |
| Deterministic validation | 16 stable finding classes, deterministic order and SHA-256 graph fingerprint | Full standard-specific rule content still depends on richer profiles | Substantially complete |
| Governance and approval | L0-L3, human-only L3, immutable baseline, workspace/change-set | Independent-review record/gate is not a separate implemented subsystem | Partial |
| Audit | Durable audit and failure/denial evidence | Production retention/export/monitoring policy is not deployed | Partial |
| Git | Snapshot, ancestry and immutable tags | Production credentials and repository policy are not proven | Adapter complete; deployment pending |
| StrictDoc | CLI JSON read and controlled workspace bridge | Real installation, publication and ReqIF exchange E2E are not proven | Partial |
| Capella | Versioned JSON bridge client and contract tests | No production headless bridge executable/deployment | Partial |
| OpenProject | API v3, HATEOAS, lockVersion and idempotency | No real instance/workflow E2E | Partial |
| MCP | Streamable HTTP, operation-scoped authorization, no L3 tools | AI Studio consumer is not configured | Gateway complete; integration pending |
| Identity | Trusted-claims mapping, request-scoped Actor, readiness contract | Upstream authentication/IdP is not part of the repository deployment | Gateway complete; deployment pending |
| ARP4754A MVP-1 | Governed and validation test slices | Profile omits aircraft/system functions, allocation detail and safety chain; no real external-system E2E | Partial |
| DO-178C MVP-2 | Governed and validation test slices | Profile omits system-requirement input, executable and evidence chain; no real external-system E2E | Partial |
| Object Storage | Typed configuration and readiness probe | No artifact storage adapter, lifecycle policy or evidence-package flow | Missing implementation |
| Vector Store / RAG | Architectural non-Source-of-Truth rule only | Retrieval contracts, provenance and deployment are absent | Missing |
| AI agents | Gateway prevents AI approval | Agent definitions, prompts, structured contracts and deployment are absent | Missing |
| AI Studio workflows | None | Orchestration, retries, review/human-decision path and deployment are absent | Missing |
| Cost/Budget | Canonical model can represent a generic cost item only conceptually | Deterministic budget model/gate and Cost Agent are absent | Missing |
| Operations | Health/readiness, Docker and CI | Metrics/logging, backup/restore, secret rotation and runbooks are incomplete | Partial |

## Important mismatches and corrections

1. The README previously mentioned Alembic, while the approved architecture uses ordered SQL migrations. The README is corrected in the lifecycle-verification change.
2. The existing ARP4754A and DO-178C profiles describe themselves accurately as vertical slices. They do not yet implement every node in the MVP-1 and MVP-2 chains from the technical specification.
3. Adapter contract tests demonstrate protocol behavior, not availability of real StrictDoc, Capella or OpenProject deployments.
4. Object Storage readiness proves only endpoint reachability. It does not prove upload, immutable addressing, integrity verification or retention.
5. A successful Gateway CI run does not prove the full Yandex AI Studio system.

## Completion plan

### Phase 0 - Production Identity closure

Result: completed in PR #7 and verified on `main` by CI run `35731205869`.

Exit criteria:

- upstream readiness URL is mandatory when identity is enabled;
- request-scoped Actor mapping remains fail-closed;
- `quality` and `staging` succeed on the merge commit.

### Phase 1 - HTTP/ASGI and MCP lifecycle closure

Work:

- exercise the actual identity-enabled composition root;
- prove wrapped MCP startup/shutdown is preserved;
- prove database and route cleanup when MCP startup fails;
- synchronize identity and migration documentation.

Exit criteria: focused lifecycle tests, full unit suite, Ruff, mypy and CI succeed.

### Phase 2 - Standard-profile and acceptance-chain completion

Work:

- expand ARP4754A profile to the complete MVP-1 chain, including safety and allocation;
- expand DO-178C profile to the complete MVP-2 chain, including system input, executable and evidence;
- preserve composition and deterministic validation;
- add positive and negative vertical-slice tests that demonstrate at least five traceability-gap classes.

Exit criteria: both complete chains validate; intentional gaps produce stable findings; no Gateway core branching by standard.

### Phase 3 - Missing deterministic infrastructure

Work:

- add an S3-compatible Object Storage port/adapter with content integrity and immutable evidence references;
- add deterministic Cost/Budget models and a budget gate, without placing cost reasoning in the LLM;
- add an explicit independent-review evidence contract if approval requires it;
- add SQL migration(s) only when persistence contracts change.

Exit criteria: contracts, persistence, tests, configuration and documentation agree; approved baseline behavior remains immutable.

### Phase 4 - Real external staging and Gateway E2E

Deployment order:

1. upstream IdP/authentication proxy;
2. Git repository and policy;
3. StrictDoc installation and controlled write/publication path;
4. Capella headless bridge executable;
5. OpenProject project/workflow;
6. S3-compatible Object Storage.

Exit criteria:

- one MVP-1 and one MVP-2 change traverse the real systems;
- retry, partial publication and concurrency behavior are demonstrated;
- the resulting baseline is reproducible from Git and stored external versions;
- evidence and logs are retained.

This phase requires deployment endpoints, credentials and a usable Capella bridge environment. Repository-only CI cannot honestly substitute for it.

### Phase 5 - AI Studio contracts, agents and orchestration

Work:

- freeze structured input/output contracts for Chief Engineer, Requirements, System Architect, Safety, Software Architect, Verification, Configuration, Independent Reviewer and Cost agents;
- ensure all engineering mutations use Gateway MCP tools;
- implement the human-decision workflow and prevent L3 exposure;
- add deterministic retry/idempotency rules and provenance propagation;
- deploy Yandex AI Studio agents/workflows.

Exit criteria: agent outputs are typed proposals, no agent can approve, and MVP-1/MVP-2 execute through the Gateway with a human decision.

### Phase 6 - RAG and production operations

Work:

- add retrieval-source identity, version, citation and `SOURCE_UNVERIFIED` state;
- keep vector search non-authoritative;
- add metrics/logging, backup/restore, retention, secret rotation and incident runbooks;
- perform final threat, failure-mode and acceptance review.

Exit criteria: full-system E2E, operational evidence and the technical-specification acceptance matrix are green.

## Delivery sequence and branch policy

Use one reviewable PR per phase or independently deployable contract. Every PR must include the relevant tests and documentation. Do not combine production deployment claims with repository-only test evidence.

The next repository change is Phase 1. Phase 4 becomes a hard external dependency: it cannot be marked complete without actual service endpoints and credentials. Phase 5 additionally requires Yandex AI Studio project access and its current deployment format/API.

## Progress after the baseline assessment

- Phase 1 was completed and merged: identity-enabled ASGI composition, wrapped MCP lifecycle and startup-failure cleanup are now covered by CI.
- Phase 2 adds `arp4754a@2.0` and `do-178c@2.0` complete acceptance chains while preserving the 1.0 vertical slices.
- MCP validation and approval preparation now accept typed attributes, artifact evidence, lifecycle states and lifecycle transitions, so the declarative profile contract is usable by future agents rather than only by direct Python calls.

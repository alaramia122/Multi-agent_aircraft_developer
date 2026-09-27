# Project genesis and acceptance without a pre-existing UAV model

The system is intended to help design a new UAV. A user-supplied Capella UAV
model is **not** a prerequisite for completion or initial deployment. The bridge needs a valid `.aird` entrypoint. Staging now supplies a verified
empty Capella v7.0.1 starter and enables the adapter against that read-only
source. General project creation and per-project starter provenance are still
product work, not a missing model deliverable from the user.

## Required project initialization

1. Start a new project with a selected versioned Standard Profile and
   repository. Record actor, timestamp, project identifier, profile version,
   change request and audit event. No architecture content is fabricated.
2. Create an empty, valid Capella project with Capella's supported project
   creation facilities or a reviewed, versioned clean starter template. Keep
   the starter template separate from the official sample model used in the
   runtime probe. Record template/runtime versions, source project digest,
   entrypoint and Git provenance; preserve an immutable initial state.
3. Initialize StrictDoc and Git for the project with explicit source content
   and provenance. A name or UUID alone cannot become a requirement statement
   or component description.
4. Let L1 propose the first content-bearing requirements and architecture
   elements. L2 writes only to isolated workspaces. Read back the saved files,
   compare source and workspace versions, replay without duplication, and
   reject stale or tampered inputs. Link typed references only where both
   endpoints and native relation mappings are supported; otherwise fail closed.
5. Apply deterministic validation, reconciliation and independent review.
   Human L3 remains a separate personal decision based on current evidence.

## Verification phases

| Phase | Acceptance evidence |
| --- | --- |
| Before operational use | CI plus staging creation from *no pre-existing UAV model*; versioned clean project, representative content fixtures, real StrictDoc/Capella write/readback/replay and failure cases; public human login/role boundary and MCP access tests. The official Capella sample proves the bridge mechanism only. |
| During first engineering project | Real UAV functions, requirements, architecture and software items are created through this system. Run MVP-1 and MVP-2 against those actual project inputs with traceability, safety, verification, evidence, change control and human review. Record exact versions and any unresolved gaps; no automatic baseline approval. |
| Later governed baselines | Human authorizes L3 after inspecting an independent review package and current validation/reconciliation evidence. Operational monitoring and regression checks continue after release. |

The pre-operational acceptance does not need a user-designed UAV model. It
*does* need project genesis and representative integration tests, because a
successful sample write alone cannot show that a newly created project works.
No certification or tool qualification claim follows from these checks.

## Staging evidence (27 September 2026 UTC)

The [clean starter bridge run](https://github.com/alaramia122/engineering-staging-deploy/actions/runs/36358724467)
created the empty logical component package from hash-pinned official fixture
files, independently read the model, wrote a committed diagnostic JSON logical
component in an isolated workspace, repeated it without duplication, and
rejected an untracked edit. Source digest was
`sha256:c21e6f10c800ad72bd4ba62e2c4eab5df02f59e66e2375574e9e8d39d8122b6b`.
The [Gateway adapter activation run](https://github.com/alaramia122/engineering-staging-deploy/actions/runs/36359953243)
provisioned the clean starter as a read-only source, enabled the private HMAC
bridge, resolved a diagnostic content artifact from an exact temporary Git
commit, and confirmed native write, independent version readback and stable
replay. The recorded disposable workspace version was
`sha256:c3524c01565a76dd3b8410007d0cef8260a3ea123ec289f8f09df4c2885b6d46`.
The initial adapter attempts failed and rolled back; PRs #20, #24 and #26 in
the staging repository addressed the stable Eclipse configuration path, volume
copy image, writable home and native output verification. The full redeploy
acceptance remains separately tracked. Native relation mapping and canonical
Capella `get_element` still fail closed; this is a logical component diagnostic,
not completion of either domain MVP or a baseline.

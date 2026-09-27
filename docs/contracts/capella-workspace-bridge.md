# Capella workspace bridge (candidate)

The Gateway subprocess adapter speaks bridge protocol v1 to a private Capella
service. The current implementation is gated by `CAPELLA_ENABLED=false` because
it requires an existing `.aird` source project in the
`engineering-capella-projects` volume. This is a bootstrap gap in the software,
not an input required from the UAV designer. Before enabling Capella for a new
project, implement a controlled project-creation path that produces a clean
Capella starter project, registers its source digest and tests the native
write/readback path. See `docs/development/project-genesis-acceptance.md`.

Only `architecture` elements with `type_id=capella.logical_component` are mapped.
Their `source_uri` must resolve to an immutable
`git-artifact://<40-hex-commit>/engineering/<path>.json#sha256=<64-hex>` in the
operator configured artifact repository. The JSON schema is
`capella.logical_component.v1`, with nonempty `name` and `description`; its name
must match the canonical element. The name and UUID are never used to invent
the description. The native service checks the content digest again and saves
the logical component with Python4Capella.
The private HTTP request is signed with a dedicated HMAC-SHA256 secret shared
only by Gateway and Capella. Both refuse mutations without a provisioned secret.

Each UUID workspace copies the configured source project, binds its original
file digest and change-set hash in a manifest, and verifies the persisted model
with a separate native read. Workspace version includes the model file digest
and manifest with source identity and artifact URI. A replay with the same
element and artifact is read-only. External model edits cause a closed failure.
Native relations and other Capella element types are refused until a precise
mapping is implemented. Source model files are mounted read-only in both
containers. The bridge is not an L3 decision or baseline operation.

The unit tests exercise the protocol and failure modes with a fake native
process. Earlier VM evidence only proves a separate write on the official
sample model. This candidate proves a native write on an isolated sample. The UAV model is
expected to be created during use of this system; operational engineering
acceptance will therefore follow project initialization, not precede it.

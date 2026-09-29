# Starting a project without an existing UAV model

The human portal at `/human/` accepts a project name, goal and optional initial
constraints after interactive Keycloak login. The user needs `gateway-propose`
or a stronger human role. `POST /human/projects` persists the exact normalized
human input under that user's subject ID. `GET /human/projects` lists only that
author's drafts; `GET /human/projects/{id}` has the same scope.

Each draft has version 1, UTC creation time and a SHA-256 digest of the canonical
JSON object containing name, goal and constraints. The initial record is
immutable. It has `state=draft`, `source=human_input` and `baseline_id=null`.
Creating a draft does not claim that a system requirement, Capella component,
StrictDoc document, Change Request or approved baseline exists. The portal
explicitly reports that no agent execution is started. A future orchestration
step must consume this versioned source and attach proposed engineering artifacts
and review evidence with traceable origins.

The owner can select **Discuss with Alice** on a saved draft. The chat sends
the selected draft's original goal, constraints, author, version and source
hash to the conversational model with explicit opt-in from the send button.
The dialogue is owner-scoped in PostgreSQL and restored after login. Alice can
assemble a bounded JSON start form from the draft and recent dialogue, or ask
for essential missing details. The portal shows the proposed Change Request
title and description, draft hash, pinned Git commit and StrictDoc/Capella/
OpenProject versions. The owner may edit the text and must explicitly confirm.
Only a human L2 token can then create the OpenProject Change Request and first
workspace. Alice cannot send this write request or decide L3. No typed
engineering artifacts or role-agent execution result from this action.

`GATEWAY__INITIAL_PROJECT_REPOSITORY` must point to the dedicated, initialized
engineering artifact Git repository. StrictDoc and Capella must expose clean,
readable source projects; OpenProject must be configured. The action pins
these source versions and isolates later changes in a new workspace. It does
not provision the sources or assert that any UAV model has been reviewed.

Deploy migrations through 0017 before the new application image; readiness requires
schema version 17. Older conversations were browser-only and cannot be restored
from the server. Test with an interactive human `gateway-propose` token, not a
service credential. No personal L3 decision is needed to create a draft.

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

Deploy migration 0015 before the new application image; readiness requires
schema version 15. Test with an interactive human `gateway-propose` token, not a
service credential. No personal L3 decision is needed to create a draft.

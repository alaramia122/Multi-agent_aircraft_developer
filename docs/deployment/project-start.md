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
The dialogue is now owner-scoped in PostgreSQL and restored after login. Alice
is instructed to summarize when enough information has been provided and to
identify the next action. This still does not create typed engineering
artifacts or run the role agents. The next implementation phase is project
genesis (profile, repository, empty StrictDoc/Capella sources and Change Request)
and an AI Studio Workflow which consumes that exact source version before L1
proposals enter the governed Gateway.

Deploy migrations 0015 and 0016 before the new application image; readiness requires
schema version 16. Older conversations were browser-only and cannot be restored
from the server. Test with an interactive human `gateway-propose` token, not a
service credential. No personal L3 decision is needed to create a draft.

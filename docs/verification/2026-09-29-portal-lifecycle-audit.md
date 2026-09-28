# Portal lifecycle walk-through — 29 September 2026

Scope: current `/human/` browser interface and Gateway routes at the source
revision of this change. This is a route and state audit, not an assertion that
a UAV engineering baseline has been produced.

| Phase | Browser path | Observed boundary |
| --- | --- | --- |
| Human idea | Sign in, enter name, goal and constraints, create draft | Owner-scoped `POST /human/projects` persists human text, version 1 and SHA-256. The owner reported a successful creation. |
| Intake clarification | Select draft, send to Alice, refresh and reopen the transcript | New exchanges are persisted in PostgreSQL, owner-scoped and displayed after login. The model receives the draft and up to 24 recent turns with a 24,000-character bound. Alice is instructed to summarize known facts and suggest the next action when enough information exists. This is prose, not a deterministic engineering readiness decision. Conversations before migration 0016 existed only in the browser and cannot be recovered from the server. |
| Project genesis | Select Standard Profile, Git repository, clean StrictDoc and Capella sources, OpenProject Change Request | **Stop.** No portal transition or Gateway project-genesis transaction connects a draft to these resources. The top lifecycle shows `Замысел · черновик` and labels the next step unavailable. |
| Requirements and architecture | L1/L2 proposals and native workspace writes | Gateway MCP has `create_workspace`, `save_workspace_element`, typed relations, validation and reconciliation, but requires an existing baseline/Change Request; the portal has no authoring view or draft-to-workspace mapping. StrictDoc and Capella bridge acceptance is separately limited to isolated staging fixtures. |
| Verification and independent review | Read current evidence and review | `/human/workspaces/{uuid}` and `/review` exist for an existing workspace. A draft has no workspace UUID or validation/reconciliation evidence. |
| Human L3 and baseline | Approve an independently reviewed, current workspace | `/approve` is restricted to a human L3 role and current evidence. The `Alaramia` draft author has proposal role only. No L3 action or baseline was performed. |

The interface therefore cannot traverse the whole lifecycle today. The first
unavailable transition is **project genesis after the draft**. Agent Atelier
role templates and the Alice conversation are not a connected AI Studio
Workflow. The next engineering implementation must create an auditable,
versioned project source and clean model/document workspaces, then wire
structured L1/L2 proposals, deterministic checks and independent review to
that project. Later system-level acceptance must use actual project inputs;
no pre-existing UAV model is required from the owner.

The lifecycle graphic is a process map. Only the draft marker is backed by
the current project record; it does not infer agent activity from a chat reply.

## Response completeness

The previous Responses API request capped output at 700 tokens and accepted
partial text without checking `status`. It now requests 4,000 tokens, checks
`status` and `incomplete_details`, and makes at most two bounded continuation
requests when the reason is `max_output_tokens`. Other incomplete results fail
closed with 502 rather than displaying a fragment as a completed answer. The
full transcript is stored only after a completed response. These checks are
covered by mocked API tests; a signed-in live Alice conversation still needs
human acceptance after staging deployment.

## Remaining transitions

The missing project-genesis operation is an engineering gap in Gateway and
staging. A blank, versioned Capella source and StrictDoc project must be
created per project, with selected Standard Profiles and Git provenance;
OpenProject must register the initial change without declaring an approved
baseline. Gateway's current `create_workspace` requires a baseline and a
Change Request, so a newly created human draft cannot simply call it. The
first baseline needs a separate genesis workflow and its own governance gate.
The browser also lacks typed requirement/architecture editing, linked evidence,
deterministic validation/reconciliation controls and a project-to-workspace
association. A prose Alice recommendation alone cannot advance the lifecycle
or authorize a baseline.

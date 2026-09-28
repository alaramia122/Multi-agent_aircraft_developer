# Portal lifecycle walk-through — 29 September 2026

Scope: current `/human/` browser interface and Gateway routes at the source
revision of this change. This is a route and state audit, not an assertion that
a UAV engineering baseline has been produced.

| Phase | Browser path | Observed boundary |
| --- | --- | --- |
| Human idea | Sign in, enter name, goal and constraints, create draft | Owner-scoped `POST /human/projects` persists human text, version 1 and SHA-256. The owner reported a successful creation. |
| Intake clarification | Select draft, send to Alice | Signed chat now receives the selected owned draft as source data. This is prose clarification, not typed engineering output. The owner must explicitly send it. |
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

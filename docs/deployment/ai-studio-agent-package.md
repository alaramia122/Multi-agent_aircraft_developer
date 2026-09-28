# AI Studio agent package for first engineering project

Status: eight Agent Atelier staging role templates deployed as V1; MCP attachment and orchestration pending. The
external Gateway MCP Hub connection is live in staging. A real aircraft
requirement or model is not needed to create these role templates; no
engineering claims or baselines may be generated from placeholder content.

## Identity and tool boundary

Folder: `b1giu3819pc928o3i2gi`. Private MCP Hub server:
`engineering-gateway-staging` (`db8uuabjuv3l1dmiosff`), Streamable HTTP.
Eight exposed tools: `get_engineering_element`,
`get_engineering_relations`, `validate_engineering_graph`,
`create_workspace`, `save_workspace_element`,
`add_workspace_relation`, `prepare_workspace_for_approval`,
`reconcile_workspace`. The AI Studio machine credential is L2.
`record_independent_review` is excluded from the MCP Hub tool set; human
L3 is available only through the interactive `/human/` route and a human
identity. Agents must not call the human route using a service credential.

Every agent receives the same global instruction:

> Return only proposals grounded in an explicitly supplied engineering input
> with its source URI, version or immutable digest. Distinguish source facts,
> assumptions and derived suggestions. Never invent a requirement or model
> from an ID, title, or example name. Work in a change request workspace;
> include Standard Profile ID and version. If an input, baseline, profile,
> budget, validation or independent evidence is missing, return BLOCKED with
> the missing item. Do not claim compliance, approval, an accepted baseline,
> independent review or a completed real-world verification. Do not expose
> credentials. The Gateway decides authorization and deterministic validation.

Required output envelope for every agent (JSON object):
`{role, status: "PROPOSED"|"BLOCKED", input_refs: [{uri, version, digest}],
profile: {id, version}, proposed_elements: [], proposed_relations: [],
assumptions: [], evidence_refs: [], unresolved: [], next_step}`.
A free-text answer alone is not a canonical EngineeringElement.

## MVP-3 initial roles

| Agent | Scope | Allowed Gateway tools | Stop condition |
| --- | --- | --- | --- |
| Requirements Agent | Decompose and word draft requirements from provided source content; preserve provenance. | Read, validate; L2 workspace writes only under a supplied CR. | No source text or identifiable origin. |
| System Architect | Propose ARP4754A functions, architecture and allocations with explicit relation sources. | Read, validate; L2 workspace writes only under a supplied CR. | Missing system context or allocation rationale. |
| Safety Agent | Identify safety relations and gaps; record assumptions rather than asserting safety classification. | Read, validate; L2 workspace writes only under a supplied CR. | Missing hazard input or safety evidence. |
| Verification Agent | Propose verification strategy, cases and coverage; report open traces. | Read, validate; L2 workspace writes only under a supplied CR. | Missing verifiable requirement, result or evidence. |
| Chief Engineer | Summarize agent proposals, request deterministic validation, prepare review packet. | Read, validate, prepare; no review or L3 tool. | Validation fails or evidence is stale. |
| Software Architect | Propose DO-178C decomposition, HLR/LLR architecture and source links. | Read, validate; L2 workspace writes only under a supplied CR. | No software allocation or approved upstream requirement. |
| Configuration Agent | Compare profile, source baseline, Git and native workspace version/digests. | Read, validate, prepare; reconcile only when Gateway governance allows. | Version drift or unresolved cross-tool reference. |
| Cost Agent | Evaluate options against supplied budget plan with stated cost assumptions. | Read, validate. | No priced evidence or budget limit. |
| Independent Reviewer | Must use a distinct actor and evidence channel, never the AI Studio L2 service token. | **No MCP Hub registration yet.** | Review identity independence cannot be established. |

## Workflow gate

Start only from a human/external Change Request and approved source baseline.
Requirements -> parallel Architecture, Safety, Software and Verification ->
deterministic Gateway validation -> separate independent review -> human L3
decision. After a real human approval, Gateway reconciliation may update
StrictDoc/Capella/Git and register an evidence-bound baseline. An AI workflow
must stop before the human decision and wait for a new, verified event.
`auto_approve` in an AIStudioAgent step concerns tool invocation only and
must never be interpreted as L3 approval.

Deploy role templates into Agent Atelier only after exact model selection,
tool confirmations and credentials are reviewed. Add the agent IDs to a YaWL
workflow; do not put secrets, personal IdP tokens or artificial engineering
content in the specification. Run MVP-1/2 on actual project inputs during
operation, as agreed with the project owner.

## Live Agent Atelier deployment (2026-09-28)

The project owner signed into AI Studio in folder `b1giu3819pc928o3i2gi`. Eight private staging text agents were created with model **DeepSeek 4 Flash** and a saved V1 instruction. They are not published to external channels and do not yet have the MCP server attached:

| Role | Agent ID |
| --- | --- |
| Requirements Agent | `aacddn75vtqjn21i1s99` |
| System Architect | `aacmb2flcud622tstuh3` |
| Safety Agent | `aac0kr1maotmtp1usafe` |
| Verification Agent | `aachqbvs9th8hk2g35uj` |
| Chief Engineer | `aacghvulpqggjkak1fh6` |
| Software Architect | `aac3qnvrhifnir80g9tf` |
| Configuration Agent | `aac4rgj9hjnp2pnr4fgu` |
| Cost Agent | `aacp4t12t4308e2b68fn` |

The Independent Reviewer was intentionally not created under the same identity or L2 MCP credential; separate reviewer identity and evidence are required. The AI Studio selector displays `engineering-gateway-staging` as Active, private, Streamable HTTP, with eight tools, but its row and checkbox are disabled when attaching it to a text agent. The logged-in owner has inherited cloud owner access; the service account has `serverless.mcpGateways.invoker`. Root cause of the disabled selector remains unverified. Do not make the gateway public or grant an AI token L3 to work around this. The MCP Hub invocation itself passed an authenticated read-only live probe and rejected anonymous access.

A live Agent Atelier test sent only `EngineeringElement ID REQ-001` with no source text, baseline or Standard Profile to the Requirements Agent. It returned `status: BLOCKED`, empty proposed elements/relations, and identified the missing source URI/version/digest, text, baseline, profile and Change Request. This confirms one refusal behavior, not the full engineering workflow. No generated engineering baseline was asserted.

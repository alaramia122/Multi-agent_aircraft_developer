# Human review endpoint

The optional `/human` HTTP application is separate from MCP. Enable it only after configuring a Keycloak public client for interactive human users and setting `IDENTITY__HUMAN_REVIEW_ENABLED=true` and `IDENTITY__HUMAN_CLIENT_IDS=["<client-id>"]`. It verifies the signed user access token against the configured issuer, audience and JWKS. A service account token is rejected even if it has the `gateway-approve` role. The AI Studio service token has no access to this endpoint.

Keep the Gateway listener private until the reverse proxy has a reviewed route for `/human`; the current public staging ingress exposes `/mcp` only. Obtain a user access token through the configured IdP's normal interactive login. Do not put tokens in URLs or commit them to the repository.

For a workspace UUID, the human reviewer reads `GET /human/workspaces/{id}`. The response includes the workspace state, profile, validation evidence, reconciliation versions, staged elements and relations, and the current change-set hash. A separate reviewer records a decision at `POST /human/workspaces/{id}/review` with JSON `{"accepted":true,"reason":"...","evidence_uri":"..."}`. The approving user must be different from the reviewer and preparer when independent review is required.

An authenticated human with the `gateway-approve` realm role can then call `POST /human/workspaces/{id}/approve`. The response contains the baseline ID and Git tag. `POST /human/workspaces/{id}/reject` accepts JSON `{"reason":"..."}`. Domain checks still require a ready workspace, current validation and reconciliation evidence, and an independent review when configured. MCP exposes none of these decisions.

This endpoint does not replace the actual decision of a human approver. The current staging ingress and IdP need configuration and an end-to-end test with real user accounts before this route is available publicly.

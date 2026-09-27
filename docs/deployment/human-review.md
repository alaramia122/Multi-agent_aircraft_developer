# Human review endpoint

The optional `/human` HTTP application is separate from MCP. Enable it only after configuring a Keycloak public client for interactive human users and setting `IDENTITY__HUMAN_REVIEW_ENABLED=true`, `IDENTITY__HUMAN_CLIENT_IDS=["<client-id>"]` and `IDENTITY__HUMAN_ISSUER_URL=https://<public-idp-host>/realms/engineering`. Keep `IDENTITY__ISSUER_URL` for the internal MCP trust boundary, with `IDENTITY__JWKS_URL` pointing to the same realm's private JWKS. Configure the public client for authorization code + PKCE S256, redirect URI `https://<gateway-host>/human/`, web origin `https://<gateway-host>`, and an audience mapper adding `engineering-gateway` to the access token. It verifies signed user access tokens against the public issuer, audience and JWKS. A service account token is rejected even if it has the `gateway-approve` role. The AI Studio service token has no access to this endpoint.

Keep the Gateway listener private until the reverse proxy has a reviewed route for `/human`; the current public staging ingress exposes `/mcp` only. The `/human/` page performs interactive Keycloak login with PKCE and keeps the access token only in the tab's memory. It clears the authorization code from the browser URL after redirect. Do not put tokens in URLs or commit them to the repository. Reloading the page requires login again.

For a workspace UUID, the human reviewer reads `GET /human/workspaces/{id}`. The response includes the workspace state, profile, validation evidence, reconciliation versions, staged elements and relations, and the current change-set hash. A separate reviewer records a decision at `POST /human/workspaces/{id}/review` with JSON `{"accepted":true,"reason":"...","evidence_uri":"..."}`. The approving user must be different from the reviewer and preparer when independent review is required.

Review recording compares the current staged change-set with the reconciled
change-set hash. A mismatch rejects the review before any acceptance evidence
is recorded. The reviewer still has to inspect the actual content-bearing Git
artifacts and external workspace versions; the JSON package alone is not a
rendered requirements or Capella model review.

An authenticated human with the `gateway-approve` realm role can then call `POST /human/workspaces/{id}/approve`. The response contains the baseline ID and Git tag. `POST /human/workspaces/{id}/reject` accepts JSON `{"reason":"..."}`. Domain checks still require a ready workspace, current validation and reconciliation evidence, and an independent review when configured. MCP exposes none of these decisions.

This endpoint does not replace the actual decision of a human approver. The current staging ingress and IdP need configuration and an end-to-end test with real user accounts before this route is available publicly.

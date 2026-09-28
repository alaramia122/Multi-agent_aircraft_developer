# Human review endpoint

The optional `/human` HTTP application is separate from MCP. Enable it only after configuring a Keycloak public client for interactive human users and setting `IDENTITY__HUMAN_REVIEW_ENABLED=true`, `IDENTITY__HUMAN_CLIENT_IDS=["<client-id>"]` and `IDENTITY__HUMAN_ISSUER_URL=https://<public-idp-host>/realms/engineering`. Keep `IDENTITY__ISSUER_URL` for the internal MCP trust boundary, with `IDENTITY__JWKS_URL` pointing to the same realm's private JWKS. Configure the public client for authorization code + PKCE S256, redirect URI `https://<gateway-host>/human/`, web origin `https://<gateway-host>`, and an audience mapper adding `engineering-gateway` to the access token. It verifies signed user access tokens against the public issuer, audience and JWKS. A service account token is rejected even if it has the `gateway-approve` role. The AI Studio service token has no access to this endpoint.

The staging reverse proxy now routes `/human` to Gateway, and the Keycloak public client and issuer are provisioned. Keep the Gateway listener private behind that ingress. The `/human/` page performs interactive Keycloak login with PKCE and keeps the access token only in the tab's memory. It clears the authorization code from the browser URL after redirect. Do not put tokens in URLs or commit them to the repository. Reloading the page requires login again.

The same page includes an optional Russian-language Alice assistant. Configure `AI_STUDIO_PORTAL_ENABLED=true`, `AI_STUDIO_FOLDER_ID=<folder-id>`, and `AI_STUDIO_MODEL_ID=gpt://<folder-id>/aliceai-llm` in the staging deployment environment. Gateway obtains a short-lived IAM token from the VM metadata endpoint and calls the AI Studio Responses API server-side. Browser code never receives the IAM token. `POST /human/assistant/chat` requires the signed interactive Keycloak user token (at least `gateway-read`), rejects service tokens, limits requests to five per user per minute, and accepts at most six short preceding turns. Workspace review content is sent to Alice only when the user explicitly selects a workspace UUID; Gateway first checks that user's read permission. The user must avoid submitting secrets. The assistant is informational: it cannot invoke the L3 route or issue an approval. This direct Alice model path is independent of the currently unverified Agent Atelier saved-agent invocation and MCP Hub attachment.

For a workspace UUID, the human reviewer reads `GET /human/workspaces/{id}`. The response includes the workspace state, profile, validation evidence, reconciliation versions, staged elements and relations, and the current change-set hash. A separate reviewer records a decision at `POST /human/workspaces/{id}/review` with JSON `{"accepted":true,"reason":"...","evidence_uri":"..."}`. The approving user must be different from the reviewer and preparer when independent review is required.

Review recording compares the current staged change-set with the reconciled
change-set hash. A mismatch rejects the review before any acceptance evidence
is recorded. The reviewer still has to inspect the actual content-bearing Git
artifacts and external workspace versions; the JSON package alone is not a
rendered requirements or Capella model review.

An authenticated human with the `gateway-approve` realm role can then call `POST /human/workspaces/{id}/approve`. The response contains the baseline ID and Git tag. `POST /human/workspaces/{id}/reject` accepts JSON `{"reason":"..."}`. Domain checks still require a ready workspace, current validation and reconciliation evidence, and an independent review when configured. MCP exposes none of these decisions.

This endpoint does not replace the actual decision of a human approver. The staging route, issuer, JWKS and service-token exclusion passed automated VM checks. A personal interactive login, inspection of a real review packet and any L3 decision have not been performed.

The staging Compose file defaults `HUMAN_REVIEW_ENABLED=false`; its private VM
environment enables the flag after ingress and IdP verification. Do not assign
the MCP service client the human review client ID or an L3 capability. A real
person must authenticate, inspect current validation and reconciliation evidence,
and record an independent decision; the AI service cannot do so.

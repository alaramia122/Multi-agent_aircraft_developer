# Capella bridge verification, 27 September 2026

| Boundary | Evidence | Result |
| --- | --- | --- |
| Existing VM isolated native sample probe | staging run `36322387529`, job `108628744448`, staging PR #1 | Python4Capella saved the committed fixture's name and description, read it back and replayed without a duplicate. This predates the new bridge. |
| Gateway immutable artifact transport | source PR #14, CI run `36324797804`, 315 passed, 2 skipped for its earlier code head; HMAC follow-up pending CI | Git commit and SHA-256 resolved before private HTTP transport. Dedicated HMAC authenticates the request. CI includes local staging smoke, not the live VM deployment. |
| New native workspace service | staging PR #3, local `test_bridge_server.py`: 3 passed; Ruff passed | Isolated copy, source version, manifest, content digest, replay, tamper rejection and HMAC checked with a fake native process. |
| New service on staging VM | No workflow run associated with PR #3 head `304ac1b503f990110a600134b921a5e3ba674262` as of this record | Native sample probe for the new service is prepared in `capella/probe-workspace-bridge.sh`, but has not executed. |
| Target UAV model and full MVP | Target model and authoritative architecture content not provisioned | No target write, reconciliation, independent human review, or L3 baseline has been claimed. |

The deployed Gateway remains the earlier integration commit `c7f709d0435afd9e5423908ef904913b9354f5bc` as last verified by the VM integration job. Source PRs #12, #13, #14 and staging PRs #1, #2, #3 are draft. Their passing CI or isolated sample probes do not change the deployed system.

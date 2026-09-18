#!/usr/bin/env python3
"""Smoke-test a running staging Gateway over its public HTTP boundary."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


BASE_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:8000").rstrip("/")


def get_json(path: str) -> tuple[int, dict[str, object]]:
    request = urllib.request.Request(f"{BASE_URL}{path}", method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError(f"{path}: expected JSON object")
            return response.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{path}: HTTP {exc.code}: {raw}") from exc


def main() -> int:
    status, live = get_json("/health/live")
    if status != 200 or live.get("status") != "ok":
        raise RuntimeError(f"liveness check failed: {status} {live}")

    status, ready = get_json("/health/ready")
    if status != 200 or ready.get("status") != "ready":
        raise RuntimeError(f"readiness check failed: {status} {ready}")

    checks = ready.get("checks")
    if not isinstance(checks, list):
        raise RuntimeError("readiness response has no checks list")

    by_name = {
        item.get("name"): item
        for item in checks
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    for required in ("postgresql", "git.repository"):
        check = by_name.get(required)
        if not isinstance(check, dict) or check.get("status") != "ready":
            raise RuntimeError(f"required staging check is not ready: {required}: {check}")

    for optional in ("strictdoc", "capella", "openproject", "object_storage"):
        check = by_name.get(optional)
        if not isinstance(check, dict) or check.get("status") != "disabled":
            raise RuntimeError(f"optional integration must be explicitly disabled in core staging: {optional}: {check}")

    print("staging smoke: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - CLI smoke test should report one actionable failure
        print(f"staging smoke: FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

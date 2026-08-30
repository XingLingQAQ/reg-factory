"""Codex K12 workspace operations used by the unified Python workflow."""

from __future__ import annotations

import time
import uuid
from typing import Any

import requests


CHATGPT_BASE_URL = "https://chatgpt.com"


def normalize_workspace_ids(values: Any) -> list[str]:
    if isinstance(values, str):
        raw = values.replace(",", "\n").splitlines()
    elif isinstance(values, (list, tuple, set)):
        raw = values
    else:
        raw = []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = str(item or "").strip()
        if not value or value.lower() in seen:
            continue
        seen.add(value.lower())
        result.append(value)
    return result[:100]


def send_workspace_invite(
    access_token: str,
    workspace_id: str,
    route: str = "request",
    *,
    timeout: float = 30,
    retries: int = 2,
) -> dict[str, Any]:
    """Request or accept access to one K12 workspace.

    The endpoint intentionally mirrors the former K12 service.  It returns a
    redacted result suitable for task logs; the bearer token is never included.
    """
    token = str(access_token or "").strip()
    workspace = str(workspace_id or "").strip()
    action = str(route or "request").strip().lower()
    if not token:
        raise ValueError("缺少 Codex access token")
    if not workspace:
        raise ValueError("缺少 K12 Workspace ID")
    if action not in {"request", "accept"}:
        raise ValueError("K12 route 只能是 request 或 accept")

    url = f"{CHATGPT_BASE_URL}/backend-api/accounts/{workspace}/invites/{action}"
    headers = {
        "accept": "*/*",
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
        "origin": CHATGPT_BASE_URL,
        "referer": f"{CHATGPT_BASE_URL}/",
        "oai-device-id": str(uuid.uuid4()),
        "oai-language": "zh-CN",
        "user-agent": "Mozilla/5.0 RegFactoryK12/1.0",
    }
    last: dict[str, Any] | None = None
    attempts = max(1, int(retries) + 1)
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(url, headers=headers, data=b"", timeout=timeout)
            body = response.text[:500]
            last = {
                "workspace_id": workspace,
                "route": action,
                "ok": bool(response.ok),
                "status": int(response.status_code),
                "body": body,
                "attempt": attempt,
            }
            if response.ok:
                return last
            if response.status_code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                return last
        except requests.RequestException as exc:
            last = {
                "workspace_id": workspace,
                "route": action,
                "ok": False,
                "status": 0,
                "body": str(exc)[:500],
                "attempt": attempt,
            }
        if attempt < attempts:
            time.sleep(min(30, 1.5 * attempt))
    return last or {
        "workspace_id": workspace,
        "route": action,
        "ok": False,
        "status": 0,
        "body": "未执行",
        "attempt": 0,
    }


def join_workspaces(
    access_token: str,
    workspace_ids: Any,
    route: str = "request",
    *,
    timeout: float = 30,
    retries: int = 2,
    interval: float = 1.5,
) -> list[dict[str, Any]]:
    ids = normalize_workspace_ids(workspace_ids)
    results: list[dict[str, Any]] = []
    for index, workspace_id in enumerate(ids):
        if index:
            time.sleep(max(0, float(interval)))
        results.append(
            send_workspace_invite(
                access_token,
                workspace_id,
                route,
                timeout=timeout,
                retries=retries,
            )
        )
    return results

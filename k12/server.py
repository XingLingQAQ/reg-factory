"""New standalone Codex K12 service.

This service owns its port, storage and task lifecycle while reusing the
reg-factory account parser and OAuth worker as an implementation library.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import secrets
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.environ.get("REG_FACTORY_K12_DATA_DIR") or ROOT / "k12" / "data").resolve()
STATIC_ROOT = Path(__file__).resolve().parent / "static"
CONFIG_PATH = DATA_ROOT / "config.json"
EMAILS_PATH = DATA_ROOT / "emails.json"
TASKS_PATH = DATA_ROOT / "tasks.json"
RUNTIME_ROOT = DATA_ROOT / "runtime"
TEMP_ROOT = RUNTIME_ROOT / "inputs"

app = FastAPI(title="Reg Factory K12")
app.mount("/static", StaticFiles(directory=str(STATIC_ROOT)), name="static")

STATE_LOCK = asyncio.Lock()
TASKS: dict[str, dict[str, Any]] = {}
EMAILS: dict[str, dict[str, Any]] = {}
PROCESSES: dict[str, asyncio.subprocess.Process] = {}
CONFIG: dict[str, Any] = {}
TASK_SEMAPHORE = asyncio.Semaphore(1)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _default_config() -> dict[str, Any]:
    return {
        "port": int(os.environ.get("K12_PORT", "8806") or 8806),
        "workspace_ids": [item.strip() for item in os.environ.get("K12_WORKSPACE_IDS", "").replace(",", "\n").splitlines() if item.strip()],
        "workspace_route": os.environ.get("K12_WORKSPACE_ROUTE", "request"),
        "run_workspace_join": os.environ.get("K12_RUN_WORKSPACE_JOIN", "1").lower() not in {"0", "false", "no", "off"},
        "group": os.environ.get("K12_SUB2API_GROUP", os.environ.get("SUB2API_GROUP", "k12")),
        "concurrency": max(1, min(5, int(os.environ.get("K12_CONCURRENCY", "1") or 1))),
        "timeout": max(120, min(3600, int(os.environ.get("K12_TIMEOUT", "600") or 600))),
        "phone_attempts": max(1, min(10, int(os.environ.get("K12_PHONE_ATTEMPTS", "3") or 3))),
        "sms_timeout": max(30, min(600, int(os.environ.get("K12_SMS_TIMEOUT", "180") or 180))),
        "sms_provider": os.environ.get("K12_SMS_PROVIDER", "auto"),
        "node": os.environ.get("K12_NODE", "auto"),
    }


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return fallback


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _public_email(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id", ""),
        "email": record.get("email", ""),
        "status": record.get("status", "free"),
        "last_error": record.get("last_error", ""),
        "updated_at": record.get("updated_at", ""),
    }


def _public_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in task.items()
        if key not in {"access_token", "password", "refresh_token", "client_id", "raw"}
    }


def _load_state() -> None:
    global CONFIG, EMAILS, TASKS
    CONFIG = {**_default_config(), **(_read_json(CONFIG_PATH, {}) if isinstance(_read_json(CONFIG_PATH, {}), dict) else {})}
    raw_emails = _read_json(EMAILS_PATH, {})
    raw_tasks = _read_json(TASKS_PATH, {})
    EMAILS = raw_emails if isinstance(raw_emails, dict) else {}
    TASKS = raw_tasks if isinstance(raw_tasks, dict) else {}


def _normalize_records(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from common.account_records import parse_account_text

    records, errors = parse_account_text(text, plus_credentials=True)
    result = []
    for item in records:
        email = str(item.get("email") or "").strip().lower()
        if not email:
            continue
        result.append({
            "id": secrets.token_hex(10),
            "email": email,
            "password": str(item.get("password") or ""),
            "account_password": str(item.get("account_password") or ""),
            "refresh_token": str(item.get("refresh_token") or ""),
            "client_id": str(item.get("client_id") or ""),
            "raw": str(item.get("raw") or ""),
            "status": "free",
            "last_error": "",
            "updated_at": _now(),
        })
    return result, errors


async def _persist() -> None:
    async with STATE_LOCK:
        await asyncio.to_thread(_write_json, CONFIG_PATH, CONFIG)
        await asyncio.to_thread(_write_json, EMAILS_PATH, EMAILS)
        await asyncio.to_thread(_write_json, TASKS_PATH, TASKS)


def _child_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["REG_FACTORY_DATA_DIR"] = str(DATA_ROOT)
    env["REG_FACTORY_ENV_FILE"] = str(DATA_ROOT / ".env")
    env["REG_FACTORY_PLATFORM"] = "chatgpt"
    env["SUB2API_GROUP"] = str(CONFIG.get("group") or "k12")
    if CONFIG.get("workspace_ids"):
        env["K12_WORKSPACE_IDS"] = "\n".join(str(item) for item in CONFIG["workspace_ids"])
    return env


def _account_line(record: dict[str, Any]) -> str:
    raw = str(record.get("raw") or "").strip()
    if raw:
        return raw
    fields = [str(record.get("email") or ""), str(record.get("password") or "")]
    if record.get("refresh_token"):
        fields.extend([str(record.get("client_id") or ""), str(record.get("refresh_token") or "")])
    return "----".join(fields)


async def _run_task(task_id: str, record_id: str) -> None:
    async with TASK_SEMAPHORE:
        await _run_task_limited(task_id, record_id)


async def _run_task_limited(task_id: str, record_id: str) -> None:
    task = TASKS[task_id]
    record = EMAILS[record_id]
    TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    input_path = TEMP_ROOT / f"{task_id}.txt"
    input_path.write_text(_account_line(record) + "\n", encoding="utf-8")
    command = [
        sys.executable,
        "-u",
        str(ROOT / "tools" / "import_plus_codex.py"),
        "--accounts-file", str(input_path),
        "--group", str(CONFIG.get("group") or "k12"),
        "--concurrency", "1",
        "--node", str(CONFIG.get("node") or "auto"),
        "--sms-provider", str(CONFIG.get("sms_provider") or "auto"),
        "--phone-attempts", str(CONFIG.get("phone_attempts") or 3),
        "--sms-timeout", str(CONFIG.get("sms_timeout") or 180),
        "--timeout", str(CONFIG.get("timeout") or 600),
        "--workspace-ids", *[str(item) for item in CONFIG.get("workspace_ids") or []],
        "--workspace-route", str(CONFIG.get("workspace_route") or "request"),
        "--delete-input",
    ]
    if CONFIG.get("run_workspace_join"):
        command.append("--run-workspace-join")
    task.update({"status": "running", "started_at": _now(), "updated_at": _now()})
    record.update({"status": "running", "updated_at": _now(), "last_error": ""})
    await _persist()
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(ROOT),
        env=_child_environment(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    PROCESSES[task_id] = process
    try:
        assert process.stdout is not None
        async for line in process.stdout:
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                task.setdefault("logs", []).append(text[:1000])
                task["logs"] = task["logs"][-300:]
                task["updated_at"] = _now()
                await _persist()
        code = await process.wait()
        task["status"] = "success" if code == 0 else "failed"
        task["returncode"] = code
        record["status"] = "success" if code == 0 else "failed"
        if code != 0:
            record["last_error"] = next((line for line in reversed(task.get("logs", [])) if "[FAIL]" in line), "K12 task failed")[:500]
    except asyncio.CancelledError:
        task["status"] = "canceled"
        record["status"] = "free"
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        raise
    finally:
        PROCESSES.pop(task_id, None)
        input_path.unlink(missing_ok=True)
        task.update({"finished_at": _now(), "updated_at": _now()})
        record["updated_at"] = _now()
        await _persist()


@app.on_event("startup")
async def startup() -> None:
    global TASK_SEMAPHORE
    _load_state()
    TASK_SEMAPHORE = asyncio.Semaphore(max(1, min(5, int(CONFIG.get("concurrency") or 1))))
    DATA_ROOT.mkdir(parents=True, exist_ok=True)


@app.on_event("shutdown")
async def shutdown() -> None:
    for process in list(PROCESSES.values()):
        with contextlib.suppress(ProcessLookupError):
            process.terminate()


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (STATIC_ROOT / "index.html").read_text(encoding="utf-8")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "service": "reg-factory-k12", "version": "1.0.0", "port": CONFIG.get("port", 8806)}


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    public = dict(CONFIG)
    public["sub2api_password_present"] = bool(os.environ.get("SUB2API_PASSWORD"))
    return {"config": public}


@app.patch("/api/config")
async def update_config(request: Request) -> dict[str, Any]:
    payload = await request.json()
    if not isinstance(payload, dict):
        return JSONResponse({"error": "config must be an object"}, status_code=400)
    if "workspace_ids" in payload:
        from k12.workspace import workspace_ids
        CONFIG["workspace_ids"] = workspace_ids(payload["workspace_ids"])
    for key in ("workspace_route", "group", "node", "sms_provider"):
        if key in payload and payload[key] is not None:
            CONFIG[key] = str(payload[key]).strip()
    for key in ("run_workspace_join", "concurrency", "timeout", "phone_attempts", "sms_timeout"):
        if key in payload:
            CONFIG[key] = payload[key]
    await _persist()
    return {"config": CONFIG}


@app.get("/api/emails")
async def list_emails() -> dict[str, Any]:
    return {"items": [_public_email(item) for item in EMAILS.values()]}


@app.post("/api/emails/import")
async def import_emails(request: Request) -> dict[str, Any]:
    payload = await request.json()
    records, errors = _normalize_records(str((payload or {}).get("text") or ""))
    existing = {item.get("email", "").lower() for item in EMAILS.values()}
    added = 0
    for record in records:
        if record["email"] in existing:
            continue
        EMAILS[record["id"]] = record
        existing.add(record["email"])
        added += 1
    await _persist()
    return {"added": added, "skipped": len(records) - added, "invalid": len(errors), "errors": errors[:20], "total": len(EMAILS)}


@app.get("/api/tasks")
async def list_tasks() -> dict[str, Any]:
    return {"items": [_public_task(item) for item in sorted(TASKS.values(), key=lambda value: value.get("created_at", ""), reverse=True)]}


@app.post("/api/tasks")
async def create_tasks(request: Request) -> dict[str, Any]:
    payload = await request.json()
    requested = [str(item) for item in (payload or {}).get("email_ids") or [] if str(item)]
    selected = [EMAILS[item] for item in requested if item in EMAILS]
    if not selected:
        selected = [item for item in EMAILS.values() if item.get("status") == "free"][: int((payload or {}).get("count") or 1)]
    if CONFIG.get("run_workspace_join") and not CONFIG.get("workspace_ids"):
        return JSONResponse({"error": "请先配置 K12 Workspace ID"}, status_code=400)
    created = []
    for record in selected:
        if record.get("status") == "running":
            continue
        task_id = f"k12_{uuid.uuid4().hex[:12]}"
        task = {"id": task_id, "email_id": record["id"], "email": record["email"], "status": "queued", "created_at": _now(), "updated_at": _now(), "logs": []}
        TASKS[task_id] = task
        created.append(_public_task(task))
        asyncio.create_task(_run_task(task_id, record["id"]))
    await _persist()
    return {"tasks": created, "count": len(created)}


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        return JSONResponse({"error": "task not found"}, status_code=404)
    process = PROCESSES.get(task_id)
    if process:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
    task["status"] = "canceled"
    await _persist()
    return {"task": _public_task(task)}


@app.get("/api/tasks/{task_id}/logs")
async def task_logs(task_id: str) -> dict[str, Any]:
    task = TASKS.get(task_id)
    if not task:
        return JSONResponse({"error": "task not found"}, status_code=404)
    return {"task": _public_task(task), "logs": task.get("logs", [])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("k12.server:app", host="127.0.0.1", port=int(os.environ.get("K12_PORT", "8806")), reload=False)

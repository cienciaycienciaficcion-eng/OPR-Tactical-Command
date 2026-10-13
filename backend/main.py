from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

GITHUB_API = "https://api.github.com"
GITHUB_DEVICE = "https://github.com/login/device/code"
GITHUB_OAUTH = "https://github.com/login/oauth"
APP_ID = os.environ.get("GITHUB_APP_ID", "").strip()
CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "").strip()
PRIVATE_KEY = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n").strip()
SESSION_SECRET = os.environ.get("APP_SESSION_SECRET", "").strip()
OWNER = os.environ.get("GITHUB_OWNER", "cienciaycienciaficcion-eng").strip()
REPO = os.environ.get("GITHUB_REPO", "OPR-Tactical-Command").strip()

app = FastAPI(title="OPR Tactical Command API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.environ.get("CORS_ORIGINS", "*").split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class DeviceStart(BaseModel):
    # The mobile app does not send a client secret; GitHub Device Flow uses the public Client ID.
    client_id: str | None = None


class DevicePoll(BaseModel):
    device_code: str = Field(min_length=5, max_length=2048)


class ArmyUpload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    data: dict[str, Any]


class BattleUpload(BaseModel):
    data: dict[str, Any]


def config_ready() -> None:
    missing = []
    for name, value in (
        ("GITHUB_APP_ID", APP_ID),
        ("GITHUB_CLIENT_ID", CLIENT_ID),
        ("GITHUB_APP_PRIVATE_KEY", PRIVATE_KEY),
        ("APP_SESSION_SECRET", SESSION_SECRET),
    ):
        if not value:
            missing.append(name)
    if missing:
        raise HTTPException(status_code=503, detail="Backend not configured: " + ", ".join(missing))


def app_jwt() -> str:
    config_ready()
    now = int(time.time())
    return jwt.encode({"iat": now - 30, "exp": now + 8 * 60, "iss": APP_ID}, PRIVATE_KEY, algorithm="RS256")


async def github_request(method: str, path: str, *, token: str | None = None, app_auth: bool = False, **kwargs: Any) -> httpx.Response:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "OPR-Tactical-Command-API",
    }
    if app_auth:
        headers["Authorization"] = f"Bearer {app_jwt()}"
    elif token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(method, f"{GITHUB_API}{path}", headers=headers, **kwargs)
    return response


def require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not SESSION_SECRET:
        raise HTTPException(status_code=503, detail="Backend not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer session token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=["HS256"], issuer="opr-tactical-command")
        if not payload.get("sub") or not payload.get("login"):
            raise ValueError("missing identity")
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired session")


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "OPR Tactical Command API", "status": "ok", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/device/start")
async def device_start(body: DeviceStart) -> dict[str, Any]:
    config_ready()
    client_id = CLIENT_ID
    if body.client_id and body.client_id != CLIENT_ID:
        raise HTTPException(status_code=400, detail="Client ID does not match server configuration")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(GITHUB_DEVICE, data={"client_id": client_id}, headers={"Accept": "application/json"})
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="GitHub could not start device authorization")
    data = response.json()
    if "device_code" not in data or "user_code" not in data:
        raise HTTPException(status_code=502, detail="Unexpected response from GitHub Device Flow")
    # device_code is returned only to the requesting client and should be treated as temporary secret material.
    return {k: data[k] for k in ("device_code", "user_code", "verification_uri", "verification_uri_complete", "expires_in", "interval") if k in data}


@app.post("/auth/device/poll")
async def device_poll(body: DevicePoll) -> dict[str, Any]:
    config_ready()
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{GITHUB_OAUTH}/access_token",
            data={"client_id": CLIENT_ID, "device_code": body.device_code, "grant_type": "urn:ietf:params:oauth:grant-type:device_code"},
            headers={"Accept": "application/json"},
        )
    
try:
    data = response.json()
except ValueError:
    body_preview = (response.text or "")[:500]
    print(
        "[GitHub device_poll] Respuesta no JSON: "
        f"status={response.status_code}, "
        f"body={body_preview!r}"
    )
    raise HTTPException(
        status_code=502,
        detail=(
            "GitHub devolvió una respuesta no válida "
            f"(HTTP {response.status_code}). "
            "Revisar los logs del backend."
        ),
    )

    if "error" in data:
        err = data.get("error")
        if err in ("authorization_pending", "slow_down"):
            return {"status": err, "interval": data.get("interval")}
        if err == "expired_token":
            return {"status": "expired"}
        if err == "access_denied":
            return {"status": "denied"}
        raise HTTPException(status_code=400, detail=f"GitHub authorization failed: {err}")
    gh_token = data.get("access_token")
    if not gh_token:
        raise HTTPException(status_code=502, detail="GitHub did not return an access token")
    user_response = await github_request("GET", "/user", token=gh_token)
    if user_response.status_code != 200:
        raise HTTPException(status_code=401, detail="Could not verify GitHub user")
    user = user_response.json()
    # Do not return or persist the GitHub access token. Issue a short-lived app session instead.
    now = datetime.now(timezone.utc)
    session = jwt.encode(
        {"sub": str(user["id"]), "login": user["login"], "name": user.get("name"), "iat": now, "exp": now + timedelta(hours=12), "iss": "opr-tactical-command"},
        SESSION_SECRET,
        algorithm="HS256",
    )
    return {"status": "authorized", "session_token": session, "expires_in": 43200, "user": {"id": user["id"], "login": user["login"], "name": user.get("name"), "avatar_url": user.get("avatar_url")}}


async def installation_token() -> str:
    config_ready()
    installations = await github_request("GET", "/app/installations", app_auth=True)
    if installations.status_code != 200:
        raise HTTPException(status_code=502, detail="Unable to list GitHub App installations; verify App ID and private key")
    installation = next((item for item in installations.json() if (item.get("account") or {}).get("login", "").lower() == OWNER.lower()), None)
    if not installation:
        raise HTTPException(status_code=503, detail=f"GitHub App is not installed for {OWNER}")
    token_response = await github_request(
        "POST", f"/app/installations/{installation['id']}/access_tokens", app_auth=True,
        json={"repositories": [REPO], "permissions": {"contents": "write"}},
    )
    if token_response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Unable to create installation token; verify Contents: read/write permission and installation access")
    return token_response.json()["token"]


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_").lower()
    return slug[:80] or "item"


async def put_json(path: str, data: dict[str, Any], message: str) -> dict[str, Any]:
    token = await installation_token()
    encoded = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii")
    url_path = f"/repos/{OWNER}/{REPO}/contents/{path}"
    for attempt in range(3):
        current = await github_request("GET", url_path, token=token)
        payload: dict[str, Any] = {"message": message, "content": encoded, "branch": "main"}
        if current.status_code == 200:
            payload["sha"] = current.json().get("sha")
        elif current.status_code != 404:
            raise HTTPException(status_code=502, detail=f"Could not inspect target file in GitHub (HTTP {current.status_code})")
        saved = await github_request("PUT", url_path, token=token, json=payload)
        if saved.status_code in (200, 201):
            return {"path": path, "sha": (saved.json().get("content") or {}).get("sha"), "url": (saved.json().get("content") or {}).get("html_url")}
        if saved.status_code == 409 and attempt < 2:
            continue
        if saved.status_code in (403, 404):
            raise HTTPException(status_code=502, detail="GitHub rejected the write. Verify that the App is installed on the repository and has Contents: read/write permission.")
        raise HTTPException(status_code=502, detail=f"GitHub write failed (HTTP {saved.status_code})")
    raise HTTPException(status_code=409, detail="Repeated conflict while writing to GitHub; retry the operation")


@app.post("/api/armies")
async def upload_army(body: ArmyUpload, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    raw = json.dumps(body.data, ensure_ascii=False)
    if len(raw.encode("utf-8")) > 1_000_000:
        raise HTTPException(status_code=413, detail="Army JSON exceeds 1 MB")
    army_id = safe_slug(str(body.data.get("id") or body.name))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = f"ejercitos/{safe_slug(user['login'])}/{army_id}-{stamp}.json"
    document = {"schema_version": 1, "owner": {"github_id": user["sub"], "login": user["login"]}, "name": body.name, "uploaded_at": stamp, "army": body.data}
    result = await put_json(path, document, f"Add army {body.name} for {user['login']}")
    return {"ok": True, **result}


@app.post("/api/battles")
async def upload_battle(body: BattleUpload, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    raw = json.dumps(body.data, ensure_ascii=False)
    if len(raw.encode("utf-8")) > 750_000:
        raise HTTPException(status_code=413, detail="Battle report exceeds 750 KB")
    battle_id = safe_slug(str(body.data.get("id") or uuid.uuid4()))
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    year = now.strftime("%Y")
    document = {"schema_version": 1, "uploaded_by": {"github_id": user["sub"], "login": user["login"]}, "uploaded_at": stamp, "battle": body.data}
    path = f"batallas/{year}/{battle_id}-{stamp}.json"
    result = await put_json(path, document, f"Add battle report {battle_id}")
    # A canonical per-battle file is the source of truth. The general index is maintained by a separate workflow
    # to avoid racing simultaneous mobile uploads and overwriting another player's report.
    return {"ok": True, **result, "index_status": "pending_workflow"}


@app.get("/api/config")
def public_config() -> dict[str, str]:
    return {"github_owner": OWNER, "github_repo": REPO, "auth_method": "github_device_flow"}

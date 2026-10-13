from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

GITHUB_API = "https://api.github.com"
GITHUB_DEVICE = "https://github.com/login/device/code"
GITHUB_OAUTH = "https://github.com/login/oauth"
APP_ID = os.environ.get("GITHUB_APP_ID", "").strip()
CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "").strip()
PRIVATE_KEY = os.environ.get("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n").strip()
SESSION_SECRET = os.environ.get("APP_SESSION_SECRET", "").strip()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "").strip()
OWNER = os.environ.get("GITHUB_OWNER", "cienciaycienciaficcion-eng").strip()
REPO = os.environ.get("GITHUB_REPO", "OPR-Tactical-Command").strip()

app = FastAPI(title="OPR Tactical Command API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.environ.get("CORS_ORIGINS", "*").split(",") if x.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


class DeviceStart(BaseModel):
    client_id: str | None = None


class DevicePoll(BaseModel):
    device_code: str = Field(min_length=5, max_length=2048)
    invite_code: str | None = Field(default=None, min_length=6, max_length=80)


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=2, max_length=40, pattern=r"^[\wÀ-ÿ .'-]+$")


class InviteCreate(BaseModel):
    expires_in_hours: int = Field(default=168, ge=1, le=8760)
    max_uses: int = Field(default=1, ge=1, le=100)
    note: str | None = Field(default=None, max_length=200)


class ArmyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    data: dict[str, Any]


class ArmyShare(BaseModel):
    shared: bool


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


def db_ready() -> None:
    if not DATABASE_URL:
        raise HTTPException(status_code=503, detail="Backend database is not configured; set DATABASE_URL to a Render PostgreSQL database")


def db_connect():
    db_ready()
    url = DATABASE_URL
    # Render may provide postgres://; psycopg accepts postgresql://.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)


def init_db() -> None:
    if not DATABASE_URL:
        return
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opr_profiles (
                github_id TEXT PRIMARY KEY,
                github_login TEXT NOT NULL,
                display_name TEXT NOT NULL,
                avatar_url TEXT,
                role TEXT NOT NULL DEFAULT 'player',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opr_invitations (
                code_hash TEXT PRIMARY KEY,
                created_by TEXT NOT NULL,
                note TEXT,
                expires_at TIMESTAMPTZ NOT NULL,
                max_uses INTEGER NOT NULL DEFAULT 1,
                uses INTEGER NOT NULL DEFAULT 0,
                revoked BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opr_armies (
                id TEXT PRIMARY KEY,
                owner_github_id TEXT NOT NULL REFERENCES opr_profiles(github_id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                data JSONB NOT NULL,
                is_shared BOOLEAN NOT NULL DEFAULT FALSE,
                github_path TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS opr_armies_owner_idx ON opr_armies(owner_github_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS opr_armies_shared_idx ON opr_armies(is_shared)")


@app.on_event("startup")
def startup() -> None:
    init_db()


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
        return await client.request(method, f"{GITHUB_API}{path}", headers=headers, **kwargs)


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


def require_admin(authorization: str | None = Header(default=None)) -> None:
    if not ADMIN_API_TOKEN:
        raise HTTPException(status_code=503, detail="Admin invitation creation is not configured")
    if not authorization or not secrets.compare_digest(
        authorization.removeprefix("Bearer ").strip(), ADMIN_API_TOKEN
    ):
        raise HTTPException(status_code=403, detail="Admin authorization required")


def code_hash(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_").lower()
    return slug[:80] or "item"


def session_for(user: dict[str, Any], profile: dict[str, Any]) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": str(user["id"]),
        "login": user["login"],
        "name": user.get("name"),
        "display_name": profile["display_name"],
        "role": profile["role"],
        "iat": now,
        "exp": now + timedelta(hours=12),
        "iss": "opr-tactical-command",
    }, SESSION_SECRET, algorithm="HS256")


def profile_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "github_id": row["github_id"],
        "github_login": row["github_login"],
        "display_name": row["display_name"],
        "avatar_url": row.get("avatar_url"),
        "role": row["role"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "OPR Tactical Command API", "status": "ok", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/database")
def database_health() -> dict[str, str]:
    db_ready()
    try:
        with db_connect() as conn:
            conn.execute("SELECT 1")
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database connection failed; inspect Render logs")


@app.post("/auth/device/start")
async def device_start(body: DeviceStart) -> dict[str, Any]:
    config_ready()
    if body.client_id and body.client_id != CLIENT_ID:
        raise HTTPException(status_code=400, detail="Client ID does not match server configuration")
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(GITHUB_DEVICE, data={"client_id": CLIENT_ID}, headers={"Accept": "application/json"})
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="GitHub could not start device authorization")
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="GitHub returned an invalid Device Flow response")
    if "device_code" not in data or "user_code" not in data:
        raise HTTPException(status_code=502, detail="Unexpected response from GitHub Device Flow")
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
        preview = (response.text or "")[:300]
        print(f"[GitHub device_poll] Non-JSON response: status={response.status_code}, body={preview!r}")
        raise HTTPException(status_code=502, detail=f"GitHub returned an invalid response (HTTP {response.status_code})")
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
    db_ready()
    with db_connect() as conn:
        profile = conn.execute("SELECT * FROM opr_profiles WHERE github_id = %s", (str(user["id"]),)).fetchone()
        if profile is None:
            if not body.invite_code:
                return {"status": "invitation_required", "message": "This account needs a valid invitation code."}
            invitation = conn.execute(
                """SELECT * FROM opr_invitations WHERE code_hash=%s AND revoked=FALSE
                   AND expires_at > NOW() AND uses < max_uses FOR UPDATE""",
                (code_hash(body.invite_code),),
            ).fetchone()
            if invitation is None:
                raise HTTPException(status_code=403, detail="Invalid, expired, revoked, or already-used invitation")
            conn.execute("UPDATE opr_invitations SET uses=uses+1 WHERE code_hash=%s", (invitation["code_hash"],))
            default_name = (user.get("name") or user["login"]).strip()[:40]
            profile = conn.execute(
                """INSERT INTO opr_profiles(github_id, github_login, display_name, avatar_url, role)
                   VALUES (%s,%s,%s,%s,'player') RETURNING *""",
                (str(user["id"]), user["login"], default_name, user.get("avatar_url")),
            ).fetchone()
        else:
            profile = conn.execute(
                """UPDATE opr_profiles SET github_login=%s, avatar_url=%s, updated_at=NOW()
                   WHERE github_id=%s RETURNING *""",
                (user["login"], user.get("avatar_url"), str(user["id"])),
            ).fetchone()
    session = session_for(user, profile)
    return {
        "status": "authorized",
        "session_token": session,
        "expires_in": 43200,
        "user": {
            "id": user["id"], "login": user["login"], "name": user.get("name"),
            "avatar_url": user.get("avatar_url"), "display_name": profile["display_name"],
            "role": profile["role"],
        },
    }


@app.post("/admin/invitations")
def create_invitation(body: InviteCreate, _: None = Depends(require_admin)) -> dict[str, Any]:
    db_ready()
    code = "OPR-" + secrets.token_urlsafe(12).replace("-", "").replace("_", "")[:16].upper()
    expires = datetime.now(timezone.utc) + timedelta(hours=body.expires_in_hours)
    with db_connect() as conn:
        conn.execute(
            """INSERT INTO opr_invitations(code_hash, created_by, note, expires_at, max_uses)
               VALUES (%s,%s,%s,%s,%s)""",
            (code_hash(code), "admin", body.note, expires, body.max_uses),
        )
    # The raw invitation code is shown once and never stored.
    return {"code": code, "expires_at": expires.isoformat(), "max_uses": body.max_uses, "note": body.note}


@app.get("/api/me")
def get_me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    db_ready()
    with db_connect() as conn:
        row = conn.execute("SELECT * FROM opr_profiles WHERE github_id=%s", (str(user["sub"]),)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Player profile not found")
    return profile_dict(row)


@app.patch("/api/me")
def update_me(body: ProfileUpdate, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    db_ready()
    display_name = body.display_name.strip()
    if len(display_name) < 2:
        raise HTTPException(status_code=422, detail="Display name must contain at least 2 characters")
    with db_connect() as conn:
        row = conn.execute(
            """UPDATE opr_profiles SET display_name=%s, updated_at=NOW()
               WHERE github_id=%s RETURNING *""",
            (display_name, str(user["sub"])),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Player profile not found")
    return profile_dict(row)


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
async def create_army(body: ArmyCreate, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    raw = json.dumps(body.data, ensure_ascii=False)
    if len(raw.encode("utf-8")) > 1_000_000:
        raise HTTPException(status_code=413, detail="Army JSON exceeds 1 MB")
    db_ready()
    army_id = safe_slug(str(body.data.get("id") or uuid.uuid4()))
    with db_connect() as conn:
        profile = conn.execute("SELECT display_name FROM opr_profiles WHERE github_id=%s", (str(user["sub"]),)).fetchone()
        if not profile:
            raise HTTPException(status_code=403, detail="Player profile required")
        row = conn.execute(
            """INSERT INTO opr_armies(id, owner_github_id, name, data, is_shared)
               VALUES (%s,%s,%s,%s::jsonb,FALSE) RETURNING id,name,is_shared,created_at""",
            (str(uuid.uuid4()), str(user["sub"]), body.name, json.dumps(body.data, ensure_ascii=False)),
        ).fetchone()
    # Private armies stay in PostgreSQL and are NOT written to the public GitHub repository.
    return {"ok": True, "id": row["id"], "name": row["name"], "shared": False, "visibility": "private", "created_at": row["created_at"].isoformat()}


@app.get("/api/armies")
def list_armies(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    db_ready()
    with db_connect() as conn:
        rows = conn.execute(
            """SELECT id,name,is_shared,github_path,created_at,updated_at
               FROM opr_armies WHERE owner_github_id=%s
               ORDER BY updated_at DESC""",
            (str(user["sub"]),),
        ).fetchall()
    return {"items": [{
        "id": r["id"], "name": r["name"], "shared": r["is_shared"],
        "visibility": "public" if r["is_shared"] else "private",
        "github_path": r["github_path"],
        "created_at": r["created_at"].isoformat(),
        "updated_at": r["updated_at"].isoformat(),
    } for r in rows]}


@app.get("/api/armies/{army_id}")
def get_army(army_id: str, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    db_ready()
    with db_connect() as conn:
        row = conn.execute(
            """SELECT id,owner_github_id,name,data,is_shared,github_path,created_at,updated_at
               FROM opr_armies WHERE id=%s AND (owner_github_id=%s OR is_shared=TRUE)""",
            (army_id, str(user["sub"])),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Army not found")
    return {"id": row["id"], "name": row["name"], "data": row["data"], "shared": row["is_shared"], "owner_github_id": row["owner_github_id"]}


@app.patch("/api/armies/{army_id}/sharing")
async def set_army_sharing(army_id: str, body: ArmyShare, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    db_ready()
    with db_connect() as conn:
        row = conn.execute(
            "SELECT id,name,data,is_shared,github_path FROM opr_armies WHERE id=%s AND owner_github_id=%s FOR UPDATE",
            (army_id, str(user["sub"])),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Army not found")
        if body.shared and not row["is_shared"]:
            # Publish only after explicit opt-in. This repository is public, so the file becomes publicly readable.
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            path = f"ejercitos-compartidos/{safe_slug(user['login'])}/{safe_slug(row['name'])}-{stamp}-{safe_slug(army_id[:8])}.json"
            public_doc = {
                "schema_version": 1,
                "owner": {"github_id": user["sub"], "login": user["login"], "display_name": user.get("display_name") or user["login"]},
                "name": row["name"], "shared": True, "published_at": stamp, "army": row["data"],
            }
            result = await put_json(path, public_doc, f"Share army {row['name']} by {user['login']}")
            row = conn.execute(
                """UPDATE opr_armies SET is_shared=TRUE,github_path=%s,updated_at=NOW()
                   WHERE id=%s RETURNING id,name,is_shared,github_path""",
                (path, army_id),
            ).fetchone()
            return {"ok": True, "id": row["id"], "shared": True, "visibility": "public", "github_path": row["github_path"], "url": result["url"]}
        if not body.shared and row["is_shared"]:
            # A public GitHub commit cannot guarantee erasure from clones/caches. Remove current repository file,
            # while clearly explaining that previously copied public content may persist.
            path = row["github_path"]
            if path:
                token = await installation_token()
                encoded_path = "/repos/{}/{}/contents/{}".format(OWNER, REPO, path)
                current = await github_request("GET", encoded_path, token=token)
                if current.status_code == 200:
                    sha = current.json().get("sha")
                    deleted = await github_request("DELETE", encoded_path, token=token, json={"message": f"Unshare army {row['name']}", "sha": sha, "branch": "main"})
                    if deleted.status_code >= 300:
                        raise HTTPException(status_code=502, detail="Could not remove public copy from GitHub")
            row = conn.execute(
                """UPDATE opr_armies SET is_shared=FALSE,github_path=NULL,updated_at=NOW()
                   WHERE id=%s RETURNING id,name,is_shared""",
                (army_id,),
            ).fetchone()
            return {"ok": True, "id": row["id"], "shared": False, "visibility": "private", "warning": "The current public repository copy was removed, but copies, forks, caches, or previous clones may remain."}
        return {"ok": True, "id": row["id"], "shared": row["is_shared"], "visibility": "public" if row["is_shared"] else "private"}


@app.get("/api/armies/shared")
def list_shared_armies() -> dict[str, Any]:
    db_ready()
    with db_connect() as conn:
        rows = conn.execute(
            """SELECT id,name,owner_github_id,github_path,created_at FROM opr_armies
               WHERE is_shared=TRUE ORDER BY updated_at DESC LIMIT 500"""
        ).fetchall()
    return {"items": [{
        "id": r["id"], "name": r["name"], "owner_github_id": r["owner_github_id"],
        "github_path": r["github_path"], "created_at": r["created_at"].isoformat(),
    } for r in rows]}


@app.post("/api/battles")
async def upload_battle(body: BattleUpload, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    raw = json.dumps(body.data, ensure_ascii=False)
    if len(raw.encode("utf-8")) > 750_000:
        raise HTTPException(status_code=413, detail="Battle report exceeds 750 KB")
    battle_id = safe_slug(str(body.data.get("id") or uuid.uuid4()))
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    path = f"batallas/{now.strftime('%Y')}/{battle_id}-{stamp}.json"
    document = {"schema_version": 1, "uploaded_by": {"github_id": user["sub"], "login": user["login"]}, "uploaded_at": stamp, "battle": body.data}
    result = await put_json(path, document, f"Add battle report {battle_id}")
    return {"ok": True, **result, "index_status": "pending_workflow"}


@app.get("/api/config")
def public_config() -> dict[str, str]:
    return {"github_owner": OWNER, "github_repo": REPO, "auth_method": "github_device_flow_invitation"}

import secrets
import time
from typing import Optional, Tuple

import httpx
import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

from .config import settings
from .keycloak import KeycloakClient
from .pkce import compute_code_challenge, generate_code_verifier
from .session_store import SessionRecord, SessionStore

app = FastAPI(title="bionicpro-auth")

keycloak = KeycloakClient()
sessions = SessionStore(secret=settings.auth_secret_key, session_ttl_seconds=settings.session_ttl_seconds)
proxy_http = httpx.AsyncClient(timeout=30.0)

SESSION_COOKIE = "session_id"
PENDING_STATE_TTL = 600
ACCESS_TOKEN_REFRESH_MARGIN = 10.0

_pending_states: dict[str, dict] = {}


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _decode_claims(tokens: dict) -> dict:
    raw = tokens.get("access_token") or tokens.get("id_token")
    claims = jwt.decode(raw, options={"verify_signature": False}, algorithms=["RS256"])
    return {
        "user_id": claims.get("sub"),
        "username": claims.get("preferred_username"),
        "email": claims.get("email"),
        "roles": claims.get("realm_access", {}).get("roles", []),
    }


async def _ensure_fresh_access_token(session_id: str, record: SessionRecord) -> Tuple[bool, SessionRecord]:
    if record.access_expires_at - time.time() > ACCESS_TOKEN_REFRESH_MARGIN:
        return True, record
    if record.refresh_expires_at < time.time():
        return False, record
    refresh_token = sessions.decrypt_refresh_token(record)
    tokens = await keycloak.refresh(refresh_token)
    if not tokens:
        return False, record
    updated = sessions.update_tokens(
        session_id,
        access_token=tokens["access_token"],
        access_expires_at=time.time() + float(tokens.get("expires_in", 0)),
        refresh_token=tokens.get("refresh_token"),
        refresh_expires_at=time.time() + float(tokens.get("refresh_expires_in", 0)),
    )
    return True, updated or record


async def _resolve_session(request: Request) -> Tuple[Optional[str], Optional[SessionRecord]]:
    session_id = request.cookies.get(SESSION_COOKIE)
    record = sessions.get(session_id)
    if record is None:
        return None, None
    fresh, record = await _ensure_fresh_access_token(session_id, record)
    if not fresh:
        sessions.delete(session_id)
        return None, None
    return session_id, record


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/auth/login")
async def login():
    now = time.time()
    for state, pending in list(_pending_states.items()):
        if now - pending["created_at"] > PENDING_STATE_TTL:
            _pending_states.pop(state, None)
    state = secrets.token_urlsafe(32)
    code_verifier = generate_code_verifier()
    _pending_states[state] = {"code_verifier": code_verifier, "created_at": now}
    code_challenge = compute_code_challenge(code_verifier)
    return RedirectResponse(keycloak.authorization_url(state, code_challenge), status_code=302)


@app.get("/auth/callback")
async def callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error or not code or not state:
        return JSONResponse(
            {"error": "authorization_failed", "detail": error or "missing code or state"},
            status_code=400,
        )
    pending = _pending_states.pop(state, None)
    if pending is None or time.time() - pending["created_at"] > PENDING_STATE_TTL:
        return JSONResponse({"error": "invalid_state"}, status_code=400)
    tokens = await keycloak.exchange_code(code, settings.auth_redirect_uri, pending["code_verifier"])
    if not tokens:
        return JSONResponse({"error": "token_exchange_failed"}, status_code=400)
    claims = _decode_claims(tokens)
    now = time.time()
    session_id = sessions.create(
        user_id=claims["user_id"],
        username=claims["username"],
        email=claims["email"],
        roles=claims["roles"],
        access_token=tokens["access_token"],
        access_expires_at=now + float(tokens.get("expires_in", 0)),
        refresh_token=tokens["refresh_token"],
        refresh_expires_at=now + float(tokens.get("refresh_expires_in", 0)),
    )
    response = RedirectResponse(settings.frontend_url, status_code=302)
    _set_session_cookie(response, session_id)
    return response


@app.get("/auth/session")
async def session_status(request: Request):
    session_id, record = await _resolve_session(request)
    if record is None:
        response = JSONResponse({"authenticated": False}, status_code=401)
        _clear_session_cookie(response)
        return response
    new_session_id = sessions.rotate(session_id)
    response = JSONResponse(
        {
            "authenticated": True,
            "session_id": new_session_id,
            "user_id": record.user_id,
            "username": record.username,
            "access_expires_at": record.access_expires_at,
            "session_expires_at": record.last_seen_at + settings.session_ttl_seconds,
        }
    )
    _set_session_cookie(response, new_session_id)
    return response


@app.get("/auth/validate")
async def validate(request: Request):
    session_id, record = await _resolve_session(request)
    if record is None:
        response = Response(status_code=401)
        return response
    new_session_id = sessions.rotate(session_id)
    response = Response(status_code=200)
    response.headers["X-Access-Token"] = record.access_token
    response.headers["X-User-Id"] = record.user_id
    _set_session_cookie(response, new_session_id)
    return response


@app.get("/auth/me")
async def me(request: Request):
    session_id, record = await _resolve_session(request)
    if record is None:
        response = JSONResponse({"detail": "not authenticated"}, status_code=401)
        _clear_session_cookie(response)
        return response
    return {
        "user_id": record.user_id,
        "username": record.username,
        "email": record.email,
        "roles": record.roles,
    }


@app.post("/auth/logout")
async def logout(request: Request):
    session_id = request.cookies.get(SESSION_COOKIE)
    record = sessions.get(session_id)
    if record is not None:
        try:
            await keycloak.revoke(sessions.decrypt_refresh_token(record))
        except Exception:
            pass
        sessions.delete(session_id)
    response = JSONResponse({"logged_out": True})
    _clear_session_cookie(response)
    return response


async def _proxy_reports(request: Request, path: str):
    session_id, record = await _resolve_session(request)
    if record is None:
        response = JSONResponse({"detail": "not authenticated"}, status_code=401)
        _clear_session_cookie(response)
        return response
    target = f"{settings.reports_api_url.rstrip('/')}/reports"
    if path:
        target = f"{target}/{path}"
    try:
        upstream = await proxy_http.request(
            request.method,
            target,
            params=request.query_params,
            content=await request.body(),
            headers={
                "authorization": f"Bearer {record.access_token}",
                "content-type": request.headers.get("content-type", "application/json"),
            },
        )
    except Exception:
        return JSONResponse({"detail": "reports api unavailable"}, status_code=502)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


@app.get("/reports")
async def reports(request: Request):
    return await _proxy_reports(request, "")


@app.get("/reports/{path:path}")
async def reports_nested(request: Request, path: str):
    return await _proxy_reports(request, path)

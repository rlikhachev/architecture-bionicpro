import time
from typing import Optional

import jwt
from fastapi import Request
from fastapi.responses import JSONResponse
from jwt.algorithms import RSAAlgorithm

from .config import settings


class JWKSStore:
    def __init__(self):
        self._keys: dict[str, RSAAlgorithm] = {}
        self._fetched_at: float = 0.0

    def _fetch(self) -> None:
        import httpx

        url = f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}/protocol/openid-connect/certs"
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        keys = {}
        for jwk_key in response.json().get("keys", []):
            if jwk_key.get("kty") == "RSA" and jwk_key.get("use") in ("sig", None):
                keys[jwk_key["kid"]] = RSAAlgorithm.from_jwk(jwk_key)
        self._keys = keys
        self._fetched_at = time.time()

    def get_key(self, kid: str, force_refresh: bool = False):
        if force_refresh or not self._keys or time.time() - self._fetched_at > 3600:
            self._fetch()
        return self._keys.get(kid)


jwks_store = JWKSStore()


def verify_token(token: str) -> dict:
    unverified_header = jwt.get_unverified_header(token)
    key = jwks_store.get_key(unverified_header.get("kid", ""))
    if key is None:
        key = jwks_store.get_key(unverified_header.get("kid", ""), force_refresh=True)
    if key is None:
        raise ValueError("unknown signing key")
    claims = jwt.decode(
        token,
        key=key,
        algorithms=["RS256"],
        audience=settings.expected_audience,
        options={"verify_iss": False},
    )
    issuer = claims.get("iss", "")
    if not issuer.endswith(settings.issuer_suffix):
        raise ValueError("unexpected issuer")
    return claims


def reject(message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"detail": message}, status_code=status_code)


async def get_current_user(request: Request) -> Optional[dict]:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    token = header[7:].strip()
    try:
        return verify_token(token)
    except Exception:
        return None

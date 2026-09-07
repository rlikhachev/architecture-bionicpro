from typing import Optional
from urllib.parse import urlencode

import httpx

from .config import settings

OPENID_SCOPE = "openid profile email"


class KeycloakClient:
    def __init__(self):
        self._http = httpx.AsyncClient(timeout=15.0)

    @property
    def realm_url(self) -> str:
        return f"{settings.keycloak_url.rstrip('/')}/realms/{settings.keycloak_realm}"

    @property
    def public_realm_url(self) -> str:
        return f"{settings.keycloak_public_url.rstrip('/')}/realms/{settings.keycloak_realm}"

    def authorization_url(self, state: str, code_challenge: str) -> str:
        params = urlencode(
            {
                "client_id": settings.client_id,
                "response_type": "code",
                "scope": OPENID_SCOPE,
                "redirect_uri": settings.auth_redirect_uri,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return f"{self.public_realm_url}/protocol/openid-connect/auth?{params}"

    async def exchange_code(self, code: str, redirect_uri: str, code_verifier: str) -> Optional[dict]:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "code_verifier": code_verifier,
        }
        return await self._token_request(data)

    async def refresh(self, refresh_token: str) -> Optional[dict]:
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
        }
        return await self._token_request(data)

    async def revoke(self, refresh_token: str) -> None:
        await self._http.post(
            f"{self.realm_url}/protocol/openid-connect/logout",
            data={
                "client_id": settings.client_id,
                "client_secret": settings.client_secret,
                "refresh_token": refresh_token,
            },
        )

    async def _token_request(self, data: dict) -> Optional[dict]:
        response = await self._http.post(f"{self.realm_url}/protocol/openid-connect/token", data=data)
        if response.status_code != 200:
            return None
        return response.json()

import base64
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, field, replace
from typing import Optional

from cryptography.fernet import Fernet


@dataclass
class SessionRecord:
    user_id: str
    username: str
    email: str
    roles: list
    access_token: str
    access_expires_at: float
    encrypted_refresh_token: str
    refresh_expires_at: float
    created_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self, secret: str, session_ttl_seconds: int):
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        self._fernet = Fernet(key)
        self._session_ttl = session_ttl_seconds
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = threading.Lock()

    def encrypt_refresh_token(self, refresh_token: str) -> str:
        return self._fernet.encrypt(refresh_token.encode("utf-8")).decode("ascii")

    def decrypt_refresh_token(self, record: SessionRecord) -> str:
        return self._fernet.decrypt(record.encrypted_refresh_token.encode("ascii")).decode("utf-8")

    def create(
        self,
        user_id: str,
        username: str,
        email: str,
        roles: list,
        access_token: str,
        access_expires_at: float,
        refresh_token: str,
        refresh_expires_at: float,
    ) -> str:
        self._purge_expired()
        session_id = secrets.token_urlsafe(32)
        record = SessionRecord(
            user_id=user_id,
            username=username,
            email=email,
            roles=roles,
            access_token=access_token,
            access_expires_at=access_expires_at,
            encrypted_refresh_token=self.encrypt_refresh_token(refresh_token),
            refresh_expires_at=refresh_expires_at,
        )
        with self._lock:
            self._sessions[session_id] = record
        return session_id

    def get(self, session_id: Optional[str]) -> Optional[SessionRecord]:
        if not session_id:
            return None
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            if self._is_expired(record):
                del self._sessions[session_id]
                return None
            record.last_seen_at = time.time()
            return record

    def rotate(self, session_id: str) -> str:
        new_session_id = secrets.token_urlsafe(32)
        with self._lock:
            record = self._sessions.pop(session_id, None)
            if record is None:
                raise KeyError(session_id)
            self._sessions[new_session_id] = replace(record, last_seen_at=time.time())
        return new_session_id

    def update_tokens(
        self,
        session_id: str,
        access_token: str,
        access_expires_at: float,
        refresh_token: Optional[str],
        refresh_expires_at: float,
    ) -> Optional[SessionRecord]:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            encrypted = (
                self.encrypt_refresh_token(refresh_token)
                if refresh_token
                else record.encrypted_refresh_token
            )
            updated = replace(
                record,
                access_token=access_token,
                access_expires_at=access_expires_at,
                encrypted_refresh_token=encrypted,
                refresh_expires_at=refresh_expires_at,
            )
            self._sessions[session_id] = updated
            return updated

    def delete(self, session_id: Optional[str]) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)

    def _is_expired(self, record: SessionRecord) -> bool:
        return time.time() - record.last_seen_at > self._session_ttl

    def _purge_expired(self) -> None:
        with self._lock:
            expired = [sid for sid, record in self._sessions.items() if self._is_expired(record)]
            for sid in expired:
                del self._sessions[sid]

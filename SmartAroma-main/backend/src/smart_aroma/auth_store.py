"""Local JSON-backed users and per-user aroma history.

This is intentionally lightweight for the course prototype. Passwords are
stored as PBKDF2 hashes and session tokens are opaque random strings.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator

from smart_aroma.models.sequence_schema import AromaPlan


DATA_FILE = Path("data/auth_store.json")
PBKDF2_ITERATIONS = 200_000


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_user(user: dict[str, Any]) -> dict[str, str]:
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name") or user["username"],
        "created_at": user["created_at"],
    }


def normalize_username(username: str) -> str:
    return username.strip().lower()


def hash_password(password: str) -> dict[str, str | int]:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    ).hex()
    return {"salt": salt, "hash": digest, "iterations": PBKDF2_ITERATIONS}


def verify_password(password: str, password_record: dict[str, Any]) -> bool:
    salt = bytes.fromhex(password_record["salt"])
    expected = str(password_record["hash"])
    iterations = int(password_record.get("iterations", PBKDF2_ITERATIONS))
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations).hex()
    return hmac.compare_digest(digest, expected)


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=4, max_length=128)

    @field_validator("username")
    @classmethod
    def username_must_be_simple(cls, v: str) -> str:
        normalized = normalize_username(v)
        if not normalized.replace("_", "").replace("-", "").isalnum():
            raise ValueError("username can only contain letters, numbers, hyphen, or underscore")
        return normalized


class RegisterRequest(AuthRequest):
    display_name: str | None = Field(default=None, max_length=24)


class AuthResponse(BaseModel):
    token: str
    user: dict[str, str]


class HistoryCreate(BaseModel):
    scene: str
    persona: str
    duration_level: str
    plan_name: str | None = None
    mood_tag: str | None = None
    explanation: str | None = None
    total_duration_sec: int | None = Field(default=None, ge=0)
    plan: AromaPlan | None = None


@dataclass
class AuthStore:
    path: Path = DATA_FILE
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def _empty(self) -> dict[str, Any]:
        return {"users": {}, "tokens": {}, "histories": {}}

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("users", {})
        data.setdefault("tokens", {})
        data.setdefault("histories", {})
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.path)

    def register(self, username: str, password: str, display_name: str | None = None) -> dict[str, Any]:
        username = normalize_username(username)
        with self._lock:
            data = self._load()
            if username in data["users"]:
                raise ValueError("该用户名已存在")
            user = {
                "id": uuid.uuid4().hex,
                "username": username,
                "display_name": (display_name or username).strip() or username,
                "password": hash_password(password),
                "created_at": utc_now_iso(),
            }
            data["users"][username] = user
            data["histories"][user["id"]] = []
            token = secrets.token_urlsafe(32)
            data["tokens"][token] = {"user_id": user["id"], "created_at": utc_now_iso()}
            self._save(data)
            return {"token": token, "user": public_user(user)}

    def login(self, username: str, password: str) -> dict[str, Any]:
        username = normalize_username(username)
        with self._lock:
            data = self._load()
            user = data["users"].get(username)
            if user is None or not verify_password(password, user["password"]):
                raise ValueError("用户名或密码错误")
            token = secrets.token_urlsafe(32)
            data["tokens"][token] = {"user_id": user["id"], "created_at": utc_now_iso()}
            self._save(data)
            return {"token": token, "user": public_user(user)}

    def logout(self, token: str) -> None:
        with self._lock:
            data = self._load()
            data["tokens"].pop(token, None)
            self._save(data)

    def user_for_token(self, token: str) -> dict[str, str] | None:
        with self._lock:
            data = self._load()
            token_record = data["tokens"].get(token)
            if token_record is None:
                return None
            user_id = token_record["user_id"]
            for user in data["users"].values():
                if user["id"] == user_id:
                    return public_user(user)
            return None

    def history_for_user(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            data = self._load()
            return list(data["histories"].get(user_id, []))

    def add_history(self, user_id: str, payload: HistoryCreate) -> dict[str, Any]:
        with self._lock:
            data = self._load()
            entry = {
                "id": uuid.uuid4().hex,
                "created_at": utc_now_iso(),
                **payload.model_dump(),
            }
            history = data["histories"].setdefault(user_id, [])
            history.insert(0, entry)
            del history[30:]
            self._save(data)
            return entry

    def get_history_entry(self, user_id: str, entry_id: str) -> dict[str, Any] | None:
        with self._lock:
            data = self._load()
            for entry in data["histories"].get(user_id, []):
                if entry["id"] == entry_id:
                    return dict(entry)
            return None

    def delete_history(self, user_id: str, entry_id: str) -> bool:
        with self._lock:
            data = self._load()
            history = data["histories"].setdefault(user_id, [])
            before = len(history)
            data["histories"][user_id] = [entry for entry in history if entry["id"] != entry_id]
            changed = len(data["histories"][user_id]) != before
            if changed:
                self._save(data)
            return changed


auth_store = AuthStore()

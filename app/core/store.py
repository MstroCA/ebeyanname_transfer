# -*- coding: utf-8 -*-
"""
Encrypted connection store.

Connections are stored in ~/.recordrelay/connections.enc using a
machine-specific Fernet key derived via PBKDF2.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Union

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .environments import Environment, EnvironmentRegistry

APP_DIR = Path.home() / ".recordrelay"
CONN_FILE = APP_DIR / "connections.enc"
SALT_FILE = APP_DIR / ".salt"


@dataclass
class Connection:
    id: str
    name: str
    environment: str
    host: str
    port: int
    dbname: str
    user: str
    password: str
    db_type: str = "postgresql"
    note: str = ""

    @property
    def env(self) -> Environment:
        return EnvironmentRegistry.instance().get(self.environment)

    def dsn(self) -> str:
        if self.db_type == "mysql":
            return ""
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )

    def connect_params(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
        }

    def masked_summary(self) -> str:
        return f"{self.host}:{self.port}/{self.dbname}"

    @staticmethod
    def new(
        name: str,
        environment: str,
        host: str,
        port: int,
        dbname: str,
        user: str,
        password: str,
        db_type: str = "postgresql",
        note: str = "",
    ) -> "Connection":
        return Connection(
            id=str(uuid.uuid4()),
            name=name,
            environment=environment,
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            db_type=db_type,
            note=note,
        )


def _machine_secret() -> bytes:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    machine_file = APP_DIR / ".machine"
    if machine_file.exists():
        return machine_file.read_bytes()
    secret = (str(uuid.getnode()) + uuid.uuid4().hex).encode("utf-8")
    machine_file.write_bytes(secret)
    try:
        os.chmod(machine_file, 0o600)
    except OSError:
        pass
    return secret


def _derive_key() -> bytes:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    if SALT_FILE.exists():
        salt = SALT_FILE.read_bytes()
    else:
        salt = os.urandom(16)
        SALT_FILE.write_bytes(salt)
        try:
            os.chmod(SALT_FILE, 0o600)
        except OSError:
            pass
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(_machine_secret()))


class ConnectionStore:
    def __init__(self) -> None:
        self._fernet = Fernet(_derive_key())
        self._connections: list[Connection] = []
        self.load()

    def load(self) -> None:
        self._connections = []
        if not CONN_FILE.exists():
            return
        try:
            raw = CONN_FILE.read_bytes()
            data = self._fernet.decrypt(raw)
            items = json.loads(data.decode("utf-8"))
            for item in items:
                item.setdefault("db_type", "postgresql")
                self._connections.append(Connection(**item))
        except (InvalidToken, ValueError, json.JSONDecodeError):
            self._connections = []

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([asdict(c) for c in self._connections]).encode("utf-8")
        token = self._fernet.encrypt(payload)
        CONN_FILE.write_bytes(token)
        try:
            os.chmod(CONN_FILE, 0o600)
        except OSError:
            pass

    def all(self) -> list[Connection]:
        return list(self._connections)

    def by_environment(self, env: Union[Environment, str]) -> list[Connection]:
        env_name = env.name if isinstance(env, Environment) else str(env)
        return [c for c in self._connections if c.environment.upper() == env_name.upper()]

    def get(self, conn_id: str) -> Optional[Connection]:
        return next((c for c in self._connections if c.id == conn_id), None)

    def add(self, conn: Connection) -> None:
        self._connections.append(conn)
        self.save()

    def update(self, conn: Connection) -> None:
        for i, c in enumerate(self._connections):
            if c.id == conn.id:
                self._connections[i] = conn
                self.save()
                return
        raise KeyError(conn.id)

    def remove(self, conn_id: str) -> None:
        self._connections = [c for c in self._connections if c.id != conn_id]
        self.save()

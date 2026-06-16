# -*- coding: utf-8 -*-
"""
Veritabanı tanımlarının şifreli olarak saklanması.

Tanımlar kullanıcının home dizininde, makineye özel türetilmiş bir
anahtarla (Fernet) şifrelenerek tutulur. Şifreler düz metin olarak
diske yazılmaz.

Dosya konumu:
    ~/.beyanname_transfer/connections.enc
    ~/.beyanname_transfer/.salt
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .environments import Environment


APP_DIR = Path.home() / ".beyanname_transfer"
CONN_FILE = APP_DIR / "connections.enc"
SALT_FILE = APP_DIR / ".salt"


@dataclass
class Connection:
    """Tek bir veritabanı tanımı."""
    id: str
    name: str                # Görünen ad, ör: "Prod KATV"
    environment: str         # Environment değeri: PROD / TEST / LOCAL
    host: str
    port: int
    dbname: str
    user: str
    password: str
    note: str = ""

    @property
    def env(self) -> Environment:
        return Environment(self.environment)

    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )

    def masked_summary(self) -> str:
        return f"{self.host}:{self.port}/{self.dbname}"

    @staticmethod
    def new(name: str, environment: str, host: str, port: int,
            dbname: str, user: str, password: str, note: str = "") -> "Connection":
        return Connection(
            id=str(uuid.uuid4()),
            name=name,
            environment=environment,
            host=host,
            port=port,
            dbname=dbname,
            user=user,
            password=password,
            note=note,
        )


def _machine_secret() -> bytes:
    """
    Makineye özgü, kalıcı bir gizli değer üretir/okur.
    Bu, anahtar türetmenin temelini oluşturur; böylece şifreli dosya
    başka makineye kopyalansa bile kolayca çözülemez.
    """
    APP_DIR.mkdir(parents=True, exist_ok=True)
    machine_file = APP_DIR / ".machine"
    if machine_file.exists():
        return machine_file.read_bytes()
    # uuid.getnode() MAC tabanlı + rastgele bileşen
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
    key = base64.urlsafe_b64encode(kdf.derive(_machine_secret()))
    return key


class ConnectionStore:
    """Bağlantı tanımlarını şifreli dosyada saklar/okur."""

    def __init__(self) -> None:
        self._fernet = Fernet(_derive_key())
        self._connections: list[Connection] = []
        self.load()

    # ── kalıcılık ──
    def load(self) -> None:
        self._connections = []
        if not CONN_FILE.exists():
            return
        try:
            raw = CONN_FILE.read_bytes()
            data = self._fernet.decrypt(raw)
            items = json.loads(data.decode("utf-8"))
            self._connections = [Connection(**item) for item in items]
        except (InvalidToken, ValueError, json.JSONDecodeError):
            # Bozuk veya farklı makineden gelmiş dosya — sessizce boşla,
            # üzerine yazılana kadar dokunma.
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

    # ── CRUD ──
    def all(self) -> list[Connection]:
        return list(self._connections)

    def by_environment(self, env: Environment) -> list[Connection]:
        return [c for c in self._connections if c.env == env]

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

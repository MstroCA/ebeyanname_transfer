# -*- coding: utf-8 -*-
"""
Transfer profile store.

A profile captures a reusable (root_table, pk_column, fk_column) combo
so users don't have to re-enter them every time.

Storage: ~/.recordrelay/profiles.enc — same Fernet/PBKDF2 scheme as
ConnectionStore (key derivation is re-used).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

# re-use key derivation from store
from .store import _derive_key, APP_DIR

PROFILES_FILE = APP_DIR / "profiles.enc"

BUILTIN_PROFILE_IDS = {"__beyanname__", "__order__", "__user__", "__custom__"}


@dataclass
class TransferProfile:
    id: str
    name: str
    root_table: str
    pk_column: str
    fk_column: str
    description: str = ""

    @property
    def is_builtin(self) -> bool:
        return self.id in BUILTIN_PROFILE_IDS

    @staticmethod
    def new(
        name: str,
        root_table: str,
        fk_column: str,
        pk_column: str = "id",
        description: str = "",
    ) -> "TransferProfile":
        return TransferProfile(
            id=str(uuid.uuid4()),
            name=name,
            root_table=root_table,
            pk_column=pk_column,
            fk_column=fk_column,
            description=description,
        )


BUILTIN_PROFILES: list[TransferProfile] = [
    TransferProfile(
        id="__beyanname__",
        name="Beyanname (Turkish Tax Declaration)",
        root_table="beyanname",
        pk_column="id",
        fk_column="beyanname_id",
        description="Turkish tax declaration records and all related child tables.",
    ),
    TransferProfile(
        id="__order__",
        name="Order / Invoice",
        root_table="order",
        pk_column="id",
        fk_column="order_id",
        description="Order record and all related line items.",
    ),
    TransferProfile(
        id="__user__",
        name="User Record",
        root_table="user",
        pk_column="id",
        fk_column="user_id",
        description="User record and all user-owned data.",
    ),
    TransferProfile(
        id="__custom__",
        name="Custom (Manual)",
        root_table="",
        pk_column="id",
        fk_column="",
        description="Enter root table and FK column names manually.",
    ),
]


class ProfileStore:
    def __init__(self) -> None:
        self._fernet = Fernet(_derive_key())
        self._profiles: list[TransferProfile] = []
        self.load()

    def load(self) -> None:
        self._profiles = []
        if not PROFILES_FILE.exists():
            return
        try:
            raw = PROFILES_FILE.read_bytes()
            data = self._fernet.decrypt(raw)
            items = json.loads(data.decode("utf-8"))
            for item in items:
                if item.get("id") not in BUILTIN_PROFILE_IDS:
                    self._profiles.append(TransferProfile(**item))
        except (InvalidToken, ValueError, json.JSONDecodeError):
            self._profiles = []

    def _save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([asdict(p) for p in self._profiles]).encode("utf-8")
        token = self._fernet.encrypt(payload)
        PROFILES_FILE.write_bytes(token)

    def all(self) -> list[TransferProfile]:
        """Returns builtins first, then user-defined profiles."""
        return list(BUILTIN_PROFILES) + list(self._profiles)

    def get(self, profile_id: str) -> Optional[TransferProfile]:
        for p in self.all():
            if p.id == profile_id:
                return p
        return None

    def add(self, profile: TransferProfile) -> None:
        if profile.id in BUILTIN_PROFILE_IDS:
            return
        self._profiles.append(profile)
        self._save()

    def update(self, profile: TransferProfile) -> None:
        if profile.id in BUILTIN_PROFILE_IDS:
            return
        for i, p in enumerate(self._profiles):
            if p.id == profile.id:
                self._profiles[i] = profile
                self._save()
                return
        raise KeyError(profile.id)

    def remove(self, profile_id: str) -> None:
        if profile_id in BUILTIN_PROFILE_IDS:
            return
        self._profiles = [p for p in self._profiles if p.id != profile_id]
        self._save()

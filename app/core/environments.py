# -*- coding: utf-8 -*-
"""
Environment definitions and transfer direction rules.

Environments are rank-based: data only flows from higher rank to lower rank.
Custom environments can be added via EnvironmentRegistry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

APP_DIR = Path.home() / ".recordrelay"
ENV_FILE = APP_DIR / "environments.json"


@dataclass(frozen=True)
class Environment:
    name: str
    rank: int

    @property
    def label(self) -> str:
        _labels = {
            "PROD": "Production", "PRODUCTION": "Production",
            "STAGING": "Staging",
            "TEST": "Test",
            "QA": "QA",
            "LOCAL": "Local",
            "DEV": "Development", "DEVELOPMENT": "Development",
        }
        return _labels.get(self.name.upper(), self.name)

    def __str__(self) -> str:
        return self.name

    def __eq__(self, other) -> bool:
        if isinstance(other, Environment):
            return self.name.upper() == other.name.upper()
        if isinstance(other, str):
            return self.name.upper() == other.upper()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.name.upper())


# Module-level constants for backward compatibility
PROD = Environment("PROD", 3)
STAGING = Environment("STAGING", 2)
TEST = Environment("TEST", 2)
QA = Environment("QA", 2)
LOCAL = Environment("LOCAL", 1)
DEV = Environment("DEV", 1)

BUILTIN_ENVIRONMENTS: list[Environment] = [PROD, STAGING, TEST, QA, LOCAL, DEV]


class EnvironmentRegistry:
    _instance: Optional["EnvironmentRegistry"] = None

    def __init__(self) -> None:
        self._envs: list[Environment] = list(BUILTIN_ENVIRONMENTS)
        self._load()

    @classmethod
    def instance(cls) -> "EnvironmentRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def _load(self) -> None:
        if not ENV_FILE.exists():
            return
        try:
            data = json.loads(ENV_FILE.read_text("utf-8"))
            custom = [Environment(e["name"], e["rank"]) for e in data.get("custom", [])]
            builtin_names = {e.name.upper() for e in BUILTIN_ENVIRONMENTS}
            existing_custom = [e for e in custom if e.name.upper() not in builtin_names]
            self._envs = list(BUILTIN_ENVIRONMENTS) + existing_custom
        except Exception:
            pass

    def save_custom(self, custom_envs: list[Environment]) -> None:
        builtin_names = {e.name.upper() for e in BUILTIN_ENVIRONMENTS}
        custom = [e for e in custom_envs if e.name.upper() not in builtin_names]
        APP_DIR.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text(
            json.dumps(
                {"custom": [{"name": e.name, "rank": e.rank} for e in custom]},
                ensure_ascii=False,
            ),
            "utf-8",
        )
        self._envs = list(BUILTIN_ENVIRONMENTS) + custom

    def all(self) -> list[Environment]:
        seen: dict[str, Environment] = {}
        for e in self._envs:
            seen[e.name.upper()] = e
        return sorted(seen.values(), key=lambda e: -e.rank)

    def get(self, name: str) -> Environment:
        upper = name.upper()
        for e in self._envs:
            if e.name.upper() == upper:
                return e
        return Environment(name, 0)

    def names(self) -> list[str]:
        return [e.name for e in self.all()]

    def add_custom(self, name: str, rank: int) -> Environment:
        new_env = Environment(name.upper(), rank)
        existing = [e for e in self._envs if e.name.upper() != name.upper()]
        self._envs = existing + [new_env]
        self.save_custom(self._envs)
        return new_env

    def remove_custom(self, name: str) -> None:
        builtin_names = {e.name.upper() for e in BUILTIN_ENVIRONMENTS}
        if name.upper() in builtin_names:
            return
        self._envs = [e for e in self._envs if e.name.upper() != name.upper()]
        self.save_custom(self._envs)


@dataclass(frozen=True)
class DirectionCheck:
    allowed: bool
    reason: str


def check_direction(source: Environment, target: Environment) -> DirectionCheck:
    if source == target:
        return DirectionCheck(
            False,
            f"Cannot transfer to the same environment ({source.label}).",
        )
    if source.rank > target.rank:
        return DirectionCheck(
            True,
            f"{source.label} → {target.label}: Transfer allowed (data flows downstream).",
        )
    if source.rank == target.rank:
        return DirectionCheck(
            False,
            f"{source.label} → {target.label}: Same-tier transfer not allowed.",
        )
    return DirectionCheck(
        False,
        f"{source.label} → {target.label}: BLOCKED — data cannot flow upstream.",
    )


def allowed_targets_for(
    source: Environment, all_envs: Optional[list[Environment]] = None
) -> list[Environment]:
    if all_envs is None:
        all_envs = EnvironmentRegistry.instance().all()
    return [t for t in all_envs if check_direction(source, t).allowed]

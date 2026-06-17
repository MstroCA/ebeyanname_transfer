# -*- coding: utf-8 -*-
"""Direction rules tests — the most critical safety constraint."""

import pytest

from app.core.environments import (
    Environment, EnvironmentRegistry, check_direction, allowed_targets_for,
    PROD, TEST, LOCAL, STAGING, QA, DEV,
)


@pytest.mark.parametrize("source,target", [
    (PROD, TEST),
    (PROD, LOCAL),
    (TEST, LOCAL),
    (PROD, DEV),
    (STAGING, LOCAL),
    (STAGING, DEV),
])
def test_allowed_directions(source, target):
    assert check_direction(source, target).allowed is True


@pytest.mark.parametrize("source,target", [
    (LOCAL, PROD),
    (TEST, PROD),
    (LOCAL, TEST),
    (DEV, PROD),
    (LOCAL, STAGING),
])
def test_forbidden_upward_directions(source, target):
    chk = check_direction(source, target)
    assert chk.allowed is False
    assert chk.reason


@pytest.mark.parametrize("env", [PROD, TEST, LOCAL, STAGING, QA, DEV])
def test_same_environment_forbidden(env):
    assert check_direction(env, env).allowed is False


def test_no_upward_flow_ever():
    """Data must never flow from lower rank to higher rank."""
    all_envs = [PROD, STAGING, TEST, QA, LOCAL, DEV]
    for s in all_envs:
        for t in all_envs:
            chk = check_direction(s, t)
            if t.rank > s.rank:
                assert chk.allowed is False, f"{s} -> {t} upstream flow must be blocked!"


def test_allowed_targets_for_prod():
    all_envs = [PROD, STAGING, TEST, QA, LOCAL, DEV]
    targets = allowed_targets_for(PROD, all_envs)
    target_names = {e.name for e in targets}
    assert "PROD" not in target_names
    assert "LOCAL" in target_names
    assert "TEST" in target_names


def test_allowed_targets_for_local():
    all_envs = [PROD, STAGING, TEST, QA, LOCAL, DEV]
    assert allowed_targets_for(LOCAL, all_envs) == []


def test_environment_equality():
    assert PROD == Environment("PROD", 3)
    assert PROD == "PROD"
    assert PROD == "prod"
    assert TEST != PROD


def test_custom_environment():
    registry = EnvironmentRegistry()
    custom = Environment("UAT", 2)
    prod = Environment("PROD", 3)
    chk = check_direction(prod, custom)
    assert chk.allowed is True

    chk2 = check_direction(custom, prod)
    assert chk2.allowed is False

# -*- coding: utf-8 -*-
"""Yön kuralları testleri — en kritik güvenlik kısıtı."""

import pytest

from app.core.environments import (
    Environment, check_direction, allowed_targets_for, ALLOWED_DIRECTIONS,
)


@pytest.mark.parametrize("source,target", [
    (Environment.PROD, Environment.TEST),
    (Environment.PROD, Environment.LOCAL),
    (Environment.TEST, Environment.LOCAL),
])
def test_allowed_directions(source, target):
    assert check_direction(source, target).allowed is True


@pytest.mark.parametrize("source,target", [
    (Environment.LOCAL, Environment.PROD),
    (Environment.TEST, Environment.PROD),
    (Environment.LOCAL, Environment.TEST),
])
def test_forbidden_upward_directions(source, target):
    chk = check_direction(source, target)
    assert chk.allowed is False
    assert chk.reason  # bir gerekçe dönmeli


@pytest.mark.parametrize("env", list(Environment))
def test_same_environment_forbidden(env):
    assert check_direction(env, env).allowed is False


def test_no_upward_flow_ever():
    """Hiçbir senaryoda alt ortamdan üst ortama akış olmamalı."""
    for s in Environment:
        for t in Environment:
            chk = check_direction(s, t)
            if t.rank > s.rank:
                assert chk.allowed is False, f"{s}->{t} yukarı akış izinli olmamalı!"


def test_allowed_targets_for_prod():
    targets = set(allowed_targets_for(Environment.PROD))
    assert targets == {Environment.TEST, Environment.LOCAL}


def test_allowed_targets_for_test():
    assert allowed_targets_for(Environment.TEST) == [Environment.LOCAL]


def test_allowed_targets_for_local():
    assert allowed_targets_for(Environment.LOCAL) == []


def test_allowed_set_size():
    # Tam olarak 3 izinli yön olmalı, fazlası güvenlik açığı demektir.
    assert len(ALLOWED_DIRECTIONS) == 3

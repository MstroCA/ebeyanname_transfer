# -*- coding: utf-8 -*-
"""Şifreli bağlantı saklama testleri."""

import importlib
from pathlib import Path

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    """Her test için izole, geçici bir store döndürür."""
    import app.core.store as store_mod
    importlib.reload(store_mod)
    monkeypatch.setattr(store_mod, "APP_DIR", tmp_path)
    monkeypatch.setattr(store_mod, "CONN_FILE", tmp_path / "connections.enc")
    monkeypatch.setattr(store_mod, "SALT_FILE", tmp_path / ".salt")
    return store_mod


def test_add_and_reload(store):
    s = store.ConnectionStore()
    c = store.Connection.new("Prod", "PROD", "h", 5432, "db", "u", "secret-pass")
    s.add(c)

    s2 = store.ConnectionStore()
    names = [x.name for x in s2.all()]
    assert names == ["Prod"]
    assert s2.all()[0].password == "secret-pass"


def test_password_not_plaintext_on_disk(store):
    s = store.ConnectionStore()
    s.add(store.Connection.new("Prod", "PROD", "myhost", 5432,
                               "mydb", "myuser", "supersecret"))
    raw = store.CONN_FILE.read_bytes()
    assert b"supersecret" not in raw
    assert b"myhost" not in raw
    assert b"mydb" not in raw


def test_update(store):
    s = store.ConnectionStore()
    c = store.Connection.new("Prod", "PROD", "h", 5432, "db", "u", "p")
    s.add(c)
    c.name = "Prod KATV"
    s.update(c)
    assert store.ConnectionStore().get(c.id).name == "Prod KATV"


def test_remove(store):
    s = store.ConnectionStore()
    c = store.Connection.new("X", "TEST", "h", 5432, "db", "u", "p")
    s.add(c)
    s.remove(c.id)
    assert store.ConnectionStore().all() == []


def test_by_environment(store):
    from app.core.environments import Environment
    s = store.ConnectionStore()
    s.add(store.Connection.new("P", "PROD", "h", 5432, "db", "u", "p"))
    s.add(store.Connection.new("L", "LOCAL", "h", 5432, "db", "u", "p"))
    assert len(s.by_environment(Environment.PROD)) == 1
    assert len(s.by_environment(Environment.LOCAL)) == 1

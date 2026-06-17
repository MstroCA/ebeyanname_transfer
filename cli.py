#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RecordRelay CLI — for automation, CI/CD, and support teams.

Usage examples:
  recordrelay transfer --source-id <id> --target-id <id> \\
      --record-id 42 --root-table order --fk-column order_id
  recordrelay connections list
  recordrelay profiles list
  recordrelay history --limit 20
"""

import json
import sys
from typing import Optional

import typer

app = typer.Typer(
    name="recordrelay",
    help="RecordRelay — Universal database record transfer across environments.",
    no_args_is_help=True,
)

connections_app = typer.Typer(help="Manage database connections.")
profiles_app = typer.Typer(help="Manage transfer profiles.")
app.add_typer(connections_app, name="connections")
app.add_typer(profiles_app, name="profiles")


def _store():
    from app.core.store import ConnectionStore
    return ConnectionStore()


def _profile_store():
    from app.core.profiles import ProfileStore
    return ProfileStore()


# ── transfer ──────────────────────────────────────────────────────────────────

@app.command()
def transfer(
    source_id: str = typer.Option(..., "--source-id", help="Source connection ID"),
    target_id: str = typer.Option(..., "--target-id", help="Target connection ID"),
    record_id: str = typer.Option(..., "--record-id", help="Record ID value to transfer"),
    root_table: str = typer.Option(..., "--root-table", help="Root/parent table name"),
    fk_column: str = typer.Option(..., "--fk-column", help="FK column name in child tables"),
    pk_column: str = typer.Option("id", "--pk-column", help="PK column in root table"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    skip_delete: bool = typer.Option(False, "--skip-delete", help="Keep existing target data"),
    created_by: Optional[str] = typer.Option(None, "--created-by", help="Override created_by column"),
    field_overrides: Optional[str] = typer.Option(
        None, "--field-overrides", help='JSON string e.g. \'{"col": "value"}\''
    ),
):
    """Transfer a record and all related rows from source to target."""
    from app.core.engine import TransferEngine, DirectionError, TransferError

    store = _store()
    src = store.get(source_id)
    tgt = store.get(target_id)

    if not src:
        typer.echo(f"✕ Source connection '{source_id}' not found.", err=True)
        raise typer.Exit(1)
    if not tgt:
        typer.echo(f"✕ Target connection '{target_id}' not found.", err=True)
        raise typer.Exit(1)

    overrides = {}
    if field_overrides:
        try:
            overrides = json.loads(field_overrides)
        except json.JSONDecodeError as e:
            typer.echo(f"✕ Invalid --field-overrides JSON: {e}", err=True)
            raise typer.Exit(1)

    def on_progress(level: str, msg: str):
        icons = {"ok": "✓", "warn": "⚠", "error": "✕", "step": "▸", "info": "·"}
        icon = icons.get(level, "·")
        typer.echo(f"  {icon} {msg}")

    typer.echo(f"\nRecordRelay {'[DRY RUN] ' if dry_run else ''}Transfer")
    typer.echo(f"  {src.name} ({src.env.label})  →  {tgt.name} ({tgt.env.label})")
    typer.echo(f"  Table: {root_table}  |  FK: {fk_column}  |  Record ID: {record_id}\n")

    engine = TransferEngine(
        source=src,
        target=tgt,
        record_id=record_id,
        root_table=root_table,
        pk_column=pk_column,
        fk_column=fk_column,
        created_by=created_by,
        field_overrides=overrides or None,
        skip_delete=skip_delete,
        dry_run=dry_run,
        progress=on_progress,
        percent=lambda c, t: None,
    )

    try:
        summary = engine.run()
    except DirectionError as e:
        typer.echo(f"\n✕ BLOCKED: {e}", err=True)
        raise typer.Exit(2)
    except TransferError as e:
        typer.echo(f"\n✕ Error: {e}", err=True)
        raise typer.Exit(1)

    typer.echo()
    if summary.fatal_error:
        typer.echo(f"✕ Fatal: {summary.fatal_error}", err=True)
        raise typer.Exit(1)

    status = "DRY RUN complete" if dry_run else ("Done" if summary.ok else "Done with warnings")
    typer.echo(
        f"✓ {status}: {summary.total_rows} rows transferred, "
        f"{summary.skipped_tables} tables skipped, "
        f"{summary.total_errors} errors."
    )
    if summary.total_errors > 0:
        raise typer.Exit(1)


# ── connections ───────────────────────────────────────────────────────────────

@connections_app.command("list")
def connections_list():
    """List all saved connections."""
    store = _store()
    conns = store.all()
    if not conns:
        typer.echo("No connections saved. Use 'recordrelay connections add' to add one.")
        return
    typer.echo(f"{'ID':<38} {'Name':<20} {'Env':<12} {'Type':<12} {'Host:Port/DB'}")
    typer.echo("─" * 100)
    for c in conns:
        typer.echo(f"{c.id:<38} {c.name:<20} {c.environment:<12} {c.db_type:<12} {c.masked_summary()}")


@connections_app.command("add")
def connections_add(
    name: str = typer.Option(..., "--name"),
    env: str = typer.Option(..., "--env", help="Environment name (PROD, TEST, LOCAL, ...)"),
    host: str = typer.Option(..., "--host"),
    port: int = typer.Option(5432, "--port"),
    db: str = typer.Option(..., "--db", help="Database name"),
    user: str = typer.Option(..., "--user"),
    password: str = typer.Option(..., "--password", prompt=True, hide_input=True),
    db_type: str = typer.Option("postgresql", "--type", help="postgresql or mysql"),
    note: str = typer.Option("", "--note"),
):
    """Add a new database connection."""
    from app.core.store import Connection
    store = _store()
    conn = Connection.new(
        name=name, environment=env.upper(), host=host, port=port,
        dbname=db, user=user, password=password, db_type=db_type, note=note,
    )
    store.add(conn)
    typer.echo(f"✓ Connection '{name}' saved (ID: {conn.id})")


@connections_app.command("remove")
def connections_remove(conn_id: str = typer.Argument(..., help="Connection ID to remove")):
    """Remove a connection by ID."""
    store = _store()
    conn = store.get(conn_id)
    if not conn:
        typer.echo(f"✕ Connection '{conn_id}' not found.", err=True)
        raise typer.Exit(1)
    store.remove(conn_id)
    typer.echo(f"✓ Removed connection '{conn.name}'")


@connections_app.command("test")
def connections_test(conn_id: str = typer.Argument(..., help="Connection ID to test")):
    """Test a connection."""
    from app.core.engine import TransferEngine
    store = _store()
    conn = store.get(conn_id)
    if not conn:
        typer.echo(f"✕ Connection '{conn_id}' not found.", err=True)
        raise typer.Exit(1)
    typer.echo(f"Testing {conn.name} ({conn.masked_summary()})...")
    ok, msg = TransferEngine.test_connection(conn)
    if ok:
        typer.echo(f"✓ {msg}")
    else:
        typer.echo(f"✕ {msg}", err=True)
        raise typer.Exit(1)


# ── profiles ──────────────────────────────────────────────────────────────────

@profiles_app.command("list")
def profiles_list():
    """List all transfer profiles."""
    store = _profile_store()
    typer.echo(f"{'Name':<30} {'Root Table':<20} {'FK Column':<20} Description")
    typer.echo("─" * 90)
    for p in store.all():
        built = " [builtin]" if p.is_builtin else ""
        typer.echo(f"{p.name + built:<30} {p.root_table or '—':<20} {p.fk_column or '—':<20} {p.description}")


# ── history ───────────────────────────────────────────────────────────────────

@app.command()
def history(limit: int = typer.Option(20, "--limit", help="Max records to show")):
    """Show transfer history."""
    from app.core.monitoring import read_history
    records = read_history(limit=limit)
    if not records:
        typer.echo("No transfer history found.")
        return
    typer.echo(f"{'Time':<20} {'Table':<16} {'Record':<12} {'Status':<12} {'Rows':>6} {'Duration'}")
    typer.echo("─" * 80)
    for r in records:
        dry = " [DRY]" if r.dry_run else ""
        typer.echo(
            f"{r.timestamp:<20} {r.root_table + dry:<16} {str(r.record_id):<12} "
            f"{r.status:<12} {r.total_rows:>6} {r.duration_sec:g}s"
        )


if __name__ == "__main__":
    app()

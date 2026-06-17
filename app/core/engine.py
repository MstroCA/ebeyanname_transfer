# -*- coding: utf-8 -*-
"""
Generic transfer engine.

Transfers any root record (identified by pk_column = record_id) and all
child rows (identified by fk_column = record_id) from source to target DB.
Supports PostgreSQL and MySQL via the adapter abstraction layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable

from .environments import check_direction
from .store import Connection
from .adapters import get_adapter


class TransferError(Exception):
    pass


class DirectionError(TransferError):
    pass


@dataclass
class TableResult:
    table_name: str
    schema_name: str
    rows_transferred: int = 0
    total_rows: int = 0
    skipped: bool = False
    skip_reason: str = ""
    errors: list = field(default_factory=list)


@dataclass
class TransferSummary:
    started_at: datetime
    dry_run: bool = False
    finished_at: Optional[datetime] = None
    results: list = field(default_factory=list)
    total_rows: int = 0
    total_errors: int = 0
    skipped_tables: int = 0
    fatal_error: str = ""

    @property
    def ok(self) -> bool:
        return not self.fatal_error and self.total_errors == 0


ProgressFn = Callable[[str, str], None]
PercentFn = Callable[[int, int], None]


class TransferEngine:
    def __init__(
        self,
        source: Connection,
        target: Connection,
        record_id: str,
        root_table: str,
        pk_column: str,
        fk_column: str,
        created_by: Optional[str] = None,
        field_overrides: Optional[dict] = None,
        skip_delete: bool = False,
        dry_run: bool = False,
        progress: Optional[ProgressFn] = None,
        percent: Optional[PercentFn] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.source = source
        self.target = target
        self.record_id = record_id
        self.root_table = root_table
        self.pk_column = pk_column
        self.fk_column = fk_column
        self.created_by = created_by
        self.field_overrides: dict = field_overrides or {}
        self.skip_delete = skip_delete
        self.dry_run = dry_run
        self._progress = progress or (lambda lvl, msg: None)
        self._percent = percent or (lambda c, t: None)
        self._cancel_check = cancel_check or (lambda: False)

    def _log(self, level: str, msg: str) -> None:
        prefix = "[DRY RUN] " if self.dry_run else ""
        self._progress(level, prefix + msg)

    def _cancelled(self) -> bool:
        return self._cancel_check()

    def _validate_direction(self) -> None:
        chk = check_direction(self.source.env, self.target.env)
        if not chk.allowed:
            raise DirectionError(chk.reason)
        self._log("info", chk.reason)

    def _apply_overrides(self, row: dict) -> dict:
        if not self.field_overrides and not self.created_by:
            return row
        result = dict(row)
        if self.created_by is not None:
            for col in ("created_by", "updated_by", "last_modified_by", "kullanici_kod"):
                if col in result:
                    result[col] = self.created_by
        for col, val in self.field_overrides.items():
            if col in result:
                result[col] = val
        return result

    def _match_columns(
        self, source_cols: list[str], target_cols: list[str], table_name: str
    ) -> list[str]:
        target_set = set(target_cols)
        source_set = set(source_cols)
        common = [c for c in source_cols if c in target_set]
        only_source = [c for c in source_cols if c not in target_set]
        only_target = [c for c in target_cols if c not in source_set]
        if only_source:
            self._log("warn", f"[{table_name}] Columns in source but not target (skipped): {only_source}")
        if only_target:
            self._log("warn", f"[{table_name}] Columns in target but not source (NULL/DEFAULT): {only_target}")
        return common

    def run(self) -> TransferSummary:
        summary = TransferSummary(started_at=datetime.now(), dry_run=self.dry_run)
        self._validate_direction()

        src_adapter = get_adapter(self.source.db_type)
        tgt_adapter = get_adapter(self.target.db_type)

        self._log("step", f"Connecting to source ({self.source.env.label}): {self.source.masked_summary()}")
        src = src_adapter.connect(self.source)
        self._log("ok", "Source connection established")

        self._log("step", f"Connecting to target ({self.target.env.label}): {self.target.masked_summary()}")
        tgt = tgt_adapter.connect(self.target)
        self._log("ok", "Target connection established")

        try:
            # find root table schema in source
            src_schema = src_adapter.find_schema(src, self.root_table)
            if not src_schema:
                raise TransferError(f"Table '{self.root_table}' not found in source database.")
            self._log("info", f"Schema: {src_schema}")

            # fetch root row
            root_row = src_adapter.fetch_row(src, src_schema, self.root_table, self.pk_column, self.record_id)
            if not root_row:
                raise TransferError(
                    f"No row found in '{self.root_table}' where {self.pk_column} = {self.record_id}"
                )
            self._log("ok", f"Root record found ({self.root_table}.{self.pk_column}={self.record_id})")

            # transfer root row
            r_main = TableResult(table_name=self.root_table, schema_name=src_schema, total_rows=1)
            src_cols = src_adapter.table_columns(src, src_schema, self.root_table)
            tgt_schema = tgt_adapter.find_schema(tgt, self.root_table, src_schema) or src_schema
            tgt_cols = tgt_adapter.table_columns(tgt, tgt_schema, self.root_table)
            common = self._match_columns(src_cols, tgt_cols, self.root_table)
            row_data = self._apply_overrides(root_row)
            values = [row_data.get(c) for c in common]

            if self.dry_run:
                self._log("info", f"[{self.root_table}] Would transfer 1 row (dry run)")
                r_main.rows_transferred = 1
            else:
                if not self.skip_delete:
                    deleted = tgt_adapter.delete_rows(tgt, tgt_schema, self.root_table, self.pk_column, self.record_id)
                    if deleted > 0:
                        self._log("info", f"[{self.root_table}] Deleted {deleted} existing row(s)")
                try:
                    tgt_adapter.insert_row(tgt, tgt_schema, self.root_table, common, values)
                    r_main.rows_transferred = 1
                    self._log("ok", f"[{self.root_table}] 1 row transferred")
                except Exception as e:
                    r_main.errors.append(str(e))
                    self._log("error", f"[{self.root_table}] Insert error: {e}")
                tgt_adapter.commit(tgt)

            summary.results.append(r_main)

            # discover child tables
            all_tables = src_adapter.tables_with_column(src, self.fk_column)
            child_tables = [(s, t) for s, t in all_tables if t != self.root_table]
            total = len(child_tables)
            self._log("info", f"Found {total} child table(s) with column '{self.fk_column}'")

            for idx, (tbl_schema, tbl_name) in enumerate(child_tables, start=1):
                if self._cancelled():
                    self._log("warn", "Transfer cancelled by user.")
                    break
                self._percent(idx, total)
                r = TableResult(table_name=tbl_name, schema_name=tbl_schema)

                try:
                    rows = src_adapter.fetch_child_rows(src, tbl_schema, tbl_name, self.fk_column, self.record_id)
                except Exception as e:
                    r.skipped = True
                    r.skip_reason = f"Read error: {e}"
                    self._log("error", f"[{tbl_name}] Read error: {e}")
                    summary.results.append(r)
                    continue

                if not rows:
                    r.skipped = True
                    r.skip_reason = "No rows in source"
                    summary.results.append(r)
                    continue

                r.total_rows = len(rows)

                if self.dry_run:
                    self._log("info", f"[{tbl_name}] Would transfer {len(rows)} row(s) (dry run)")
                    r.rows_transferred = len(rows)
                    summary.results.append(r)
                    continue

                tgt_tbl_schema = tgt_adapter.find_schema(tgt, tbl_name, tbl_schema)
                if not tgt_tbl_schema:
                    r.skipped = True
                    r.skip_reason = "Table not found in target (schema drift)"
                    self._log("warn", f"[{tbl_name}] Not in target, skipping")
                    summary.results.append(r)
                    continue

                try:
                    src_cols_child = src_adapter.table_columns(src, tbl_schema, tbl_name)
                    tgt_cols_child = tgt_adapter.table_columns(tgt, tgt_tbl_schema, tbl_name)
                except Exception:
                    src_cols_child = []
                    tgt_cols_child = []

                if not tgt_cols_child:
                    r.skipped = True
                    r.skip_reason = "No columns in target table"
                    summary.results.append(r)
                    continue

                common_child = self._match_columns(src_cols_child, tgt_cols_child, tbl_name)
                if not common_child:
                    r.skipped = True
                    r.skip_reason = "No common columns"
                    summary.results.append(r)
                    continue

                if not self.skip_delete:
                    deleted = tgt_adapter.delete_rows(tgt, tgt_tbl_schema, tbl_name, self.fk_column, self.record_id)
                    if deleted > 0:
                        self._log("info", f"[{tbl_name}] Deleted {deleted} existing row(s)")

                for i, row in enumerate(rows):
                    row_data = self._apply_overrides(dict(row))
                    values = [row_data.get(c) for c in common_child]
                    try:
                        tgt_adapter.insert_row(tgt, tgt_tbl_schema, tbl_name, common_child, values)
                        r.rows_transferred += 1
                    except Exception as e:
                        r.errors.append(f"Row {i + 1}: {e}")
                        self._log("error", f"[{tbl_name}] Row {i + 1}: {e}")

                tgt_adapter.commit(tgt)
                self._log("ok", f"[{tbl_name}] {r.rows_transferred}/{len(rows)} rows transferred")
                summary.results.append(r)

        except Exception as e:
            summary.fatal_error = str(e)
            self._log("error", f"Fatal error: {e}")
        finally:
            try:
                src.close()
            except Exception:
                pass
            try:
                tgt.close()
            except Exception:
                pass

        for r in summary.results:
            if r.skipped:
                summary.skipped_tables += 1
            else:
                summary.total_rows += r.rows_transferred
                summary.total_errors += len(r.errors)
        summary.finished_at = datetime.now()
        return summary

    @staticmethod
    def test_connection(conn: Connection) -> tuple[bool, str]:
        try:
            adapter = get_adapter(conn.db_type)
            c = adapter.connect(conn)
            adapter.commit(c)
            c.close()
            return True, "Connection successful."
        except Exception as e:
            return False, str(e)

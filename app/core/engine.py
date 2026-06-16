# -*- coding: utf-8 -*-
"""
Transfer motoru.

V1 (beyanname_transfer.py) mantığının, GUI'den bağımsız, ilerleme
geri-bildirimi (callback) destekli ve yön kuralı zorlamalı hali.

Önemli: Bu motor source ve target Connection nesnelerini alır.
Transfer'i başlatmadan önce check_direction ile yön doğrulanır;
yasak yön gelirse DirectionError fırlatılır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover
    psycopg2 = None

from .environments import check_direction
from .store import Connection


# ── Olay/ilerleme tipleri ──
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
    finished_at: Optional[datetime] = None
    results: list = field(default_factory=list)
    total_rows: int = 0
    total_errors: int = 0
    skipped_tables: int = 0
    fatal_error: str = ""

    @property
    def ok(self) -> bool:
        return not self.fatal_error and self.total_errors == 0


# Progress callback imzası: (level, message)
# level: "info" | "ok" | "warn" | "error" | "step"
ProgressFn = Callable[[str, str], None]
# Yüzde callback: (current, total)
PercentFn = Callable[[int, int], None]


class TransferEngine:
    def __init__(
        self,
        source: Connection,
        target: Connection,
        beyanname_id: int,
        created_by: Optional[str] = None,
        mukellef_vkn: Optional[str] = None,
        skip_delete: bool = False,
        progress: Optional[ProgressFn] = None,
        percent: Optional[PercentFn] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> None:
        self.source = source
        self.target = target
        self.beyanname_id = beyanname_id
        self.created_by = created_by
        self.mukellef_vkn = mukellef_vkn
        self.skip_delete = skip_delete
        self._progress = progress or (lambda lvl, msg: None)
        self._percent = percent or (lambda c, t: None)
        self._cancel_check = cancel_check or (lambda: False)

    # ── yardımcılar ──
    def _log(self, level: str, msg: str) -> None:
        self._progress(level, msg)

    def _cancelled(self) -> bool:
        return self._cancel_check()

    def _validate_direction(self) -> None:
        chk = check_direction(self.source.env, self.target.env)
        if not chk.allowed:
            raise DirectionError(chk.reason)
        self._log("info", chk.reason)

    # ── DB yardımcıları (V1'den uyarlandı) ──
    @staticmethod
    def _connect(conn: Connection):
        if psycopg2 is None:
            raise TransferError("psycopg2 kurulu değil. 'pip install psycopg2-binary'")
        c = psycopg2.connect(conn.dsn())
        c.set_client_encoding("UTF8")
        return c

    @staticmethod
    def _tables_with_beyanname_id(conn) -> list[tuple[str, str]]:
        q = """
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE column_name = 'beyanname_id'
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
        """
        with conn.cursor() as cur:
            cur.execute(q)
            return cur.fetchall()

    @staticmethod
    def _table_columns(conn, schema: str, table: str) -> list[str]:
        q = """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        with conn.cursor() as cur:
            cur.execute(q, (schema, table))
            res = [r[0] for r in cur.fetchall()]
            if res:
                return res
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s
                  AND table_schema NOT IN ('information_schema', 'pg_catalog')
                ORDER BY ordinal_position
            """, (table,))
            return [r[0] for r in cur.fetchall()]

    @staticmethod
    def _find_schema(conn, table: str, preferred: str = "public") -> Optional[str]:
        q = """
            SELECT table_schema FROM information_schema.tables
            WHERE table_name = %s
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY CASE WHEN table_schema = %s THEN 0 ELSE 1 END
            LIMIT 1
        """
        with conn.cursor() as cur:
            cur.execute(q, (table, preferred))
            row = cur.fetchone()
            return row[0] if row else None

    @staticmethod
    def _beyanname_row(conn, schema: str, beyanname_id: int) -> Optional[dict]:
        q = f'SELECT * FROM "{schema}"."beyanname" WHERE id = %s'
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, (beyanname_id,))
            return cur.fetchone()

    @staticmethod
    def _child_rows(conn, schema: str, table: str, beyanname_id: int) -> list[dict]:
        q = f'SELECT * FROM "{schema}"."{table}" WHERE beyanname_id = %s'
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(q, (beyanname_id,))
            return cur.fetchall()

    def _match_columns(self, source_cols, target_cols, table_name):
        target_set = set(target_cols)
        source_set = set(source_cols)
        common = [c for c in source_cols if c in target_set]
        only_source = [c for c in source_cols if c not in target_set]
        only_target = [c for c in target_cols if c not in source_set]
        if only_source:
            self._log("warn", f"[{table_name}] Kaynakta var, hedefte yok (atlanacak): {only_source}")
        if only_target:
            self._log("warn", f"[{table_name}] Hedefte var, kaynakta yok (NULL/DEFAULT): {only_target}")
        return common, only_source, only_target

    def _insert_row(self, cur, schema, table, columns, row):
        values = []
        for col in columns:
            val = row.get(col)
            if col in ("created_by", "updated_by", "last_modified_by", "kullanici_kod") \
                    and self.created_by is not None:
                val = self.created_by
            elif col == "mukellef_vkn" and self.mukellef_vkn is not None:
                val = self.mukellef_vkn
            values.append(val)
        col_str = ", ".join(f'"{c}"' for c in columns)
        ph = ", ".join(["%s"] * len(columns))
        cur.execute(f'INSERT INTO "{schema}"."{table}" ({col_str}) VALUES ({ph})', values)

    def _delete_existing(self, cur, schema, table, beyanname_id, is_beyanname=False):
        if is_beyanname:
            sql = f'DELETE FROM "{schema}"."{table}" WHERE id = %s'
        else:
            sql = f'DELETE FROM "{schema}"."{table}" WHERE beyanname_id = %s'
        cur.execute(sql, (beyanname_id,))
        if cur.rowcount > 0:
            self._log("info", f"[{table}] Mevcut {cur.rowcount} satır silindi (üzerine yazılacak)")

    # ── ana akış ──
    def run(self) -> TransferSummary:
        summary = TransferSummary(started_at=datetime.now())
        self._validate_direction()  # yasaksa burada patlar

        self._log("step", f"Kaynak ({self.source.env.label}) bağlanılıyor: {self.source.masked_summary()}")
        src = self._connect(self.source)
        self._log("ok", "Kaynak bağlantısı başarılı")

        self._log("step", f"Hedef ({self.target.env.label}) bağlanılıyor: {self.target.masked_summary()}")
        tgt = self._connect(self.target)
        self._log("ok", "Hedef bağlantısı başarılı")

        try:
            # beyanname şeması
            with src.cursor() as cur:
                cur.execute("""
                    SELECT table_schema FROM information_schema.tables
                    WHERE table_name = 'beyanname'
                      AND table_schema NOT IN ('information_schema','pg_catalog')
                """)
                schemas = [r[0] for r in cur.fetchall()]
            if not schemas:
                raise TransferError("Kaynakta 'beyanname' tablosu bulunamadı.")
            schema = schemas[0]
            self._log("info", f"Şema: {schema}")

            beyanname_row = self._beyanname_row(src, schema, self.beyanname_id)
            if not beyanname_row:
                raise TransferError(f"Kaynakta beyanname id={self.beyanname_id} bulunamadı.")
            self._log("ok", f"Beyanname bulundu (id={self.beyanname_id})")

            # ── beyanname ana satır ──
            r_main = TableResult(table_name="beyanname", schema_name=schema, total_rows=1)
            src_cols = self._table_columns(src, schema, "beyanname")
            tgt_schema = self._find_schema(tgt, "beyanname", schema) or schema
            tgt_cols = self._table_columns(tgt, tgt_schema, "beyanname")
            common, _, _ = self._match_columns(src_cols, tgt_cols, "beyanname")

            with tgt.cursor() as cur:
                if not self.skip_delete:
                    self._delete_existing(cur, tgt_schema, "beyanname", self.beyanname_id, is_beyanname=True)
                try:
                    self._insert_row(cur, tgt_schema, "beyanname", common, dict(beyanname_row))
                    r_main.rows_transferred = 1
                    self._log("ok", "[beyanname] 1 satır aktarıldı")
                except Exception as e:
                    r_main.errors.append(str(e))
                    self._log("error", f"[beyanname] Insert hatası: {e}")
            tgt.commit()
            summary.results.append(r_main)

            # ── alt tablolar ──
            all_tables = self._tables_with_beyanname_id(src)
            child_tables = [(s, t) for s, t in all_tables if t != "beyanname"]
            total = len(child_tables)
            self._log("info", f"beyanname_id kolonuna sahip {total} alt tablo bulundu")

            for idx, (tbl_schema, tbl_name) in enumerate(child_tables, start=1):
                if self._cancelled():
                    self._log("warn", "İşlem kullanıcı tarafından iptal edildi.")
                    break
                self._percent(idx, total)
                r = TableResult(table_name=tbl_name, schema_name=tbl_schema)

                try:
                    rows = self._child_rows(src, tbl_schema, tbl_name, self.beyanname_id)
                except Exception as e:
                    r.skipped = True
                    r.skip_reason = f"Kaynaktan okuma hatası: {e}"
                    self._log("error", f"[{tbl_name}] Kaynaktan okuma hatası: {e}")
                    summary.results.append(r)
                    continue

                if not rows:
                    r.skipped = True
                    r.skip_reason = "Kaynakta veri yok"
                    summary.results.append(r)
                    continue

                r.total_rows = len(rows)
                test_cols = self._table_columns(src, tbl_schema, tbl_name)

                local_tbl_schema = self._find_schema(tgt, tbl_name, tbl_schema)
                if not local_tbl_schema:
                    r.skipped = True
                    r.skip_reason = "Hedefte tablo yok (Liquibase farkı olabilir)"
                    self._log("warn", f"[{tbl_name}] Hedefte tablo yok, atlanıyor")
                    summary.results.append(r)
                    continue

                try:
                    local_cols = self._table_columns(tgt, local_tbl_schema, tbl_name)
                except Exception:
                    local_cols = []
                if not local_cols:
                    r.skipped = True
                    r.skip_reason = "Hedefte tablo yok (Liquibase farkı olabilir)"
                    summary.results.append(r)
                    continue

                common, _, _ = self._match_columns(test_cols, local_cols, tbl_name)
                if not common:
                    r.skipped = True
                    r.skip_reason = "Ortak kolon yok"
                    self._log("warn", f"[{tbl_name}] Ortak kolon yok, atlanıyor")
                    summary.results.append(r)
                    continue

                with tgt.cursor() as cur:
                    if not self.skip_delete:
                        self._delete_existing(cur, local_tbl_schema, tbl_name, self.beyanname_id)
                    for i, row in enumerate(rows):
                        try:
                            self._insert_row(cur, local_tbl_schema, tbl_name, common, dict(row))
                            r.rows_transferred += 1
                        except Exception as e:
                            r.errors.append(f"Satır {i+1}: {e}")
                            self._log("error", f"[{tbl_name}] Satır {i+1}: {e}")
                tgt.commit()
                self._log("ok", f"[{tbl_name}] {r.rows_transferred}/{len(rows)} satır aktarıldı")
                summary.results.append(r)

        except Exception as e:
            summary.fatal_error = str(e)
            self._log("error", f"Beklenmeyen hata: {e}")
        finally:
            src.close()
            tgt.close()

        # özet
        for r in summary.results:
            if r.skipped:
                summary.skipped_tables += 1
            else:
                summary.total_rows += r.rows_transferred
                summary.total_errors += len(r.errors)
        summary.finished_at = datetime.now()
        return summary

    # ── bağlantı testi (UI'daki "Test Et" butonu için) ──
    @staticmethod
    def test_connection(conn: Connection) -> tuple[bool, str]:
        try:
            c = TransferEngine._connect(conn)
            with c.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
            c.close()
            return True, "Bağlantı başarılı."
        except Exception as e:
            return False, str(e)

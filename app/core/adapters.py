# -*- coding: utf-8 -*-
"""
Database adapter abstraction for PostgreSQL and MySQL.

Adapters normalise the differences between DB drivers so the transfer
engine can work against any supported database without branching logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .store import Connection


class DBAdapter(ABC):
    @abstractmethod
    def connect(self, conn: "Connection"):
        """Return a live DB connection object."""

    @abstractmethod
    def tables_with_column(self, db_conn, col_name: str) -> list[tuple[str, str]]:
        """Return [(schema, table)] for all tables that have col_name."""

    @abstractmethod
    def table_columns(self, db_conn, schema: str, table: str) -> list[str]:
        """Return ordered column names for schema.table."""

    @abstractmethod
    def find_schema(self, db_conn, table: str, preferred: str = "public") -> Optional[str]:
        """Return the schema name where table lives, or None."""

    @abstractmethod
    def fetch_row(
        self, db_conn, schema: str, table: str, pk_col: str, pk_val
    ) -> Optional[dict]:
        """Fetch a single row as a dict."""

    @abstractmethod
    def fetch_child_rows(
        self, db_conn, schema: str, table: str, fk_col: str, fk_val
    ) -> list[dict]:
        """Fetch all rows where fk_col = fk_val."""

    @abstractmethod
    def delete_rows(self, db_conn, schema: str, table: str, col: str, val) -> int:
        """Delete rows where col = val. Returns rowcount."""

    @abstractmethod
    def insert_row(
        self, db_conn, schema: str, table: str, columns: list[str], values: list
    ) -> None:
        """Insert a single row."""

    @abstractmethod
    def commit(self, db_conn) -> None:
        pass

    # helpers that subclasses may override
    def quote(self, identifier: str) -> str:
        return f'"{identifier}"'


# ── PostgreSQL ────────────────────────────────────────────────────────────────

class PostgreSQLAdapter(DBAdapter):

    def connect(self, conn: "Connection"):
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError:
            raise RuntimeError("psycopg2 is not installed. Run: pip install psycopg2-binary")
        params = conn.connect_params()
        c = psycopg2.connect(**params)
        c.set_client_encoding("UTF8")
        return c

    def tables_with_column(self, db_conn, col_name: str) -> list[tuple[str, str]]:
        sql = """
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE column_name = %s
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, (col_name,))
            return cur.fetchall()

    def table_columns(self, db_conn, schema: str, table: str) -> list[str]:
        sql = """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, (schema, table))
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

    def find_schema(self, db_conn, table: str, preferred: str = "public") -> Optional[str]:
        sql = """
            SELECT table_schema FROM information_schema.tables
            WHERE table_name = %s
              AND table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY CASE WHEN table_schema = %s THEN 0 ELSE 1 END
            LIMIT 1
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, (table, preferred))
            row = cur.fetchone()
            return row[0] if row else None

    def fetch_row(self, db_conn, schema: str, table: str, pk_col: str, pk_val) -> Optional[dict]:
        import psycopg2.extras
        sql = f'SELECT * FROM {self.quote(schema)}.{self.quote(table)} WHERE {self.quote(pk_col)} = %s'
        with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (pk_val,))
            row = cur.fetchone()
            return dict(row) if row else None

    def fetch_child_rows(self, db_conn, schema: str, table: str, fk_col: str, fk_val) -> list[dict]:
        import psycopg2.extras
        sql = f'SELECT * FROM {self.quote(schema)}.{self.quote(table)} WHERE {self.quote(fk_col)} = %s'
        with db_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (fk_val,))
            return [dict(r) for r in cur.fetchall()]

    def delete_rows(self, db_conn, schema: str, table: str, col: str, val) -> int:
        sql = f'DELETE FROM {self.quote(schema)}.{self.quote(table)} WHERE {self.quote(col)} = %s'
        with db_conn.cursor() as cur:
            cur.execute(sql, (val,))
            return cur.rowcount

    def insert_row(self, db_conn, schema: str, table: str, columns: list[str], values: list) -> None:
        col_str = ", ".join(self.quote(c) for c in columns)
        ph = ", ".join(["%s"] * len(columns))
        sql = f'INSERT INTO {self.quote(schema)}.{self.quote(table)} ({col_str}) VALUES ({ph})'
        with db_conn.cursor() as cur:
            cur.execute(sql, values)

    def commit(self, db_conn) -> None:
        db_conn.commit()


# ── MySQL / MariaDB ───────────────────────────────────────────────────────────

class MySQLAdapter(DBAdapter):

    def quote(self, identifier: str) -> str:
        return f"`{identifier}`"

    def connect(self, conn: "Connection"):
        try:
            import pymysql
            import pymysql.cursors
        except ImportError:
            raise RuntimeError("PyMySQL is not installed. Run: pip install PyMySQL")
        params = conn.connect_params()
        c = pymysql.connect(
            host=params["host"],
            port=params["port"],
            database=params["dbname"],
            user=params["user"],
            password=params["password"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
        return c

    def tables_with_column(self, db_conn, col_name: str) -> list[tuple[str, str]]:
        sql = """
            SELECT table_schema, table_name
            FROM information_schema.columns
            WHERE column_name = %s
              AND table_schema = DATABASE()
            ORDER BY table_name
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, (col_name,))
            return [(r["table_schema"], r["table_name"]) for r in cur.fetchall()]

    def table_columns(self, db_conn, schema: str, table: str) -> list[str]:
        sql = """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = DATABASE() AND table_name = %s
            ORDER BY ordinal_position
        """
        with db_conn.cursor() as cur:
            cur.execute(sql, (table,))
            return [r["column_name"] for r in cur.fetchall()]

    def find_schema(self, db_conn, table: str, preferred: str = "public") -> Optional[str]:
        sql = "SELECT DATABASE() AS db"
        with db_conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            if not row:
                return None
            db_name = row["db"]
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = %s LIMIT 1",
                (table,),
            )
            r = cur.fetchone()
            return db_name if r else None

    def fetch_row(self, db_conn, schema: str, table: str, pk_col: str, pk_val) -> Optional[dict]:
        sql = f"SELECT * FROM {self.quote(table)} WHERE {self.quote(pk_col)} = %s"
        with db_conn.cursor() as cur:
            cur.execute(sql, (pk_val,))
            return cur.fetchone()

    def fetch_child_rows(self, db_conn, schema: str, table: str, fk_col: str, fk_val) -> list[dict]:
        sql = f"SELECT * FROM {self.quote(table)} WHERE {self.quote(fk_col)} = %s"
        with db_conn.cursor() as cur:
            cur.execute(sql, (fk_val,))
            return cur.fetchall()

    def delete_rows(self, db_conn, schema: str, table: str, col: str, val) -> int:
        sql = f"DELETE FROM {self.quote(table)} WHERE {self.quote(col)} = %s"
        with db_conn.cursor() as cur:
            cur.execute(sql, (val,))
            return cur.rowcount

    def insert_row(self, db_conn, schema: str, table: str, columns: list[str], values: list) -> None:
        col_str = ", ".join(self.quote(c) for c in columns)
        ph = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO {self.quote(table)} ({col_str}) VALUES ({ph})"
        with db_conn.cursor() as cur:
            cur.execute(sql, values)

    def commit(self, db_conn) -> None:
        db_conn.commit()


# ── Factory ───────────────────────────────────────────────────────────────────

def get_adapter(db_type: str) -> DBAdapter:
    if db_type == "mysql":
        return MySQLAdapter()
    return PostgreSQLAdapter()

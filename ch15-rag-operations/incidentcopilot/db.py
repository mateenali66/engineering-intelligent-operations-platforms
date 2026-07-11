"""Postgres connection and schema helpers.

Connection info is read from the standard PG* environment variables (PGHOST,
PGPORT, PGUSER, PGPASSWORD, PGDATABASE) so the same code runs against a local
Docker Postgres and the CI service container with no change.
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector


def connect(dsn: str | None = None) -> psycopg.Connection:
    """Open a connection and register the pgvector type adapter on it.

    register_vector must run on every connection before vector params are sent
    or read, or psycopg ships the embedding as a plain list and the cast fails.
    """
    if dsn is None:
        dsn = "host={host} port={port} user={user} password={pw} dbname={db}".format(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "5432"),
            user=os.environ.get("PGUSER", "copilot"),
            pw=os.environ.get("PGPASSWORD", "copilot"),
            db=os.environ.get("PGDATABASE", "incidentcopilot"),
        )
    conn = psycopg.connect(dsn, autocommit=True)
    # The vector type must exist before the adapter can register it.
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)
    return conn


def apply_schema(conn: psycopg.Connection, schema_path: str = "schema.sql") -> None:
    """Run schema.sql (extension, table, indexes, the rrf_hybrid function)."""
    sql = Path(schema_path).read_text(encoding="utf-8")
    conn.execute(sql)


def reset(conn: psycopg.Connection) -> None:
    """Truncate the chunks table so a run starts from a known state."""
    conn.execute("TRUNCATE chunks RESTART IDENTITY")

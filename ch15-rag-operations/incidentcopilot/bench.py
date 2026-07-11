"""Load the labeled query set and resolve gold (doc_id, heading) pairs to the
chunk ids actually in the table, so the metrics score against real rows.
"""

from __future__ import annotations

import json
from pathlib import Path

import psycopg


def load_queries(path: str = "corpus/queries.json") -> list[dict]:
    """Return the list of {query, gold} entries from queries.json."""
    return json.loads(Path(path).read_text(encoding="utf-8"))["queries"]


def resolve_gold_ids(
    conn: psycopg.Connection, gold: list[dict], variant: str = "plain"
) -> set[int]:
    """Map [{doc_id, heading}, ...] to the matching chunk ids for a variant."""
    ids: set[int] = set()
    for g in gold:
        rows = conn.execute(
            "SELECT id FROM chunks WHERE doc_id = %s AND heading = %s AND variant = %s",
            (g["doc_id"], g["heading"], variant),
        ).fetchall()
        ids.update(r[0] for r in rows)
    return ids

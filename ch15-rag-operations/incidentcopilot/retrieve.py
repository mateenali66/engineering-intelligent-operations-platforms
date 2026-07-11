"""Three retrievers over the chunks table: dense, lexical, and hybrid (RRF).

Dense uses pgvector cosine distance (<=>) over the HNSW index. Lexical uses the
Postgres full-text tsvector column with ts_rank_cd, which is BM25-style coverage
density ranking, not textbook Okapi BM25. Hybrid calls the rrf_hybrid SQL
function, which fuses the two ranked lists with Reciprocal Rank Fusion in one
round trip.
"""

from __future__ import annotations

import psycopg

from .types import Hit


def dense_search(
    conn: psycopg.Connection, embedder, query: str, k: int = 10, variant: str = "plain"
) -> list[Hit]:
    """Nearest neighbors by cosine distance over the HNSW index."""
    vec = embedder.encode([query])[0]
    # Exercise the pgvector 0.8.x iterative-scan behavior so a post-filter on
    # variant cannot silently overfilter the index results.
    conn.execute("SET hnsw.iterative_scan = 'relaxed_order'")
    rows = conn.execute(
        "SELECT id, doc_id, heading, embedding <=> %s AS distance "
        "FROM chunks WHERE variant = %s "
        "ORDER BY embedding <=> %s, id LIMIT %s",
        (vec, variant, vec, k),
    ).fetchall()
    # Score = 1 - distance so higher is better, consistent with the other retrievers.
    return [Hit(id=r[0], doc_id=r[1], heading=r[2], score=1.0 - r[3]) for r in rows]


def lexical_search(
    conn: psycopg.Connection, query: str, k: int = 10, variant: str = "plain"
) -> list[Hit]:
    """BM25-style lexical ranking via Postgres full-text search (ts_rank_cd)."""
    rows = conn.execute(
        "SELECT id, doc_id, heading, "
        "ts_rank_cd(fts, websearch_to_tsquery('english', %s)) AS rank "
        "FROM chunks "
        "WHERE variant = %s AND fts @@ websearch_to_tsquery('english', %s) "
        "ORDER BY rank DESC, id LIMIT %s",
        (query, variant, query, k),
    ).fetchall()
    return [Hit(id=r[0], doc_id=r[1], heading=r[2], score=float(r[3])) for r in rows]


def hybrid_search(
    conn: psycopg.Connection, embedder, query: str, k: int = 10, variant: str = "plain"
) -> list[Hit]:
    """Dense + lexical fused with Reciprocal Rank Fusion (the rrf_hybrid function)."""
    vec = embedder.encode([query])[0]
    conn.execute("SET hnsw.iterative_scan = 'relaxed_order'")
    rows = conn.execute(
        "SELECT id, doc_id, heading, rrf_score "
        "FROM rrf_hybrid(%s, %s, %s, 20, 60, %s)",
        (vec, query, variant, k),
    ).fetchall()
    return [Hit(id=r[0], doc_id=r[1], heading=r[2], score=float(r[3])) for r in rows]

"""Hybrid retrieval must beat dense-only on the identifier query."""

from __future__ import annotations

from incidentcopilot import bench
from incidentcopilot.retrieve import dense_search, hybrid_search


def _rank_of_gold(hits, gold_ids):
    for i, h in enumerate(hits, start=1):
        if h.id in gold_ids:
            return i
    return 10**6


def test_hybrid_beats_dense_on_identifier_query(store):
    conn, embedder, _ = store
    query = "INC-4822 payments gateway mitigation"
    gold = bench.resolve_gold_ids(
        conn,
        [{"doc_id": "payments-incidents", "heading": "Mitigating incident INC-4822 on the payments gateway"}],
        variant="plain",
    )
    dense_rank = _rank_of_gold(dense_search(conn, embedder, query, k=10), gold)
    hybrid_rank = _rank_of_gold(hybrid_search(conn, embedder, query, k=10), gold)
    assert hybrid_rank < dense_rank
    assert hybrid_rank == 1

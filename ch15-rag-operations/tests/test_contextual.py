"""Contextual retrieval must not regress hit-rate vs plain on the labeled set."""

from __future__ import annotations

from incidentcopilot import bench
from incidentcopilot.evaluate import hit_rate, mean_metric
from incidentcopilot.retrieve import hybrid_search


def test_contextual_at_least_matches_plain(store):
    conn, embedder, _ = store
    queries = bench.load_queries("corpus/queries.json")
    plain, ctx = [], []
    for q in queries:
        gp = bench.resolve_gold_ids(conn, q["gold"], variant="plain")
        gc = bench.resolve_gold_ids(conn, q["gold"], variant="contextual")
        ids_p = [h.id for h in hybrid_search(conn, embedder, q["query"], k=3, variant="plain")]
        ids_c = [h.id for h in hybrid_search(conn, embedder, q["query"], k=3, variant="contextual")]
        plain.append(hit_rate(ids_p, gp, 3))
        ctx.append(hit_rate(ids_c, gc, 3))
    assert mean_metric(ctx) >= mean_metric(plain)

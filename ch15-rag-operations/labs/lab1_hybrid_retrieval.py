"""Listing 15-1: ingest the runbook and postmortem corpus into pgvector, then
show that hybrid retrieval (dense + Postgres tsvector lexical, fused with
Reciprocal Rank Fusion) surfaces an exact-identifier chunk that dense-only ranks
below a semantically generic distractor. Runs in CI against a pgvector service
container, no API key.
"""

from __future__ import annotations

from incidentcopilot import db, ingest
from incidentcopilot.embed import LocalEmbedder
from incidentcopilot.retrieve import dense_search, hybrid_search, lexical_search


def rank_of_gold(hits, gold_heading: str) -> int | str:
    for i, h in enumerate(hits, start=1):
        if h.heading == gold_heading:
            return i
    return "not found"


def main() -> None:
    conn = db.connect()
    db.apply_schema(conn, "schema.sql")
    db.reset(conn)

    embedder = LocalEmbedder()
    docs = ingest.load_docs("corpus")
    chunks = [c for d in docs for c in ingest.chunk_by_heading(d)]
    n = ingest.ingest(conn, embedder, chunks, variant="plain")
    print(f"corpus: {len(docs)} docs, {n} chunks ingested (variant=plain, dim={embedder.DIM})")

    # An on-call engineer knows the incident number and searches by it. The body
    # of every payments incident is near-identical boilerplate, so dense-only
    # retrieval ranks the generic "elevated declines" playbook above the specific
    # incident. The exact identifier INC-4822 lives in the heading, which the
    # lexical leg matches, so hybrid pulls the right chunk to the top.
    query = "INC-4822 payments gateway mitigation"
    gold = "Mitigating incident INC-4822 on the payments gateway"
    print(f'\nquery: "{query}"')
    for label, hits in (
        ("dense-only ", dense_search(conn, embedder, query, k=3)),
        ("lexical-only", lexical_search(conn, query, k=3)),
        ("hybrid (RRF)", hybrid_search(conn, embedder, query, k=3)),
    ):
        top = [f"#{h.id} {h.heading!r}" for h in hits]
        print(f"  {label} top-3: {top}")

    dense_rank = rank_of_gold(dense_search(conn, embedder, query, k=10), gold)
    hybrid_rank = rank_of_gold(hybrid_search(conn, embedder, query, k=10), gold)
    print(f"\ngold for this query = {gold!r}")
    print(f"  dense-only rank of gold: {dense_rank}")
    print(f"  hybrid     rank of gold: {hybrid_rank}   <- hybrid surfaces the exact-identifier chunk")
    conn.close()


if __name__ == "__main__":
    main()

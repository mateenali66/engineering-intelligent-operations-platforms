"""Listing 15-3: A/B the retrieval hit-rate of plain chunks vs context-prepended
chunks (Anthropic's contextual retrieval). The corpus is ingested twice into the
same table under variant='plain' and variant='contextual'. Context strings are
pre-recorded in corpus/contexts.json so the A/B is deterministic and keyless.
Runs in CI, no API key.
"""

from __future__ import annotations

from incidentcopilot import bench, contextual, db, ingest
from incidentcopilot.embed import LocalEmbedder
from incidentcopilot.evaluate import hit_rate, mean_metric
from incidentcopilot.retrieve import hybrid_search


def main() -> None:
    conn = db.connect()
    db.apply_schema(conn, "schema.sql")
    db.reset(conn)
    embedder = LocalEmbedder()
    docs = ingest.load_docs("corpus")
    docs_by_id = {d.doc_id: d for d in docs}
    chunks = [c for d in docs for c in ingest.chunk_by_heading(d)]

    # Plain: embed heading + content as-is.
    n_plain = ingest.ingest(conn, embedder, chunks, variant="plain")

    # Contextual: prepend a per-chunk situating context (baked, or the stub).
    baked = contextual.load_baked_contexts("corpus/contexts.json")
    ctx_texts = []
    for c in chunks:
        ctx = baked.get(contextual.chunk_key(c)) or contextual.deterministic_context_stub(
            docs_by_id[c.doc_id], c
        )
        ctx_texts.append(contextual.prepend_context(c.content, ctx))
    n_ctx = ingest.ingest(conn, embedder, chunks, variant="contextual", embed_texts=ctx_texts)

    print(f"ingested variant=plain       : {n_plain} chunks")
    print(f"ingested variant=contextual  : {n_ctx} chunks")

    queries = bench.load_queries("corpus/queries.json")
    h_plain, h_ctx = [], []
    for q in queries:
        gold_plain = bench.resolve_gold_ids(conn, q["gold"], variant="plain")
        gold_ctx = bench.resolve_gold_ids(conn, q["gold"], variant="contextual")
        ids_plain = [h.id for h in hybrid_search(conn, embedder, q["query"], k=3, variant="plain")]
        ids_ctx = [h.id for h in hybrid_search(conn, embedder, q["query"], k=3, variant="contextual")]
        h_plain.append(hit_rate(ids_plain, gold_plain, 3))
        h_ctx.append(hit_rate(ids_ctx, gold_ctx, 3))

    print(f"mean hit-rate@3  plain      : {mean_metric(h_plain):.2f}")
    print(f"mean hit-rate@3  contextual : {mean_metric(h_ctx):.2f}")
    print(f"contextual retrieval lift   : {mean_metric(h_ctx) - mean_metric(h_plain):+.2f} (absolute) on the fixed query set")
    print("(Anthropic report a 49% reduction in top-20 retrieval failures for contextual")
    print(" embeddings + contextual BM25; this fixture demonstrates the mechanism and the")
    print(" direction of the lift on a small corpus, not the published magnitude.)")
    conn.close()


if __name__ == "__main__":
    main()

"""Listing 15-2: add a cross-encoder reranker on top of the first-stage
retriever and measure the ordering lift on the fixed labeled query set with mean
reciprocal rank. Reranking pulls every query's gold chunk to the top, lifting
both the dense and the hybrid first stage to a perfect MRR. The reranker is
FlashRank (ONNX, CPU); production options are Cohere Rerank 3.5 / bge-reranker.
Runs in CI, no API key.
"""

from __future__ import annotations

from incidentcopilot import bench, db, ingest
from incidentcopilot.embed import LocalEmbedder
from incidentcopilot.evaluate import mean_metric, reciprocal_rank
from incidentcopilot.rerank import FlashRankReranker
from incidentcopilot.retrieve import dense_search, hybrid_search


def main() -> None:
    conn = db.connect()
    db.apply_schema(conn, "schema.sql")
    db.reset(conn)
    embedder = LocalEmbedder()
    docs = ingest.load_docs("corpus")
    chunks = [c for d in docs for c in ingest.chunk_by_heading(d)]
    ingest.ingest(conn, embedder, chunks, variant="plain")

    reranker = FlashRankReranker()
    queries = bench.load_queries("corpus/queries.json")

    dense_mrr, dense_rr, hybrid_mrr, hybrid_rr = [], [], [], []
    for q in queries:
        gold = bench.resolve_gold_ids(conn, q["gold"], variant="plain")
        dense = dense_search(conn, embedder, q["query"], k=10)
        hybrid = hybrid_search(conn, embedder, q["query"], k=10)
        dense_mrr.append(reciprocal_rank([h.id for h in dense], gold))
        hybrid_mrr.append(reciprocal_rank([h.id for h in hybrid], gold))
        dense_rr.append(reciprocal_rank([h.id for h in reranker.rerank(conn, q["query"], dense, top_k=10)], gold))
        hybrid_rr.append(reciprocal_rank([h.id for h in reranker.rerank(conn, q["query"], hybrid, top_k=10)], gold))

    print(f"labeled queries: {len(queries)}")
    print(f"MRR  dense  first stage          : {mean_metric(dense_mrr):.3f}")
    print(f"MRR  dense  + FlashRank rerank    : {mean_metric(dense_rr):.3f}")
    print(f"MRR  hybrid first stage          : {mean_metric(hybrid_mrr):.3f}")
    print(f"MRR  hybrid + FlashRank rerank    : {mean_metric(hybrid_rr):.3f}")
    print(f"rerank MRR lift over hybrid       : {mean_metric(hybrid_rr) - mean_metric(hybrid_mrr):+.3f}")
    print("(both first stages leave a few queries with the gold chunk below rank 1;")
    print(" the cross-encoder reorders the candidates and pulls them to the top.)")
    conn.close()


if __name__ == "__main__":
    main()

"""Reranking the hybrid candidate list.

CI default is FlashRank's smallest cross-encoder (ms-marco-TinyBERT-L-2-v2, a
~3.3 MB ONNX model, CPU). It re-scores the candidates by true query-document
relevance, which a first-stage retriever optimized for recall cannot do. The
production options are Cohere Rerank 3.5 (managed API) and bge-reranker (local,
heavier), shown as shapes only.
"""

from __future__ import annotations

from functools import lru_cache

import psycopg

from .types import Hit


class FlashRankReranker:
    """FlashRank cross-encoder reranker, ONNX, CPU. The CI default."""

    MODEL = "ms-marco-TinyBERT-L-2-v2"

    def __init__(self) -> None:
        self._ranker = _load_ranker(self.MODEL)

    def rerank(
        self,
        conn: psycopg.Connection,
        query: str,
        hits: list[Hit],
        top_k: int = 5,
    ) -> list[Hit]:
        """Re-score hits by cross-encoder relevance and return the top_k."""
        if not hits:
            return []
        from flashrank import RerankRequest

        bodies = _fetch_content(conn, [h.id for h in hits])
        passages = [
            {"id": h.id, "text": f"{h.heading}\n{bodies.get(h.id, '')}"} for h in hits
        ]
        ranked = self._ranker.rerank(RerankRequest(query=query, passages=passages))
        by_id = {h.id: h for h in hits}
        out: list[Hit] = []
        for r in ranked[:top_k]:
            h = by_id[r["id"]]
            out.append(Hit(id=h.id, doc_id=h.doc_id, heading=h.heading, score=float(r["score"])))
        return out


@lru_cache(maxsize=2)
def _load_ranker(model_name: str):
    from flashrank import Ranker

    return Ranker(model_name=model_name)


def _fetch_content(conn: psycopg.Connection, ids: list[int]) -> dict[int, str]:
    rows = conn.execute(
        "SELECT id, content FROM chunks WHERE id = ANY(%s)", (ids,)
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def production_cohere_reranker():  # pragma: no cover - validation-only
    """Shape only: Cohere Rerank 3.5 (rerank-v3.5). Needs COHERE_API_KEY.

        import cohere
        co = cohere.ClientV2()
        resp = co.rerank(
            model="rerank-v3.5", query=query, documents=docs, top_n=top_k
        )
        return [docs[r.index] for r in resp.results]

    Cohere now also ships Rerank 4.0; 3.5 remains available. Not run in CI; the
    FlashRank ONNX reranker is the CI default.
    """
    raise NotImplementedError("production reranker is validation-only; see docstring")

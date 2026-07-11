# Chapter 15: RAG Architectures for Operations

Companion code for the Incident Copilot, a retrieval-augmented assistant over
runbooks and postmortems on Postgres + pgvector. The deterministic pipeline runs
headless in CI with no API key and no GPU; the LLM answer generation, the live
Ragas / TruLens judges, and the LangGraph agent are validation-only.

## Listing-to-file map

| Listing | File | What it shows |
|---|---|---|
| 15-1 | `schema.sql` (`rrf_hybrid` function) | hybrid retrieval: a dense leg, a Postgres `tsvector` lexical leg, fused with Reciprocal Rank Fusion in one query |
| 15-2 | `incidentcopilot/rerank.py` (`FlashRankReranker.rerank`) | a cross-encoder reranker re-scoring the first-stage candidates |
| 15-3 | `labs/lab3_contextual_ab.py` (contextual ingest block) | re-ingesting the corpus with a per-chunk situating context for the A/B |
| 15-4 | `labs/lab4_eval_gate.py` (`gate`) | a deterministic faithfulness + context-precision gate |

## Layout

```
incidentcopilot/        the package: db, embed, ingest, retrieve, rerank,
                        contextual, evaluate, bench (+ eval_ragas, agent = validation-only)
labs/                   lab1 hybrid retrieval, lab2 rerank MRR, lab3 contextual A/B, lab4 eval gate
corpus/                 9 synthetic runbooks + postmortems, queries.json, contexts.json
tests/                  pytest: retrieval, rerank, contextual, eval gate
schema.sql              chunks table + GIN/HNSW indexes + the rrf_hybrid function
run_smoke.py            headless end-to-end; prints "smoke: ok"
requirements.txt        pinned, CI-tested (Python 3.12)
```

## Run

Bring up Postgres + pgvector with the same image CI uses, then run the labs
against it. No API key, no GPU.

```bash
docker run -d --name ch15pg -p 5432:5432 \
  -e POSTGRES_USER=copilot -e POSTGRES_PASSWORD=copilot -e POSTGRES_DB=incidentcopilot \
  pgvector/pgvector:pg17

python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export PGHOST=localhost PGPORT=5432 PGUSER=copilot PGPASSWORD=copilot PGDATABASE=incidentcopilot
python run_smoke.py            # prints "smoke: ok"
python -m pytest tests/ -q     # 5 passed
python labs/lab1_hybrid_retrieval.py   # and lab2, lab3, lab4
```

The first run downloads the local embedding model (`all-MiniLM-L6-v2`, ~90 MB)
and the FlashRank reranker (`ms-marco-TinyBERT-L-2-v2`, ~3.3 MB ONNX).

## Pinned versions (Python 3.12)

`pgvector/pgvector:pg17` (extension 0.8.3), `psycopg[binary]==3.3.4`,
`pgvector==0.4.2` (client adapter), `sentence-transformers==5.6.0`,
`flashrank==0.2.10`, `trulens-core==2.8.1`, `pytest==8.4.2`. Ragas is NOT
installed: `ragas==0.4.3` cannot be imported against langchain 1.x (it loads a
removed `langchain_community.chat_models.vertexai`), so `incidentcopilot/eval_ragas.py`
is `py_compile`-checked only and documents the production Ragas path. Production
embeddings (`text-embedding-3-large`), reranker (Cohere Rerank), context writer,
and the LangGraph `create_agent` loop need a key and are validation-only.

## What CI proves (and what it does not)

The `ch15-rag` job runs against a `pgvector/pgvector:pg17` service container:
schema + ingest, dense retrieval, Postgres lexical retrieval, RRF fusion, the
FlashRank reranker, the contextual A/B, and the deterministic eval gate all run
for real. The LLM answer generation, the live Ragas faithfulness judge, the
TruLens feedback judges, and the agent loop are validation-only (compile-checked,
never executed without a key).

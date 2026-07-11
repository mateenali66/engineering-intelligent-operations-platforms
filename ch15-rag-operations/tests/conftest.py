"""Shared fixtures: one ingested pgvector store for the retrieval tests."""

from __future__ import annotations

import pytest

from incidentcopilot import contextual, db, ingest
from incidentcopilot.embed import LocalEmbedder


@pytest.fixture(scope="session")
def store():
    conn = db.connect()
    db.apply_schema(conn, "schema.sql")
    db.reset(conn)
    embedder = LocalEmbedder()
    docs = ingest.load_docs("corpus")
    docs_by_id = {d.doc_id: d for d in docs}
    chunks = [c for d in docs for c in ingest.chunk_by_heading(d)]
    ingest.ingest(conn, embedder, chunks, variant="plain")

    baked = contextual.load_baked_contexts("corpus/contexts.json")
    ctx_texts = []
    for c in chunks:
        ctx = baked.get(contextual.chunk_key(c)) or contextual.deterministic_context_stub(
            docs_by_id[c.doc_id], c
        )
        ctx_texts.append(contextual.prepend_context(f"{c.heading}\n{c.content}", ctx))
    ingest.ingest(conn, embedder, chunks, variant="contextual", embed_texts=ctx_texts)

    yield conn, embedder, chunks
    conn.close()

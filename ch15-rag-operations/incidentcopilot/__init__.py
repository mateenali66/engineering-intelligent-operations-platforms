"""Incident Copilot: a RAG assistant over runbooks and postmortems on boring
infrastructure (Postgres + pgvector). Companion code for Chapter 15.

The deterministic pipeline (ingest, dense + tsvector lexical retrieval, RRF
fusion, local reranking, hit-rate / precision measurement, a deterministic eval
gate) runs headless in CI with no API key and no GPU. The LLM answer generation,
the live Ragas / TruLens judges, the production embeddings / reranker, and the
LangGraph agentic loop are validation-only and clearly marked.
"""

from .types import Chunk, Doc, Hit

__all__ = ["Chunk", "Doc", "Hit"]

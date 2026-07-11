"""Contextual retrieval (Anthropic, 2024): prepend a short situating context to
each chunk before embedding and lexical indexing, so a chunk that says "exit
code 137" still retrieves when the query names the service the chunk belongs to.

In production an LLM writes the context after reading the whole document. Here
the context strings are pre-recorded in corpus/contexts.json so the A/B is
deterministic and runs in CI with no API key. A deterministic stub synthesizes
an equivalent context from the document title and heading when a key is missing.
"""

from __future__ import annotations

import json
from pathlib import Path

from .types import Chunk, Doc


def load_baked_contexts(path: str = "corpus/contexts.json") -> dict[str, str]:
    """Load the pre-recorded chunk_key -> context map."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data["contexts"]


def chunk_key(chunk: Chunk) -> str:
    """The contexts.json key for a chunk: 'doc_id::heading'."""
    return f"{chunk.doc_id}::{chunk.heading}"


def deterministic_context_stub(doc: Doc, chunk: Chunk) -> str:
    """Synthesize a situating context with no LLM, for reproducibility.

    Used as a fallback when a chunk has no baked context. It mirrors what the
    production LLM writer produces: one sentence naming the document and section.
    """
    return f"From the document titled {doc.title}: the section on {chunk.heading}."


def prepend_context(chunk_text: str, context: str) -> str:
    """Anthropic's contextual chunk = context sentence then the original chunk."""
    return f"{context}\n\n{chunk_text}"


def production_context_writer():  # pragma: no cover - validation-only
    """Shape only: per-chunk situating context via an LLM over the full document.

        prompt = CONTEXT_PROMPT.format(document=full_doc, chunk=chunk_text)
        context = chat_model.complete(prompt)   # 1-2 sentences, needs a key
        return prepend_context(chunk_text, context)

    Anthropic mitigate the per-chunk LLM cost with prompt caching of the shared
    document. Not run in CI; contexts.json is the CI stand-in.
    """
    raise NotImplementedError("production context writer is validation-only")

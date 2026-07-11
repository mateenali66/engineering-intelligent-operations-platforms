"""Small dataclasses shared across the package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Doc:
    """A source document loaded from the corpus."""

    doc_id: str
    title: str
    path: str


@dataclass(frozen=True)
class Chunk:
    """A heading-delimited slice of a document, before embedding."""

    doc_id: str
    heading: str
    content: str


@dataclass(frozen=True)
class Hit:
    """One retrieved chunk and its score under whichever retriever produced it."""

    id: int
    doc_id: str
    heading: str
    score: float

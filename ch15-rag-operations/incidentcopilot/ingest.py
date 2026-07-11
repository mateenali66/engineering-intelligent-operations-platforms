"""Load the corpus, chunk by markdown heading, embed, and insert.

Runbooks and postmortems are markdown with an H1 title and H2 sections. Each H2
section becomes one chunk, which is why structure-aware chunking suits ops docs:
a heading like "Resolving ORA-00600 internal error on the billing DB" is a
natural retrieval unit and carries the identifier token that hybrid search needs.
"""

from __future__ import annotations

import re
from pathlib import Path

import psycopg

from .types import Chunk, Doc


def load_docs(corpus_dir: str = "corpus") -> list[Doc]:
    """Discover every .md file under corpus/runbooks and corpus/postmortems."""
    base = Path(corpus_dir)
    docs: list[Doc] = []
    for path in sorted(base.glob("**/*.md")):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
        title = m.group(1).strip() if m else path.stem
        docs.append(Doc(doc_id=path.stem, title=title, path=str(path)))
    return docs


def chunk_by_heading(doc: Doc) -> list[Chunk]:
    """Split a document into one chunk per H2 section."""
    text = Path(doc.path).read_text(encoding="utf-8")
    chunks: list[Chunk] = []
    parts = re.split(r"^##\s+", text, flags=re.MULTILINE)
    for part in parts[1:]:  # parts[0] is the H1 title block, not a chunk
        lines = part.splitlines()
        heading = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        if body:
            chunks.append(Chunk(doc_id=doc.doc_id, heading=heading, content=body))
    return chunks


def ingest(
    conn: psycopg.Connection,
    embedder,
    chunks: list[Chunk],
    variant: str = "plain",
    embed_texts: list[str] | None = None,
) -> int:
    """Embed and insert chunks under the given variant.

    embed_texts, when given, is the text actually embedded and indexed (used by
    the contextual A/B to embed context-prepended text); it defaults to the chunk
    body only. We embed the body, not the heading: the heading is a strong lexical
    signal (weighted 'A' in the tsvector), and embedding it would let a rare
    identifier in the heading leak into the dense vector, masking the exact-token
    weakness that hybrid search exists to fix.
    """
    if embed_texts is None:
        embed_texts = [c.content for c in chunks]
    vectors = embedder.encode(embed_texts)
    with conn.cursor() as cur:
        for chunk, text, vec in zip(chunks, embed_texts, vectors):
            # heading drives the tsvector weight 'A'; for the contextual variant the
            # prepended context is folded into content so it reaches lexical too.
            heading = chunk.heading
            content = text if variant == "contextual" else chunk.content
            cur.execute(
                "INSERT INTO chunks (doc_id, heading, content, variant, embedding) "
                "VALUES (%s, %s, %s, %s, %s)",
                (chunk.doc_id, heading, content, variant, vec),
            )
    return len(chunks)

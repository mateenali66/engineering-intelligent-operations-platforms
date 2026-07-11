"""Embedding models.

CI default is a small local model (all-MiniLM-L6-v2, 384-dim, CPU) so the labs
run with no API key and no GPU. The production option is text-embedding-3-large
(3072-dim, API), shown as a shape only. Switching between them changes the
vector(N) column width, so it means re-embedding the whole corpus: embeddings
are a commitment, not a config flag.
"""

from __future__ import annotations

from functools import lru_cache


class LocalEmbedder:
    """sentence-transformers all-MiniLM-L6-v2, 384-dim, CPU. The CI default."""

    DIM = 384
    MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self) -> None:
        self._model = _load_model(self.MODEL)

    def encode(self, texts: list[str]) -> list:
        """Return one 384-dim vector per input text, normalized for cosine.

        Returns numpy arrays: the pgvector psycopg adapter sends a numpy array as
        a real `vector`, while a plain Python list is sent as `double precision[]`
        and the `<=>` operator then has no matching type.
        """
        vectors = self._model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return [v for v in vectors]


@lru_cache(maxsize=2)
def _load_model(name: str):
    # Imported lazily so importing this module does not pull torch unless an
    # embedder is actually constructed.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(name)


def production_openai_embedder():  # pragma: no cover - validation-only
    """Shape only: text-embedding-3-large -> vector(3072). Needs OPENAI_API_KEY.

        from openai import OpenAI
        client = OpenAI()
        resp = client.embeddings.create(
            model="text-embedding-3-large", input=texts
        )
        return [d.embedding for d in resp.data]  # 3072-dim

    Moving to this model widens the chunks.embedding column from vector(384) to
    vector(3072) and requires re-embedding every chunk. This path is not run in
    CI; the local 384-dim embedder is the CI default.
    """
    raise NotImplementedError("production embedder is validation-only; see docstring")

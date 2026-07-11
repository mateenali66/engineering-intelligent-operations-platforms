-- schema.sql : Incident Copilot store. Postgres 17 + pgvector 0.8.3.
-- N=384 in CI (all-MiniLM-L6-v2). Production text-embedding-3-large is vector(3072),
-- which means re-embedding the whole corpus and altering this column: embeddings
-- are a commitment, not a config flag.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doc_id      text        NOT NULL,
    heading     text        NOT NULL,
    content     text        NOT NULL,
    -- variant marks which ingest produced this row, for the A/B in Listing 15-3:
    --   'plain'      = content embedded as-is
    --   'contextual' = a per-chunk context sentence prepended before embedding
    variant     text        NOT NULL DEFAULT 'plain',
    embedding   vector(384) NOT NULL,
    -- generated lexical column: heading is weighted 'A', content 'B' so a heading
    -- token match (often the error code) ranks above a body mention.
    fts         tsvector GENERATED ALWAYS AS (
                    setweight(to_tsvector('english', coalesce(heading, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(content, '')), 'B')
                ) STORED
);

CREATE INDEX IF NOT EXISTS chunks_fts_gin    ON chunks USING gin (fts);
CREATE INDEX IF NOT EXISTS chunks_embed_hnsw ON chunks
       USING hnsw (embedding vector_cosine_ops);

-- Reciprocal Rank Fusion as a SQL function so fusion happens in one round trip.
-- RRF score = sum over lists of 1 / (k + rank); k=60 is the canonical constant.
-- Each leg contributes its own top-N ranked list; we fuse and return the top-k ids.
CREATE OR REPLACE FUNCTION rrf_hybrid(
    query_embedding vector(384),
    query_text      text,
    target_variant  text DEFAULT 'plain',
    n_each          int  DEFAULT 20,
    rrf_k           int  DEFAULT 60,
    top_k           int  DEFAULT 10
) RETURNS TABLE (id bigint, doc_id text, heading text, rrf_score double precision)
LANGUAGE sql STABLE AS $$
WITH dense AS (
    SELECT c.id,
           row_number() OVER (ORDER BY c.embedding <=> query_embedding, c.id) AS rnk
    FROM chunks c
    WHERE c.variant = target_variant
    ORDER BY c.embedding <=> query_embedding, c.id
    LIMIT n_each
),
lexical AS (
    SELECT c.id,
           row_number() OVER (
               ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) DESC, c.id
           ) AS rnk
    FROM chunks c
    WHERE c.variant = target_variant
      AND c.fts @@ websearch_to_tsquery('english', query_text)
    ORDER BY ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) DESC, c.id
    LIMIT n_each
),
fused AS (
    SELECT id, 1.0 / (rrf_k + rnk) AS s FROM dense
    UNION ALL
    SELECT id, 1.0 / (rrf_k + rnk) AS s FROM lexical
)
-- tiebreak on id so equal rrf_score rows order deterministically (reproducible ranks)
SELECT f.id, c.doc_id, c.heading, SUM(f.s) AS rrf_score
FROM fused f JOIN chunks c ON c.id = f.id
GROUP BY f.id, c.doc_id, c.heading
ORDER BY rrf_score DESC, f.id
LIMIT top_k;
$$;

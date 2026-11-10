-- Migration 0001: PostgreSQL Full-Text Search index on artifact

CREATE INDEX IF NOT EXISTS idx_artifact_fts ON artifact USING gin (
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(body_redacted, ''))
);

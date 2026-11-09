-- Migration 0001: SQLite FTS5 index and synchronization triggers for artifact

CREATE VIRTUAL TABLE IF NOT EXISTS artifact_fts USING fts5(
    title,
    body_redacted,
    content='artifact',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS artifact_ai AFTER INSERT ON artifact BEGIN
    INSERT INTO artifact_fts(rowid, title, body_redacted)
    VALUES (new.rowid, new.title, new.body_redacted);
END;

CREATE TRIGGER IF NOT EXISTS artifact_ad AFTER DELETE ON artifact BEGIN
    INSERT INTO artifact_fts(artifact_fts, rowid, title, body_redacted)
    VALUES ('delete', old.rowid, old.title, old.body_redacted);
END;

CREATE TRIGGER IF NOT EXISTS artifact_au AFTER UPDATE ON artifact BEGIN
    INSERT INTO artifact_fts(artifact_fts, rowid, title, body_redacted)
    VALUES ('delete', old.rowid, old.title, old.body_redacted);
    INSERT INTO artifact_fts(rowid, title, body_redacted)
    VALUES (new.rowid, new.title, new.body_redacted);
END;


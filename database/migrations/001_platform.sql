-- Platform layer: users, guest trials, usage counters, and row ownership.
-- Additive only. Existing columns and indexes are untouched so the RAG
-- pipeline and evidence sidecars keep working unchanged.

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    auth_subject TEXT NOT NULL UNIQUE,
    email TEXT,
    created_at TEXT NOT NULL,
    last_seen_at TEXT
);

CREATE TABLE IF NOT EXISTS guest_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_seen_at TEXT,
    pdf_count INTEGER NOT NULL DEFAULT 0,
    question_count INTEGER NOT NULL DEFAULT 0,
    migrated_to_user_id TEXT
);

-- Question usage per billing-style period. Guests use period 'trial' so the
-- same table serves both tiers.
CREATE TABLE IF NOT EXISTS usage_counters (
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    period TEXT NOT NULL,
    question_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (actor_type, actor_id, period)
);

-- Ownership columns are added by db.init_db() via ALTER TABLE guards,
-- because SQLite has no ADD COLUMN IF NOT EXISTS.
--   documents.owner_type      TEXT  'guest' | 'user'
--   documents.owner_id        TEXT
--   conversations.owner_type  TEXT
--   conversations.owner_id    TEXT

CREATE INDEX IF NOT EXISTS idx_documents_owner
    ON documents (owner_type, owner_id);

CREATE INDEX IF NOT EXISTS idx_conversations_owner
    ON conversations (owner_type, owner_id);

-- Operator telemetry. Additive only; RAG tables stay untouched.

CREATE TABLE IF NOT EXISTS app_events (
    event_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    actor_type TEXT,
    actor_id TEXT,
    route TEXT,
    kind TEXT NOT NULL,
    provider TEXT,
    category TEXT,
    status_code INTEGER,
    message TEXT,
    document_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_app_events_created
    ON app_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_app_events_kind
    ON app_events (kind, created_at DESC);

CREATE TABLE IF NOT EXISTS provider_snapshots (
    provider TEXT PRIMARY KEY,
    updated_at TEXT NOT NULL,
    remaining_requests INTEGER,
    limit_requests INTEGER,
    remaining_tokens INTEGER,
    limit_tokens INTEGER,
    reset_requests TEXT,
    reset_tokens TEXT,
    tokens_used_today INTEGER NOT NULL DEFAULT 0,
    requests_today INTEGER NOT NULL DEFAULT 0,
    usage_day TEXT,
    last_error TEXT
);

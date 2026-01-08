CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    user_id TEXT,
    chat_id TEXT,
    input_path TEXT NOT NULL,
    output_path TEXT,
    status TEXT NOT NULL,
    profile TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    input_bytes INTEGER DEFAULT 0,
    output_bytes INTEGER DEFAULT 0,
    duration_seconds INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    error_message TEXT,
    download_token TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_download_token ON jobs(download_token);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id TEXT PRIMARY KEY,
    profile TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
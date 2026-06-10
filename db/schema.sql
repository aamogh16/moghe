-- Conversation history — each row is one message turn.
-- role is 'user' or 'assistant'.
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT    NOT NULL,
    role       TEXT    NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT    NOT NULL,
    ts         DATETIME DEFAULT (datetime('now'))
);

-- Extracted action items (TODO/task tracking — wired in later).
CREATE TABLE IF NOT EXISTS action_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT    NOT NULL,
    description TEXT    NOT NULL,
    status      TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done', 'cancelled')),
    created_at  DATETIME DEFAULT (datetime('now')),
    due_at      DATETIME
);

-- Actions that need explicit approval before execution (e.g. "send this email").
CREATE TABLE IF NOT EXISTS pending_approvals (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      TEXT    NOT NULL,
    action_type  TEXT    NOT NULL,
    payload_json TEXT    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at   DATETIME DEFAULT (datetime('now'))
);

"""004 审计日志表（谁、何时、对什么、做了什么、来源 IP）。"""
VERSION = 4
NAME = "audit_log"

DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    username    TEXT,
    action      TEXT NOT NULL,
    object_type TEXT,
    object_id   TEXT,
    detail      TEXT,
    ip          TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log (user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log (action);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at);
"""


def up(conn):
    conn.executescript(DDL)

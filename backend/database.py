import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'positions.db')


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword_id INTEGER NOT NULL,
            position INTEGER,
            url_found TEXT,
            checked_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (keyword_id) REFERENCES keywords(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_positions_keyword ON positions(keyword_id);
        CREATE INDEX IF NOT EXISTS idx_positions_checked ON positions(checked_at);
    """)
    conn.commit()
    conn.close()


def get_setting(key):
    conn = get_db()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else None


def set_setting(key, value):
    conn = get_db()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value)
    )
    conn.commit()
    conn.close()


def get_keywords():
    conn = get_db()
    rows = conn.execute("SELECT id, keyword, created_at FROM keywords ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_keyword(keyword):
    conn = get_db()
    try:
        conn.execute("INSERT INTO keywords (keyword) VALUES (?)", (keyword.strip(),))
        conn.commit()
        kid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return kid
    except sqlite3.IntegrityError:
        conn.close()
        return None


def delete_keyword(keyword_id):
    conn = get_db()
    conn.execute("DELETE FROM positions WHERE keyword_id = ?", (keyword_id,))
    conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
    conn.commit()
    conn.close()


def save_position(keyword_id, position, url_found):
    conn = get_db()
    conn.execute(
        "INSERT INTO positions (keyword_id, position, url_found) VALUES (?, ?, ?)",
        (keyword_id, position, url_found)
    )
    conn.commit()
    conn.close()


def get_latest_positions():
    conn = get_db()
    rows = conn.execute("""
        SELECT k.id, k.keyword, p.position, p.url_found, p.checked_at
        FROM keywords k
        LEFT JOIN positions p ON p.id = (
            SELECT p2.id FROM positions p2
            WHERE p2.keyword_id = k.id
            ORDER BY p2.checked_at DESC LIMIT 1
        )
        ORDER BY k.id
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_history(keyword_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT position, url_found, checked_at
        FROM positions
        WHERE keyword_id = ?
        ORDER BY checked_at ASC
    """, (keyword_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

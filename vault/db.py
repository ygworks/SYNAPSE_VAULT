import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(r"E:\SYNAPSE VAULT\SYNAPSE_VAULT\data\vault_core.db").resolve()
os.makedirs(DB_PATH.parent, exist_ok=True)

def init_vault_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS vault_items (
                uid TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                year INTEGER DEFAULT 0,
                release_date TEXT,
                studio TEXT,
                file_path TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                poster_path TEXT,
                plot TEXT,
                tags TEXT,
                actors_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS vault_items_fts USING fts5(
                uid UNINDEXED,
                code,
                title,
                artist,
                studio,
                tags,
                plot,
                tokenize = 'unicode61'
            );
        """)
    conn.close()

@contextmanager
def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

init_vault_db()

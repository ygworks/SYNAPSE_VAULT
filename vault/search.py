import re
from typing import List, Dict, Any
from vault.db import get_db

def search_vault(keyword: str, limit: int = 100) -> List[Dict[str, Any]]:
    clean = re.sub(r"[^\w\s\-\.]", "", keyword).strip()
    if not clean:
        return []
    
    no_space = clean.replace(" ", "")
    words = clean.split()
    fts_q = " AND ".join([f'"{w}"*' for w in words])
    
    sql = """
        SELECT v.*, bm25(vault_items_fts, 10.0, 5.0, 7.0, 2.0, 3.0, 1.0) AS score
        FROM vault_items_fts f
        JOIN vault_items v ON f.uid = v.uid
        WHERE vault_items_fts MATCH ?
           OR REPLACE(v.title, ' ', '') LIKE ?
           OR REPLACE(v.artist, ' ', '') LIKE ?
           OR v.code LIKE ?
        ORDER BY score ASC, v.year DESC LIMIT ?
    """
    params = [fts_q, f"%{no_space}%", f"%{no_space}%", f"%{clean}%", limit]
    with get_db() as conn:
        cursor = conn.execute(sql, params)
        return [dict(r) for r in cursor.fetchall()]

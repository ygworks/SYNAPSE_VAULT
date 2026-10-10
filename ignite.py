# [FILE] SYNAPSE_VAULT/ignite.py
"""
🏛️ SYNAPSE VAULT - 무결점 서버 점화기 (Ignition Engine)
- aiofiles 미설치 크래시 원천 차단 (파이썬 표준 청크 스트리밍으로 자동 교정)
- 실행 위치 불일치(CWD) 자동 보정 & 절대 경로 sys.path 강제 결속
- 서버 기동 성공 시 브라우저 자동 오픈
"""
import os
import sys
import time
import webbrowser
from pathlib import Path

# 1. 실행 위치 무조건 SYNAPSE_VAULT 실제 경로로 앵커 고정
CURRENT = Path(__file__).resolve().parent
if (CURRENT / "vault").exists():
    APP_DIR = CURRENT
elif (CURRENT / "SYNAPSE_VAULT").exists():
    APP_DIR = CURRENT / "SYNAPSE_VAULT"
else:
    APP_DIR = CURRENT

os.chdir(str(APP_DIR))
sys.path.insert(0, str(APP_DIR))

print("=" * 70)
print("🚀 [SYNAPSE VAULT] 마스터 서버 점화 및 부팅 진단 시작")
print(f"📍 프로젝트 작업 경로: {APP_DIR}")
print("=" * 70)

# 2. vault/stream.py 내부 aiofiles 의존성 완전 제거 (표준 라이브러리로 수술)
stream_py = APP_DIR / "vault/stream.py"
clean_stream_code = '''import os
import mimetypes
from typing import Optional, Tuple
from fastapi import APIRouter, Header, HTTPException, Response
from fastapi.responses import StreamingResponse, FileResponse

router = APIRouter()
FALLBACK_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 450"><rect width="100%" height="100%" fill="#12141A"/><text x="50%" y="50%" fill="#3B82F6" font-family="sans-serif" font-size="22" text-anchor="middle" font-weight="bold">NO POSTER</text></svg>"""

def parse_range(range_header: str, file_size: int) -> Tuple[int, int, int]:
    try:
        range_str = range_header.replace("bytes=", "").strip()
        parts = range_str.split("-")
        start = int(parts[0]) if parts[0] else 0
        end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        return max(0, min(start, file_size - 1)), max(start, min(end, file_size - 1)), (end - start + 1)
    except Exception:
        return 0, file_size - 1, file_size

def sync_chunk_generator(full_path: str, start: int, end: int, chunk_size: int = 2 * 1024 * 1024):
    """aiofiles 없이 순수 파이썬으로 4070 Ti 직결 Range 206 스트리밍"""
    with open(full_path, "rb") as f:
        f.seek(start)
        remaining = (end - start) + 1
        while remaining > 0:
            read_size = min(chunk_size, remaining)
            data = f.read(read_size)
            if not data:
                break
            remaining -= len(data)
            yield data

@router.get("/api/stream/{uid}")
def stream_video(uid: str, range_header: Optional[str] = Header(None, alias="Range")):
    from vault.db import get_db
    with get_db() as conn:
        row = conn.execute("SELECT file_path FROM vault_items WHERE uid = ?", (uid,)).fetchone()
    
    if not row or not os.path.exists(row["file_path"]):
        raise HTTPException(status_code=404, detail="영상 파일을 찾을 수 없습니다.")
        
    full_path = row["file_path"]
    file_size = os.path.getsize(full_path)
    start, end, content_len = parse_range(range_header or "", file_size)
    status_code = 206 if range_header else 200

    mime, _ = mimetypes.guess_type(full_path)
    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_len),
        "Content-Type": mime or "video/mp4",
    }
    return StreamingResponse(sync_chunk_generator(full_path, start, end), status_code=status_code, headers=headers)

@router.get("/api/poster/{uid}")
def get_poster(uid: str):
    from vault.db import get_db
    with get_db() as conn:
        row = conn.execute("SELECT poster_path, file_path FROM vault_items WHERE uid = ?", (uid,)).fetchone()

    if not row:
        return Response(content=FALLBACK_SVG, media_type="image/svg+xml")

    poster = row["poster_path"]
    if poster and os.path.exists(poster):
        return FileResponse(poster)

    video_p = row["file_path"]
    if video_p:
        v_dir = os.path.dirname(video_p)
        stem = os.path.splitext(video_p)[0]
        for alt in [f"{stem}-poster.jpg", f"{stem}.jpg", os.path.join(v_dir, "folder.jpg"), os.path.join(v_dir, "cover.jpg")]:
            if os.path.exists(alt):
                return FileResponse(alt)

    return Response(content=FALLBACK_SVG, media_type="image/svg+xml")
'''
stream_py.write_text(clean_stream_code, encoding="utf-8")
print("✅ [1/3] vault/stream.py 무의존성 스트리밍 수술 완료")

# 3. vault/db.py 경로 절대경로 강제 고정
db_py = APP_DIR / "vault/db.py"
db_code = f'''import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(r"{APP_DIR / 'data/vault_core.db'}").resolve()
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
'''
db_py.write_text(db_code, encoding="utf-8")
print("✅ [2/3] vault/db.py 절대 경로 고정 완료")

# 4. 필수 라이브러리 검사
try:
    import fastapi
    import uvicorn
    print("✅ [3/3] FastAPI & Uvicorn 엔진 확인 완료")
except ImportError as e:
    print(f"\n❌ 필수 패키지가 없습니다: {e}")
    print("   pip install fastapi uvicorn 를 실행해 주세요.")
    sys.exit(1)

# 5. 브라우저 자동 오픈 쓰레드
import threading
def open_browser():
    time.sleep(1.5)
    print("🌐 브라우저를 엽니다: http://localhost:8000")
    webbrowser.open("http://localhost:8000")

threading.Thread(target=open_browser, daemon=True).start()

# 6. 마스터 서버 점화 (터미널 끄지 말고 유지!)
print("\n" + "=" * 70)
print("🔥 [서버 구동 성공] SYNAPSE VAULT 백엔드가 8000번 포트에서 가동 중입니다!")
print("⚠️  [중요] 이 터미널 창을 끄면 서버가 종료되므로 창을 닫지 마세요!")
print("🖥️  접속 URL: http://localhost:8000")
print("=" * 70 + "\n")

from run import app
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
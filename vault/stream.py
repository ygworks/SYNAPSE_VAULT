import os
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

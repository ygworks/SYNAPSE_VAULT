import os
import math
import mimetypes
from typing import Optional
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from vault.db import get_db

router = APIRouter(prefix="/api/vault", tags=["Vault & Canvas API"])

FALLBACK_SVG = b"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 450"><rect width="100%" height="100%" fill="#12141A"/><text x="50%" y="50%" fill="#3B82F6" font-family="sans-serif" font-size="22" text-anchor="middle" font-weight="bold">NO POSTER</text></svg>"""

@router.get("/stats")
async def get_vault_stats():
    """라이브러리 전체 통계"""
    with get_db() as conn:
        total_works = conn.execute("SELECT COUNT(*) FROM vault_items").fetchone()[0]
        total_actors = conn.execute("SELECT COUNT(DISTINCT artist) FROM vault_items WHERE artist != '' AND artist != 'UNKNOWN'").fetchone()[0]
    return {"total_works": total_works, "total_actors": total_actors}

@router.get("/actors")
async def get_top_actors(limit: int = 150):
    """소장 작품 수가 많은 배우 랭킹 목록 (드롭다운 자동 완성용)"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT artist, COUNT(*) as work_count
            FROM vault_items
            WHERE artist != '' AND artist != 'UNKNOWN'
            GROUP BY artist
            ORDER BY work_count DESC, artist ASC
            LIMIT ?
        """, (limit,)).fetchall()
    return [{"name": r["artist"], "count": r["work_count"]} for r in rows]

@router.get("/constellation/{artist_name}")
async def get_actor_constellation(artist_name: str, limit: int = 35):
    """배우 중심 별자리 성좌 노드 & 베지에 엣지 좌표 계산"""
    with get_db() as conn:
        rows = conn.execute("""
            SELECT uid, code, title, artist, year, studio, plot, tags, poster_path, file_path
            FROM vault_items
            WHERE artist = ? OR artist LIKE ? OR code LIKE ?
            ORDER BY year DESC, code ASC
            LIMIT ?
        """, (artist_name, f"%{artist_name}%", f"%{artist_name}%", limit)).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail="해당 배우의 작품이 없습니다.")

    cx, cy = 600.0, 450.0
    nodes = []
    edges = []

    # 1. 중심 배우 핵(Core) 노드
    actor_node_id = f"core_{artist_name}"
    nodes.append({
        "id": actor_node_id,
        "title": f"🌟 {artist_name}",
        "type": "ACTOR_CORE",
        "actor": artist_name,
        "work_count": len(rows),
        "x": cx,
        "y": cy
    })

    # 2. 궤도 위성 작품 노드들 (방사형 원형 배치)
    radius = 360.0
    step = (2 * math.pi) / max(len(rows), 1)

    for idx, r in enumerate(rows):
        angle = idx * step
        x = round(cx + radius * math.cos(angle), 1)
        y = round(cy + radius * math.sin(angle), 1)
        nid = f"work_{r['uid']}"

        nodes.append({
            "id": nid,
            "type": "WORK_CARD",
            "uid": r["uid"],
            "code": r["code"],
            "title": r["title"],
            "artist": r["artist"],
            "year": r["year"],
            "studio": r["studio"],
            "plot": r["plot"][:120] if r["plot"] else "",
            "tags": r["tags"].split() if r["tags"] else [],
            "poster_url": f"/api/vault/poster/{r['uid']}",
            "stream_url": f"/api/stream/{r['uid']}",
            "x": x,
            "y": y
        })

        # 배우 <-> 작품 연결선
        edges.append({
            "id": f"edge_{actor_node_id}_{nid}",
            "source": actor_node_id,
            "target": nid,
            "label": str(r["year"] or "")
        })

    return {
        "actor": artist_name,
        "total": len(rows),
        "nodes": nodes,
        "edges": edges
    }

@router.get("/poster/{uid}")
async def get_poster_image(uid: str):
    """브라우저 로컬 보안을 우회하여 포스터 이미지를 안전하게 직결 서빙"""
    with get_db() as conn:
        row = conn.execute("SELECT poster_path, file_path FROM vault_items WHERE uid = ?", (uid,)).fetchone()

    if not row:
        return Response(content=FALLBACK_SVG, media_type="image/svg+xml")

    poster = row["poster_path"]
    if poster and os.path.exists(poster):
        return FileResponse(poster)

    # 폴더 내 대체 포스터 탐색
    video_p = row["file_path"]
    if video_p:
        v_dir = os.path.dirname(video_p)
        stem = os.path.splitext(video_p)[0]
        for alt in [f"{stem}-poster.jpg", f"{stem}.jpg", os.path.join(v_dir, "folder.jpg"), os.path.join(v_dir, "cover.jpg")]:
            if os.path.exists(alt):
                return FileResponse(alt)

    return Response(content=FALLBACK_SVG, media_type="image/svg+xml")

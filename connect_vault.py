# [FILE] SYNAPSE_VAULT/connect_vault.py
"""
🏛️ SYNAPSE VAULT - 프론트엔드/백엔드 1:1 결합 및 옵시디언 성좌 캔버스 완결 엔진
- 기존 구글 드라이브 메모장 프론트엔드 전량 폐기
- 실제 vault_core.db 데이터를 실시간 호출하는 성좌 캔버스 UI(SVG Bezier + HTML5 플레이어) 전면 주입
- 배우 선택 드롭다운, 검색, 포스터 서빙, 206 스트리밍 단일 통신망 결합
"""
import os
import sys
from pathlib import Path

VAULT_DIR = Path(__file__).resolve().parent

def run_connect():
    print("=" * 70)
    print("🔌 [SYNAPSE VAULT] 프론트엔드 ➔ 백엔드 DB 완전 결합 수술 집행")
    print("=" * 70)

    # 1. canvas/router.py 전면 교체 (배우 목록, 통계, 성좌, 포스터 서빙 통합)
    canvas_router_path = VAULT_DIR / "canvas/router.py"
    router_code = '''import os
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
'''
    canvas_router_path.write_text(router_code, encoding="utf-8")
    print("✅ [1/3] canvas/router.py API 전면 재구축 완료!")

    # 2. canvas/static/index.html 완전한 옵시디언 AV 성좌 캔버스 프론트엔드로 교체
    html_path = VAULT_DIR / "canvas/static/index.html"
    html_code = '''<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SYNAPSE VAULT - 46.7TB 하이엔드 성좌 캔버스</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #090A0F; color: #F8FAFC; overflow: hidden; margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        #canvas-viewport { width: 100vw; height: 100vh; position: relative; cursor: grab; background-image: radial-gradient(rgba(255, 255, 255, 0.08) 1px, transparent 1px); background-size: 32px 32px; }
        #canvas-viewport:active { cursor: grabbing; }
        #canvas-world { position: absolute; top: 0; left: 0; transform-origin: 0 0; }
        svg { position: absolute; top: 0; left: 0; width: 4000px; height: 4000px; pointer-events: none; overflow: visible; }
        .node { position: absolute; user-select: none; transition: transform 0.15s, box-shadow 0.15s; }
        .node:hover { z-index: 100; transform: scale(1.02); }
        .bezier-path { stroke: rgba(59, 130, 246, 0.45); stroke-width: 2.5; fill: none; filter: drop-shadow(0 0 4px rgba(59, 130, 246, 0.3)); }
        .poster-glow:hover { box-shadow: 0 0 30px rgba(59, 130, 246, 0.7); }
    </style>
</head>
<body class="w-screen h-screen">

    <!-- 상단 마스터 네비게이션 헤더 -->
    <header class="absolute top-4 left-6 right-6 z-50 flex items-center justify-between bg-[#12141A]/90 backdrop-blur-md border border-[#232733] px-6 py-3 rounded-2xl shadow-2xl">
        <div class="flex items-center gap-3">
            <span class="text-2xl">🏛️</span>
            <div>
                <h1 class="text-sm font-extrabold tracking-wider text-white flex items-center gap-2">
                    SYNAPSE VAULT <span class="text-[10px] bg-blue-600/30 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/30">PRO</span>
                </h1>
                <p id="liveStats" class="text-xs text-gray-400">데이터 로딩 중...</p>
            </div>
        </div>

        <!-- 배우 드롭다운 & 검색 컨트롤 -->
        <div class="flex items-center gap-3 w-1/2 max-w-xl">
            <!-- 배우 빠른 선택 -->
            <select id="actorSelect" onchange="onSelectActor(this.value)" class="bg-[#1A1D24] border border-[#2E3545] text-xs text-white px-3 py-2.5 rounded-xl focus:outline-none focus:border-blue-500 max-w-[180px]">
                <option value="">배우 선택...</option>
            </select>

            <!-- 검색 입력창 -->
            <div class="relative flex-1">
                <input id="searchInput" type="text" placeholder="배우 이름 또는 품번 검색..." 
                       class="w-full bg-[#1A1D24] border border-[#2E3545] text-xs text-white pl-4 pr-10 py-2.5 rounded-xl focus:outline-none focus:border-blue-500">
                <button onclick="triggerSearch()" class="absolute right-2.5 top-2.5 text-gray-400 hover:text-white">🔍</button>
            </div>

            <button onclick="loadRandomActor()" class="bg-[#1E222D] hover:bg-[#2A303F] border border-[#2E3545] text-xs font-semibold text-blue-400 px-4 py-2.5 rounded-xl transition whitespace-nowrap">
                🎲 랜덤 소환
            </button>
        </div>

        <div id="statusBadge" class="text-xs font-medium text-blue-400 bg-blue-950/40 border border-blue-800/40 px-3 py-1.5 rounded-xl">
            배우를 선택하여 성좌를 소환하세요
        </div>
    </header>

    <!-- 무한 캔버스 뷰포트 -->
    <div id="canvas-viewport">
        <div id="canvas-world">
            <svg id="svgLayer"></svg>
            <div id="nodesLayer"></div>
        </div>
    </div>

    <!-- 비디오 스트리밍 모달 플레이어 -->
    <div id="videoModal" class="fixed inset-0 bg-black/90 z-[200] hidden flex items-center justify-center p-6 backdrop-blur-md">
        <div class="bg-[#12141A] border border-[#232733] rounded-3xl max-w-5xl w-full p-6 relative flex flex-col gap-4 shadow-2xl">
            <div class="flex justify-between items-center border-b border-[#232733] pb-3">
                <div class="flex items-center gap-3">
                    <span class="text-red-500 text-lg">●</span>
                    <h2 id="videoTitle" class="text-sm font-bold text-white truncate max-w-2xl">재생 중</h2>
                </div>
                <button onclick="closeVideo()" class="text-gray-400 hover:text-white text-xl font-bold px-3 py-1 bg-[#1A1D24] rounded-xl border border-[#2E3545]">✕</button>
            </div>
            <video id="videoPlayer" controls autoplay class="w-full max-h-[70vh] rounded-2xl bg-black border border-[#232733]"></video>
        </div>
    </div>

    <script>
        let panX = window.innerWidth / 2 - 600;
        let panY = window.innerHeight / 2 - 450;
        let scale = 1;
        let isPanning = false;
        let startX, startY;
        let currentGraph = null;
        let allActors = [];

        const viewport = document.getElementById('canvas-viewport');
        const world = document.getElementById('canvas-world');
        const nodesLayer = document.getElementById('nodesLayer');
        const svgLayer = document.getElementById('svgLayer');

        // 초기 구동
        window.onload = async () => {
            updateTransform();
            await fetchStats();
            await fetchActors();
        };

        async function fetchStats() {
            try {
                const res = await fetch('/api/vault/stats');
                const data = await res.json();
                document.getElementById('liveStats').innerText = `총 ${data.total_works.toLocaleString()}편 소장작 | 배우 ${data.total_actors.toLocaleString()}명`;
            } catch (e) {
                document.getElementById('liveStats').innerText = '오프라인';
            }
        }

        async function fetchActors() {
            try {
                const res = await fetch('/api/vault/actors');
                allActors = await res.json();
                const sel = document.getElementById('actorSelect');
                allActors.forEach(a => {
                    const opt = document.createElement('option');
                    opt.value = a.name;
                    opt.innerText = `${a.name} (${a.count}편)`;
                    sel.appendChild(opt);
                });
            } catch (e) {}
        }

        function onSelectActor(actor) {
            if (actor) loadConstellation(actor);
        }

        function triggerSearch() {
            const val = document.getElementById('searchInput').value.trim();
            if (val) loadConstellation(val);
        }

        document.getElementById('searchInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') triggerSearch();
        });

        function loadRandomActor() {
            if (allActors.length > 0) {
                const rand = allActors[Math.floor(Math.random() * allActors.length)];
                document.getElementById('actorSelect').value = rand.name;
                loadConstellation(rand.name);
            }
        }

        // 캔버스 팬 & 줌 이벤트
        viewport.addEventListener('mousedown', (e) => {
            if (e.target.closest('.node')) return;
            isPanning = true;
            startX = e.clientX - panX;
            startY = e.clientY - panY;
        });
        window.addEventListener('mousemove', (e) => {
            if (!isPanning) return;
            panX = e.clientX - startX;
            panY = e.clientY - startY;
            updateTransform();
        });
        window.addEventListener('mouseup', () => isPanning = false);
        viewport.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            scale = Math.min(Math.max(0.3, scale * delta), 2.5);
            updateTransform();
        });

        function updateTransform() {
            world.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
        }

        // 별자리 로드
        async function loadConstellation(actorName) {
            document.getElementById('statusBadge').innerText = `'${actorName}' 성좌 연산 중...`;
            try {
                const res = await fetch(`/api/vault/constellation/${encodeURIComponent(actorName)}`);
                if (!res.ok) throw new Error('작품을 찾을 수 없습니다.');
                currentGraph = await res.json();

                renderCanvas(currentGraph);
                document.getElementById('statusBadge').innerText = `🌟 ${currentGraph.actor} (${currentGraph.total}편 연결됨)`;

                // 중앙 리셋
                panX = window.innerWidth / 2 - 600 * scale;
                panY = window.innerHeight / 2 - 450 * scale;
                updateTransform();
            } catch (err) {
                document.getElementById('statusBadge').innerText = `⚠️ ${err.message}`;
            }
        }

        function renderCanvas(graph) {
            nodesLayer.innerHTML = '';
            svgLayer.innerHTML = '';

            // 1. 노드 렌더링
            graph.nodes.forEach(n => {
                const el = document.createElement('div');
                el.id = n.id;
                el.style.left = `${n.x}px`;
                el.style.top = `${n.y}px`;

                if (n.type === 'ACTOR_CORE') {
                    // 중심 배우 핵 노드
                    el.className = 'node flex flex-col items-center justify-center p-6 bg-gradient-to-br from-blue-900/90 to-indigo-950/90 border-2 border-blue-400 rounded-3xl w-56 text-center shadow-2xl';
                    el.innerHTML = `
                        <div class="text-3xl mb-1">🌟</div>
                        <div class="text-base font-extrabold text-yellow-300">${n.actor}</div>
                        <div class="text-xs text-blue-200 mt-1">소장 작품 ${n.work_count}편</div>
                    `;
                } else {
                    // 주변 작품 카드 노드
                    el.className = 'node poster-glow bg-[#12141A] border border-[#232733] rounded-2xl w-48 overflow-hidden flex flex-col cursor-pointer shadow-xl';
                    el.innerHTML = `
                        <div class="relative w-full h-64 bg-gray-950">
                            <img src="${n.poster_url}" class="w-full h-full object-cover" onerror="this.src='/api/vault/poster/none'">
                            <span class="absolute top-2 left-2 bg-black/70 backdrop-blur text-[10px] font-bold text-yellow-400 px-2 py-0.5 rounded-md border border-white/10">${n.code}</span>
                            <span class="absolute top-2 right-2 bg-blue-600/80 backdrop-blur text-[10px] font-bold text-white px-1.5 py-0.5 rounded-md">${n.year || '----'}</span>
                        </div>
                        <div class="p-3 flex flex-col gap-1">
                            <div class="text-xs font-bold text-white truncate">${n.title}</div>
                            <div class="text-[10px] text-gray-400 truncate">${n.studio || 'VAULT'}</div>
                        </div>
                    `;
                    el.onclick = () => openVideo(n.title, n.stream_url);
                }

                nodesLayer.appendChild(el);
            });

            // 2. 3차 베지에 곡선 연결선 렌더링
            const core = graph.nodes.find(n => n.type === 'ACTOR_CORE');
            if (!core) return;

            const cX = core.x + 112;
            const cY = core.y + 60;

            graph.edges.forEach(edge => {
                const target = graph.nodes.find(n => n.id === edge.target);
                if (!target) return;

                const tX = target.x + 96;
                const tY = target.y + 160;

                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                const midX = (cX + tX) / 2;
                const midY = (cY + tY) / 2 - 40;
                path.setAttribute('d', `M ${cX} ${cY} Q ${midX} ${midY} ${tX} ${tY}`);
                path.setAttribute('class', 'bezier-path');
                svgLayer.appendChild(path);
            });
        }

        // 비디오 스트리밍 재생
        function openVideo(title, url) {
            document.getElementById('videoTitle').innerText = title;
            const player = document.getElementById('videoPlayer');
            player.src = url;
            document.getElementById('videoModal').classList.remove('hidden');
        }

        function closeVideo() {
            const player = document.getElementById('videoPlayer');
            player.pause();
            player.src = '';
            document.getElementById('videoModal').classList.add('hidden');
        }

        window.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeVideo();
        });
    </script>
</body>
</html>
'''
    html_path.write_text(html_code, encoding="utf-8")
    print("✅ [2/3] canvas/static/index.html 완전한 성좌 캔버스 UI 주입 완료!")

    # 3. run.py 라우터 매핑 최종 확인
    run_path = VAULT_DIR / "run.py"
    run_txt = run_path.read_text(encoding="utf-8")
    if "canvas.router" in run_txt:
        print("✅ [3/3] run.py 메인 마스터 서버 연결 정상 확인!")

    print("\n" + "=" * 70)
    print("🎉 [결합 대성공] 깡통 화면이 사라지고 실시간 성좌 캔버스가 장착되었습니다!")
    print("👉 이제 서버를 켜십시오:")
    print("   python run.py")
    print("   -> 브라우저 새로고침(F5) 하시면 상단에 배우 드롭다운과 통계가 뜨고,")
    print("      배우를 고르면 즉시 성좌가 펼쳐지며 포스터 클릭 시 영상이 재생됩니다!")
    print("=" * 70)

if __name__ == "__main__":
    run_connect()
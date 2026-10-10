import os
import sys
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from vault.db import get_db
import config

SUPPORTED_EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".ts", ".m4v", ".mov", ".flv"}

def generate_uid(path: str) -> str:
    norm = path.replace("\\", "/").lower()
    return hashlib.md5(norm.encode("utf-8")).hexdigest()

def find_nfo_file(video_path: str, root_dir: str, files_in_dir: list) -> str:
    """영상 파일명 매칭 -> 폴더 내 단일 NFO -> 대소문자 무관 NFO 탐색"""
    stem = os.path.splitext(video_path)[0]
    # 1. 파일명 1:1 매칭 (xxx.nfo)
    if os.path.exists(f"{stem}.nfo"): return f"{stem}.nfo"
    if os.path.exists(f"{stem}.NFO"): return f"{stem}.NFO"

    # 2. 폴더 내 nfo 검색
    nfos = [f for f in files_in_dir if f.lower().endswith(".nfo")]
    if len(nfos) == 1:
        return os.path.join(root_dir, nfos[0]).replace("\\", "/")
    
    # 3. movie.nfo 확인
    for cand in ["movie.nfo", "index.nfo"]:
        p = os.path.join(root_dir, cand).replace("\\", "/")
        if os.path.exists(p): return p

    return ""

def find_poster_file(video_path: str, root_dir: str, files_in_dir: list) -> str:
    """세로 포스터(-poster.jpg, folder.jpg, cover.jpg) 탐색"""
    stem = os.path.splitext(video_path)[0]
    for cand in [f"{stem}-poster.jpg", f"{stem}-poster.png", f"{stem}.jpg"]:
        if os.path.exists(cand): return cand

    # 폴더 내 공용 표지 탐색
    common_names = {"folder.jpg", "poster.jpg", "cover.jpg", "folder.png", "cover.png"}
    for f in files_in_dir:
        if f.lower() in common_names:
            return os.path.join(root_dir, f).replace("\\", "/")
    return ""

def extract_meta_from_path(video_path: str, root_dir: str):
    """NFO가 없거나 깨졌을 때 배우별 하위 폴더 구조에서 메타데이터 자동 구출"""
    filename = os.path.basename(video_path)
    stem = os.path.splitext(filename)[0]
    norm_path = video_path.replace("\\", "/")

    # 카테고리 태그 추론
    category = "ARCHIVES"
    extra_tags = []
    if "uncensored" in norm_path.lower() or "leak" in norm_path.lower():
        extra_tags.extend(["무삭제", "노모", "유출"])
    if "(av)" in norm_path.lower():
        extra_tags.append("정규AV")

    # 경로에서 배우명 추출 시도 (O:/(AV)/배우명/작품/... 구조 대응)
    parts = norm_path.split("/")
    actor = "UNKNOWN"
    for idx, p in enumerate(parts):
        if p in ["(AV)", "(Uncensored Leak)", "AV", "Uncensored"]:
            if idx + 1 < len(parts) - 1:
                actor = parts[idx + 1] # 배우 폴더명
                break

    return {
        "code": stem.split("-")[0] if "-" in stem else stem,
        "title": stem,
        "artist": actor if actor != "UNKNOWN" else "",
        "year": 0,
        "release_date": "1900-01-01",
        "studio": "VAULT",
        "plot": f"{stem} (로컬 아카이브 소장작)",
        "actors": [{"name": actor}] if actor != "UNKNOWN" else [],
        "tags": extra_tags,
    }

def parse_nfo_safe(nfo_path: str, fallback_meta: dict):
    if not nfo_path or not os.path.exists(nfo_path):
        return fallback_meta
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
        
        movie_id = root.findtext("id") or root.findtext("num") or fallback_meta["code"]
        title = root.findtext("title") or fallback_meta["title"]
        plot = root.findtext("plot") or fallback_meta["plot"]
        premiered = root.findtext("premiered") or root.findtext("releasedate") or fallback_meta["release_date"]
        year = int(premiered.split("-")[0]) if "-" in premiered and premiered.split("-")[0].isdigit() else 0
        studio = root.findtext("studio") or root.findtext("maker") or fallback_meta["studio"]

        actors = []
        main_actor = fallback_meta["artist"]
        for a in root.findall("actor"):
            name = (a.findtext("name") or "").strip()
            role = (a.findtext("role") or "").strip()
            if name:
                actors.append({"name": name, "role": role})
                if not main_actor or main_actor == "UNKNOWN":
                    main_actor = name

        tags = [g.text.strip() for g in root.findall("genre") if g.text and g.text.strip()]
        tags.extend(fallback_meta["tags"])

        return {
            "code": movie_id,
            "title": title,
            "artist": main_actor,
            "year": year,
            "release_date": premiered,
            "studio": studio,
            "plot": plot,
            "actors": actors,
            "tags": list(dict.fromkeys(tags))
        }
    except Exception:
        return fallback_meta

def run_ingest(targets=None):
    if not targets:
        targets = [t for t in config.STORAGE_TARGETS if os.path.exists(t)]
    
    print(f"\n🔍 다음 드라이브/폴더에서 깊은 하위 폴더 전수 스캔을 시작합니다:")
    for t in targets:
        print(f"   📂 {t}")
    
    batch = []
    total = 0
    scanned_folders = 0

    for t in targets:
        print(f"\n🚀 [{t}] 드라이브 침투 시작...")
        for r, dirs, files in os.walk(t):
            # 시스템 휴지통 및 숨김 폴더 건너뛰기
            dirs[:] = [d for d in dirs if not d.startswith(("$", ".")) and d.lower() != "system volume information"]
            scanned_folders += 1
            if scanned_folders % 50 == 0:
                print(f"   -> {scanned_folders:,}개 폴더 통과 중... (누적 {total:,}개 작품 적재 완료)", end="\r")

            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in SUPPORTED_EXTS:
                    v_path = os.path.join(r, f).replace("\\", "/")
                    
                    # 1. 파일/폴더 기반 메타 자동 복원 (NFO 유무 상관없이 0건 방어)
                    fallback_meta = extract_meta_from_path(v_path, r)
                    nfo_path = find_nfo_file(v_path, r, files)
                    poster_path = find_poster_file(v_path, r, files)
                    
                    meta = parse_nfo_safe(nfo_path, fallback_meta)
                    uid = generate_uid(v_path)

                    batch.append((
                        uid, meta["code"], meta["title"], meta["artist"],
                        meta["year"], meta["release_date"], meta["studio"],
                        v_path, os.path.getsize(v_path),
                        poster_path, meta["plot"], " ".join(meta["tags"]), str(meta["actors"])
                    ))

                    if len(batch) >= 200:
                        _flush(batch)
                        total += len(batch)
                        print(f"   ⚡ 현재까지 {total:,}개 영상 메타데이터 DB 저장 완료...", end="\r")
                        batch.clear()

    if batch:
        _flush(batch)
        total += len(batch)

    print(f"\n\n🎉 [적재 대성공] 총 {scanned_folders:,}개 폴더를 뒤져서 {total:,}개 작품을 vault_core.db에 완벽 등록했습니다!")

def _flush(batch):
    with get_db() as conn:
        conn.executemany("""
            INSERT INTO vault_items (
                uid, code, title, artist, year, release_date, studio,
                file_path, file_size, poster_path, plot, tags, actors_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(uid) DO UPDATE SET
                title = excluded.title,
                artist = excluded.artist,
                year = excluded.year,
                poster_path = CASE WHEN excluded.poster_path != '' THEN excluded.poster_path ELSE vault_items.poster_path END,
                plot = excluded.plot,
                tags = excluded.tags;
        """, batch)

if __name__ == "__main__":
    import sys
    custom_target = sys.argv[1:] if len(sys.argv) > 1 else None
    run_ingest(custom_target)

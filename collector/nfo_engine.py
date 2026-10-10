import os
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Any

def parse_nfo(nfo_path: str, video_path: str) -> Optional[Dict[str, Any]]:
    """Javinizer가 생성한 .nfo XML을 0.001초 만에 파싱"""
    if not os.path.exists(nfo_path):
        return None
    try:
        tree = ET.parse(nfo_path)
        root = tree.getroot()
    except Exception:
        return None

    movie_id = root.findtext("id") or root.findtext("num") or os.path.splitext(os.path.basename(video_path))[0]
    title = root.findtext("title") or movie_id
    plot = root.findtext("plot") or ""
    premiered = root.findtext("premiered") or root.findtext("releasedate") or "1900-01-01"
    year = int(premiered.split("-")[0]) if "-" in premiered and premiered.split("-")[0].isdigit() else 0
    studio = root.findtext("studio") or root.findtext("maker") or ""

    actors = []
    main_actor = ""
    for a in root.findall("actor"):
        name = (a.findtext("name") or "").strip()
        role = (a.findtext("role") or "").strip()
        if name:
            actors.append({"name": name, "role": role})
            if not main_actor:
                main_actor = name

    tags = [g.text.strip() for g in root.findall("genre") if g.text and g.text.strip()]

    return {
        "code": movie_id,
        "title": title,
        "artist": main_actor,
        "year": year,
        "release_date": premiered,
        "studio": studio,
        "plot": plot,
        "actors": actors,
        "tags": tags,
        "file_path": video_path.replace("\\", "/")
    }

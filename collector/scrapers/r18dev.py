# [FILE] scrapers/r18dev.py
import re
from urllib.parse import quote
from collector.core.config import HTTP_SESSION, REQUEST_TIMEOUT
from .dmm import filter_clean_genres

def scrape_r18dev(movie_id: str):
    """[r18.dev] 영문/일문 줄거리 전수 추출 및 갤러리 파싱"""
    search_url = f"https://r18.dev/videos/vod/movies/detail/-/dvd_id={quote(movie_id)}/json"
    try:
        resp = HTTP_SESSION.get(search_url, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            return None

        search_data = resp.json()
        content_id = search_data.get('content_id')
        if not content_id:
            return None

        detail_url = f"https://r18.dev/videos/vod/movies/detail/-/combined={quote(content_id)}/json"
        detail_resp = HTTP_SESSION.get(detail_url, timeout=REQUEST_TIMEOUT)
        if detail_resp.status_code != 200:
            return None

        data = detail_resp.json()
        if not data:
            return None

        dvd_id = data.get('dvd_id', '')
        if dvd_id:
            d_norm = re.sub(r'[^a-zA-Z0-9]', '', dvd_id).upper()
            m_norm = re.sub(r'[^a-zA-Z0-9]', '', movie_id).upper()
            if d_norm != m_norm:
                return None

        cover_url = (data.get('jacket_full_url') or '').replace('ps.jpg', 'pl.jpg')

        actors = []
        for act in data.get('actresses', []):
            thumb = act.get('image_url') or ''
            if thumb and not thumb.startswith('http'):
                thumb = f"https://pics.dmm.co.jp/mono/actjpgs/{thumb}"
            actors.append({
                'name': act.get('name_romaji') or act.get('name_kanji') or 'Unknown',
                'altname': act.get('name_kanji') or '',
                'thumb': thumb,
            })

        directors = data.get('directors', [])
        director = directors[0].get('name_romaji') if directors else ''
        genres = [c.get('name_en') for c in data.get('categories', []) if c.get('name_en')]
        rel_date = (data.get('release_date') or '').split(' ')[0]

        maker = data.get('maker_name_ja') or data.get('maker_name_en') or ''
        label = data.get('label_name_ja') or data.get('label_name_en') or ''
        series = data.get('series_name_ja') or data.get('series_name_en') or ''

        # ★ 줄거리: 영문이 없으면 일문/기본 줄거리로 전수 폴백
        plot = data.get('comment_en') or data.get('comment_ja') or data.get('comment') or ''

        sample_images = []
        for g in data.get('gallery', []):
            img_url = g.get('image_full') or g.get('image_thumb') or ''
            if img_url and img_url not in sample_images:
                sample_images.append(img_url)

        return {
            'source': 'r18.dev',
            'id': data.get('dvd_id', movie_id),
            'content_id': data.get('content_id') or content_id,
            'title': data.get('title_en') or data.get('title') or '',
            'originaltitle': data.get('title_ja') or '',
            'premiered': rel_date,
            'year': rel_date.split('-')[0] if rel_date else '',
            'director': director,
            'studio': maker,
            'maker': maker,
            'label': label,
            'series': series,
            'rating': str(data.get('user_rating') or ''),
            'plot': plot.strip(),
            'runtime': str(data.get('runtime_mins') or ''),
            'trailer': data.get('sample_url') or '',
            'genres': filter_clean_genres(genres),
            'actors': actors,
            'cover_url': cover_url,
            'sample_images': sample_images,
        }
    except Exception:
        pass
    return None
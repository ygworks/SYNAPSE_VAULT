import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from collector.core.config import HTTP_SESSION, REQUEST_TIMEOUT
from collector.core.parser import match_movie_id

def _scrape_jav321_single(query_sn: str, original_id: str):
    url = "https://www.jav321.com/search"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://www.jav321.com/',
    }
    try:
        resp = HTTP_SESSION.post(url, data={'sn': query_sn}, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.content, 'html.parser')

        if '/video/' not in resp.url:
            target_link = None
            for a_tag in soup.find_all('a', href=re.compile(r'/video/')):
                parent_text = a_tag.parent.text if a_tag.parent else ""
                if match_movie_id(original_id, f"{a_tag.text} {parent_text}") or match_movie_id(query_sn, f"{a_tag.text} {parent_text}"):
                    target_link = urljoin("https://www.jav321.com", a_tag['href'])
                    break

            if not target_link:
                first_thumb = soup.find('a', href=re.compile(r'/video/[a-zA-Z0-9]+'))
                if first_thumb and (match_movie_id(original_id, first_thumb.text) or match_movie_id(query_sn, first_thumb.text)):
                    target_link = urljoin("https://www.jav321.com", first_thumb['href'])

            if not target_link:
                return None

            detail_resp = HTTP_SESSION.get(target_link, headers=headers, timeout=REQUEST_TIMEOUT)
            if detail_resp.status_code != 200:
                return None
            soup = BeautifulSoup(detail_resp.content, 'html.parser')

        h3 = soup.find('h3')
        title = h3.text.strip() if h3 else ''

        cover_tag = soup.find('img', class_='img-responsive')
        cover_url = cover_tag.get('src', '') if cover_tag else ''

        premiered, runtime, studio, plot = '', '', '', ''
        genres, actors = [], []

        for p in soup.find_all(['p', 'div']):
            text = p.text.strip()
            if '配信開始日:' in text or '発売日:' in text:
                m = re.search(r'\d{4}[/-]\d{2}[/-]\d{2}', text)
                if m: premiered = m.group(0).replace('/', '-')
            elif '収録時間:' in text:
                m = re.search(r'\d+', text)
                if m: runtime = m.group(0)
            elif 'メーカー:' in text:
                a = p.find('a')
                if a: studio = a.text.strip()
            elif '出演者:' in text:
                for a in p.find_all('a'):
                    act = a.text.strip()
                    if act and act not in [x['name'] for x in actors]:
                        actors.append({'name': act, 'altname': '', 'thumb': ''})
            elif 'ジャンル:' in text:
                for a in p.find_all('a'):
                    g = a.text.strip()
                    if g and g not in genres: genres.append(g)

        for panel in soup.find_all('div', class_='panel-body'):
            t = panel.text.strip()
            if len(t) > len(plot) and 'Cookie' not in t and 'Jav321' not in t:
                plot = t

        if title or cover_url:
            return {
                'source': 'Jav321',
                'id': original_id,
                'content_id': original_id.lower().replace('-', ''),
                'title': title,
                'originaltitle': title,
                'premiered': premiered,
                'year': premiered.split('-')[0] if premiered else '',
                'director': '',
                'studio': studio,
                'maker': studio,
                'label': '',
                'series': '',
                'rating': '',
                'plot': plot,
                'runtime': runtime,
                'trailer': '',
                'genres': genres,
                'actors': actors,
                'cover_url': cover_url,
                'sample_images': [],
            }
    except Exception:
        pass
    return None

def scrape_jav321(movie_id: str):
    candidates = []

    # 1. FC2 계열: 순수 숫자(1121174)를 1순위로 무조건 전진 배치
    fc2_num = re.search(r'\b\d{5,8}\b', movie_id)
    if fc2_num or 'FC2' in movie_id.upper():
        num = fc2_num.group(0) if fc2_num else re.sub(r'\D', '', movie_id)
        if num:
            candidates.append(num)
            candidates.append(f"FC2-{num}")

    # 2. 날짜형 무삭제: 언더바(031816_524, 011219_004)를 1순위로 전진 배치
    date_m = re.search(r'(\d{6})[-_](\d{3,4})', movie_id)
    if date_m:
        d, s = date_m.group(1), date_m.group(2)
        candidates.append(f"{d}_{s}")
        candidates.append(f"{d}-{s}")

    candidates.append(movie_id)

    for cand in list(dict.fromkeys(candidates)):
        res = _scrape_jav321_single(cand, movie_id)
        if res and (res.get('title') or res.get('cover_url')):
            return res

    return None
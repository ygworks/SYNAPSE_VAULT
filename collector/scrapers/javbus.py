# [FILE] scrapers/javbus.py
import re
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from collector.core.config import HTTP_SESSION, REQUEST_TIMEOUT
from collector.core.parser import match_movie_id, normalize_movie_id

def scrape_javbus(movie_id: str):
    """
    [JavBus 스크래퍼] 노모/유출관(uncensored) 자동 직행 & 다중 품번 후보군 릴레이 탐색
    """
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'ja,ko;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://www.javbus.com/',
    }
    cookies = {'existmag': 'all'}

    t_prefix, t_num = normalize_movie_id(movie_id)
    date_m = re.search(r'(\d{6})[-_](\d{3,4})', movie_id)

    # 1. 노모/유출 영상 여부 판별 (FC2, 날짜형, N, HEYZO 등)
    is_uncensored = (
        bool(date_m)
        or t_prefix in ['FC2', 'DATE', 'N', 'CZ', 'K', 'HEYZO', 'CARIBBEAN', '1PONDO']
        or movie_id.upper().startswith(('FC2', 'PPV', 'HEYZO'))
    )

    # 2. 다이렉트 URL 후보군 생성
    direct_candidates = [movie_id]
    if date_m:
        d_str, s_str = date_m.group(1), date_m.group(2)
        direct_candidates.extend([f"{d_str}-{s_str}", f"{d_str}_{s_str}"])
    elif t_prefix == 'FC2' and t_num:
        direct_candidates.extend([f"FC2-PPV-{t_num}", f"FC2-{t_num}", str(t_num)])
    elif t_prefix and t_num is not None:
        direct_candidates.extend([
            f"{t_prefix}-{str(t_num).zfill(2)}",
            f"{t_prefix}-{str(t_num).zfill(3)}",
            f"{t_prefix}-{str(t_num).zfill(4)}",
            f"{t_prefix}-{t_num}"
        ])

    direct_candidates = list(dict.fromkeys(direct_candidates))

    urls_to_try = []
    if is_uncensored:
        for cid in direct_candidates:
            urls_to_try.append(f"https://www.javbus.com/uncensored/{cid}")
        for cid in direct_candidates:
            urls_to_try.append(f"https://www.javbus.com/{cid}")
    else:
        for cid in direct_candidates:
            urls_to_try.append(f"https://www.javbus.com/{cid}")
        for cid in direct_candidates:
            urls_to_try.append(f"https://www.javbus.com/uncensored/{cid}")

    soup = None

    # 3. 다이렉트 URL 접근
    for d_url in urls_to_try:
        try:
            resp = HTTP_SESSION.get(d_url, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                s = BeautifulSoup(resp.content, 'html.parser')
                h3 = s.find('h3')
                if h3 and match_movie_id(movie_id, f"{h3.text} {d_url}"):
                    soup = s
                    break
        except Exception:
            continue

    # 4. 다이렉트 실패 시 검색창 침투 (노모/유출관 최우선 질의)
    if not soup:
        search_terms = [movie_id]
        if t_prefix == 'FC2' and t_num:
            search_terms.extend([f"FC2-{t_num}", str(t_num)])
        elif date_m:
            search_terms.extend([f"{date_m.group(1)}-{date_m.group(2)}", f"{date_m.group(1)}_{date_m.group(2)}"])

        search_urls = []
        for st in list(dict.fromkeys(search_terms)):
            if is_uncensored:
                search_urls.append(f"https://www.javbus.com/uncensored/search/{quote(st)}?type=&parent=uc")
                search_urls.append(f"https://www.javbus.com/search/{quote(st)}?type=&parent=uc")
            else:
                search_urls.append(f"https://www.javbus.com/search/{quote(st)}?type=&parent=uc")
                search_urls.append(f"https://www.javbus.com/uncensored/search/{quote(st)}?type=&parent=uc")

        for s_url in search_urls:
            try:
                s_resp = HTTP_SESSION.get(s_url, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT)
                if s_resp.status_code == 200:
                    s_soup = BeautifulSoup(s_resp.content, 'html.parser')
                    for box in s_soup.find_all('a', class_='movie-box'):
                        cand_text = f"{box.text} {box.get('href', '')}"
                        if match_movie_id(movie_id, cand_text):
                            detail_resp = HTTP_SESSION.get(box['href'], headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT)
                            if detail_resp.status_code == 200:
                                soup = BeautifulSoup(detail_resp.content, 'html.parser')
                                break
                if soup:
                    break
            except Exception:
                continue

    if not soup:
        return None

    h3 = soup.find('h3')
    if not h3:
        return None
    title = h3.text.strip()

    clean_title = re.sub(r'^[\[【(]?[a-zA-Z0-9-_]+[\]】)]?\s*', '', title).strip()

    big_image = soup.find('a', class_='bigImage')
    cover_url = urljoin('https://www.javbus.com', big_image['href']) if big_image and big_image.get('href') else ''

    premiered, runtime, director, studio, label, series = '', '', '', '', '', ''
    genres, actors = [], []

    info_div = soup.find('div', class_='col-md-3 info')
    if info_div:
        for p in info_div.find_all('p'):
            text = p.text
            if any(k in text for k in ['發行日期:', '발매일:']):
                m = re.search(r'\d{4}-\d{2}-\d{2}', text)
                if m: premiered = m.group(0)
            elif any(k in text for k in ['長度:', '길이:']):
                m = re.search(r'\d+', text)
                if m: runtime = m.group(0)
            elif any(k in text for k in ['導演:', '감독:']):
                a = p.find('a')
                if a: director = a.text.strip()
            elif any(k in text for k in ['製作商:', '제작사:']):
                a = p.find('a')
                if a: studio = a.text.strip()
            elif any(k in text for k in ['發行商:', '레이블:']):
                a = p.find('a')
                if a: label = a.text.strip()
            elif any(k in text for k in ['系列:', '시리즈:']):
                a = p.find('a')
                if a: series = a.text.strip()

        for a in info_div.find_all('span', class_='genre'):
            g_tag = a.find('a')
            if g_tag: genres.append(g_tag.text.strip())

    for at in soup.find_all('span', class_='star-name'):
        a_link = at.find('a')
        if a_link and a_link.text.strip():
            actors.append({'name': a_link.text.strip(), 'altname': '', 'thumb': ''})

    sample_images = []
    for a in soup.find_all('a', class_='sample-box'):
        if a.get('href'):
            sample_images.append(urljoin('https://www.javbus.com', a['href']))

    return {
        'source': 'JavBus',
        'id': movie_id,
        'content_id': movie_id.lower().replace('-', ''),
        'title': clean_title or title,
        'originaltitle': clean_title or title,
        'premiered': premiered,
        'year': premiered.split('-')[0] if premiered else '',
        'director': director,
        'studio': studio,
        'maker': studio,
        'label': label,
        'series': series,
        'rating': '',
        'plot': '',
        'runtime': runtime,
        'trailer': '',
        'genres': genres,
        'actors': actors,
        'cover_url': cover_url,
        'sample_images': sample_images,
    }
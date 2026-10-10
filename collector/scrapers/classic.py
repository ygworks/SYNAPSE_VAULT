import json
import os
import re
import threading
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from collector.core.config import HTTP_SESSION, REQUEST_TIMEOUT
from collector.core.parser import match_movie_id, normalize_movie_id

_MAKER_CACHE = None
_MAKER_LOCK = threading.Lock()

def get_classic_maker_map() -> dict:
    global _MAKER_CACHE
    if _MAKER_CACHE is not None:
        return _MAKER_CACHE
    with _MAKER_LOCK:
        if _MAKER_CACHE is not None:
            return _MAKER_CACHE
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cfg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "classic_studios.json")
        try:
            with open(cfg_path, "r", encoding="utf-8-sig") as f:
                _MAKER_CACHE = json.load(f).get("studios", {})
        except OSError:
            _MAKER_CACHE = {}
        return _MAKER_CACHE

CLASSIC_MAKER_MAP = get_classic_maker_map()

def probe_dmm_cdn_image(cid: str) -> str:
    test_urls = [
        f"https://pics.dmm.co.jp/mono/movie/adult/{cid}/{cid}pl.jpg",
        f"https://pics.dmm.co.jp/mono/movie/adult/{cid}/{cid}ps.jpg",
        f"https://pics.dmm.co.jp/digital/video/{cid}/{cid}pl.jpg",
        f"https://pics.dmm.co.jp/digital/video/{cid}/{cid}ps.jpg"
    ]
    headers = {'Referer': 'https://www.dmm.co.jp/'}
    for u in test_urls:
        try:
            r = HTTP_SESSION.get(u, headers=headers, stream=True, timeout=4, allow_redirects=False)
            status = r.status_code
            r.close()
            if status == 200 and 'nowprinting' not in u.lower():
                return u
        except (OSError, ValueError):
            continue
    return ""

def scrape_classic_dmm(movie_id: str):
    t_prefix, t_num = normalize_movie_id(movie_id)
    if not t_prefix or t_num is None or not isinstance(t_num, int):
        return None

    prefix_upper = t_prefix.upper()
    maker_map = get_classic_maker_map()
    maker_info = maker_map.get(prefix_upper, {})
    prefixes_to_try = maker_info.get('prefixes', [prefix_upper.lower()])
    studio_name = maker_info.get('studio', prefix_upper)

    cid_candidates = []
    for p in prefixes_to_try:
        if t_num >= 10000:
            cid_candidates.append(f"{p}{t_num}")
        cid_candidates.append(f"{p}{str(t_num).zfill(5)}")
        cid_candidates.append(f"{p}{str(t_num).zfill(4)}")
        cid_candidates.append(f"{p}{str(t_num).zfill(3)}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://www.dmm.co.jp/',
    }

    for cid in list(dict.fromkeys(cid_candidates)):
        target_urls = [
            f"https://www.dmm.co.jp/mono/dvd/-/detail/=/cid={cid}/",
            f"https://www.dmm.co.jp/mono/video/-/detail/=/cid={cid}/",
            f"https://www.dmm.co.jp/digital/videoa/-/detail/=/cid={cid}/"
        ]
        for target_url in target_urls:
            try:
                resp = HTTP_SESSION.get(target_url, headers=headers, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, 'html.parser')
                    h1 = soup.find('h1', id='title') or soup.find('h1', class_='item-title')
                    title = h1.text.strip() if h1 else ''

                    cover_tag = soup.find('a', id='package-src') or soup.find('img', class_='tdmm') or soup.find('a', class_='package')
                    cover_url = ''
                    if cover_tag:
                        raw_c = cover_tag.get('href') or cover_tag.get('src') or ''
                        if not any(k in raw_c.lower() for k in ['nowprinting', 'noimage']):
                            cover_url = urljoin('https://www.dmm.co.jp', raw_c).replace('ps.jpg', 'pl.jpg').replace('pr.jpg', 'pl.jpg')

                    if not cover_url:
                        og_img = soup.find('meta', property='og:image')
                        if og_img and og_img.get('content'):
                            cover_url = og_img['content'].replace('ps.jpg', 'pl.jpg')

                    premiered, runtime, director, studio, maker, label = '', '', '', '', '', ''
                    raw_genres, actors = [], []

                    for tr in soup.find_all('tr'):
                        text = tr.text
                        if any(k in text for k in ['発売日', '商品発売日']):
                            m = re.search(r'\d{4}[/-]\d{2}[/-]\d{2}', tr.text)
                            if m: premiered = m.group(0).replace('/', '-')
                        elif '収録時間' in text:
                            m = re.search(r'(\d+)', tr.text)
                            if m: runtime = m.group(1)
                        elif '監督' in text:
                            a = tr.find('a')
                            if a: director = a.text.strip()
                        elif 'メーカー' in text:
                            a = tr.find('a')
                            if a: maker, studio = a.text.strip(), a.text.strip()
                        elif 'レーベル' in text:
                            a = tr.find('a')
                            if a: label = a.text.strip()
                        elif '出演者' in text:
                            for a in tr.find_all('a'):
                                act = a.text.strip()
                                if act and 'すべて表示' not in act:
                                    actors.append({'name': act, 'altname': '', 'thumb': ''})
                        elif 'ジャンル' in text:
                            for a in tr.find_all('a'):
                                g = a.text.strip()
                                if g and g not in raw_genres: raw_genres.append(g)

                    plot_div = soup.find('div', class_='mg-b20 lh4') or soup.find('p', class_='mg-b20') or soup.find('div', class_='clear lh4')
                    plot = plot_div.text.strip() if plot_div else ''

                    if title or cover_url:
                        return {
                            'source': 'DMM-Classic', 'id': movie_id, 'content_id': cid,
                            'title': title, 'originaltitle': title, 'premiered': premiered,
                            'year': premiered.split('-')[0] if premiered else '', 'director': director,
                            'studio': studio or studio_name, 'maker': maker or studio_name, 'label': label,
                            'series': '', 'rating': '', 'plot': plot, 'runtime': runtime, 'trailer': '',
                            'genres': raw_genres, 'actors': actors, 'cover_url': cover_url, 'sample_images': [], 'is_partial': False
                        }
            except (OSError, ValueError):
                continue

    for cid in list(dict.fromkeys(cid_candidates)):
        cdn_img_url = probe_dmm_cdn_image(cid)
        if cdn_img_url:
            return {
                'source': 'DMM-CDN-Direct', 'id': movie_id, 'content_id': cid,
                'title': '', 'originaltitle': '', 'premiered': '', 'year': '', 'director': '',
                'studio': studio_name, 'maker': studio_name, 'label': '', 'series': '', 'rating': '',
                'plot': '', 'runtime': '', 'trailer': '', 'genres': [], 'actors': [],
                'cover_url': cdn_img_url, 'sample_images': [], 'is_partial': True
            }

    try:
        from scrapers.dmm import scrape_dmm
        dmm_res = scrape_dmm(movie_id)
        if dmm_res and (dmm_res.get('title') or dmm_res.get('cover_url')):
            return dmm_res
    except Exception:
        pass

    return None

def scrape_classic_javdb(movie_id: str):
    t_prefix, t_num = normalize_movie_id(movie_id)
    search_queries = [movie_id]
    if t_prefix == 'FC2' and t_num:
        search_queries.extend([f"FC2-{t_num}", f"FC2-PPV-{t_num}", str(t_num)])
    elif t_prefix == 'DATE':
        search_queries.append(str(t_num))

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Referer': 'https://javdb.com/',
    }
    cookies = {'over18': '1', 'locale': 'en', 'theme': 'dark'}

    for sq in list(dict.fromkeys(search_queries)):
        url = f"https://javdb.com/search?q={quote(sq)}&f=all"
        try:
            resp = HTTP_SESSION.get(url, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.content, 'html.parser')
            target_href = None

            for item in soup.find_all('div', class_='item'):
                if match_movie_id(movie_id, item.text.strip()):
                    a_tag = item.find('a')
                    if a_tag and a_tag.get('href'):
                        target_href = urljoin("https://javdb.com", a_tag['href'])
                        break
            if not target_href:
                continue

            d_resp = HTTP_SESSION.get(target_href, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT)
            if d_resp.status_code != 200:
                continue
            dsoup = BeautifulSoup(d_resp.content, 'html.parser')
            h2 = dsoup.find('h2', class_='title')
            title = h2.text.strip() if h2 else ''
            clean_title = re.sub(r'^[\[【(]?[a-zA-Z0-9-_]+[\]】)]?\s*', '', title).strip()

            img_tag = dsoup.find('img', class_='video-cover')
            cover_url = urljoin('https://javdb.com', img_tag['src']) if img_tag and img_tag.get('src') else ''
            if any(k in cover_url.lower() for k in ['nopicture', 'noimage', 'dummy']):
                cover_url = ''

            premiered, studio, maker = '', '', ''
            genres, actors = [], []

            for p in dsoup.find_all('p'):
                t = p.text
                if 'Released Date:' in t or '発売日:' in t:
                    m = re.search(r'\d{4}[/-]\d{2}[/-]\d{2}', t)
                    if m: premiered = m.group(0).replace('/', '-')
                elif 'Maker:' in t or 'メーカー:' in t:
                    a = p.find('a')
                    if a: maker, studio = a.text.strip(), a.text.strip()
                elif 'Actor(s):' in t or '出演者:' in t:
                    for a in p.find_all('a'):
                        act = a.text.strip()
                        if act: actors.append({'name': act, 'altname': '', 'thumb': ''})
                elif 'Tags:' in t or 'ジャンル:' in t:
                    for a in p.find_all('a'):
                        g = a.text.strip()
                        if g: genres.append(g)

            if title or cover_url:
                return {
                    'source': 'JavDB-Classic', 'id': movie_id, 'content_id': movie_id.lower().replace('-', ''),
                    'title': clean_title or title, 'originaltitle': clean_title or title,
                    'premiered': premiered, 'year': premiered.split('-')[0] if premiered else '',
                    'director': '', 'studio': studio or maker, 'maker': maker or studio,
                    'label': '', 'series': '', 'rating': '', 'plot': '', 'runtime': '', 'trailer': '',
                    'genres': genres, 'actors': actors, 'cover_url': cover_url, 'sample_images': [], 'is_partial': False
                }
        except (OSError, ValueError):
            continue
    return None

def scrape_surugaya_archive(movie_id: str):
    """[신규 3차 폴백] 스루가야 레트로 아카이브 자동 질의 (DMM 삭제 절판작 완벽 구제)"""
    t_prefix, t_num = normalize_movie_id(movie_id)
    url = f"https://www.suruga-ya.jp/search?search_word={quote(movie_id)}&category=10"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://www.suruga-ya.jp/'
    }
    try:
        resp = HTTP_SESSION.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            item = soup.find('div', class_='item') or soup.find('div', class_='item_box')
            if item:
                title_tag = item.find('p', class_='title') or item.find('a')
                title = title_tag.text.strip() if title_tag else ''

                link_tag = item.find('a', href=True)
                if link_tag and link_tag.get('href'):
                    d_url = urljoin("https://www.suruga-ya.jp", link_tag['href'])
                    d_resp = HTTP_SESSION.get(d_url, headers=headers, timeout=5)
                    if d_resp.status_code == 200:
                        d_soup = BeautifulSoup(d_resp.content, 'html.parser')
                        img_tag = d_soup.find('img', id='main_image') or d_soup.find('img', class_='product_image')
                        cover_url = img_tag.get('src') or '' if img_tag else ''
                        if cover_url and not cover_url.startswith('http'):
                            cover_url = urljoin("https://www.suruga-ya.jp", cover_url)

                        premiered = ''
                        for li in d_soup.find_all(['li', 'tr']):
                            if '発売日' in li.text:
                                m = re.search(r'\d{4}[/-]\d{2}[/-]\d{2}', li.text)
                                if m: premiered = m.group(0).replace('/', '-')

                        maker_map = get_classic_maker_map()
                        studio_name = maker_map.get(t_prefix.upper(), {}).get('studio', t_prefix.upper()) if t_prefix else 'アリスJAPAN'

                        if title or cover_url:
                            return {
                                'source': 'Surugaya-Classic',
                                'id': movie_id,
                                'content_id': movie_id.lower().replace('-', ''),
                                'title': title,
                                'originaltitle': title,
                                'premiered': premiered,
                                'year': premiered.split('-')[0] if premiered else '',
                                'director': '',
                                'studio': studio_name,
                                'maker': studio_name,
                                'label': studio_name,
                                'series': '',
                                'rating': '',
                                'plot': f"{title} (고전 명작 아카이브 복원)",
                                'runtime': '',
                                'trailer': '',
                                'genres': ['고전', studio_name],
                                'actors': [],
                                'cover_url': cover_url,
                                'sample_images': [],
                                'is_partial': False
                            }
    except Exception:
        pass
    return None

def scrape_classic_rescue(movie_id: str):
    # 1차: DMM 고전 모노 아카이브
    dmm_result = scrape_classic_dmm(movie_id)
    if dmm_result and not dmm_result.get('is_partial'):
        return dmm_result

    # 2차: JavDB 고전관
    javdb_result = scrape_classic_javdb(movie_id)
    if javdb_result:
        if dmm_result and dmm_result.get('cover_url'):
            javdb_result['cover_url'] = dmm_result['cover_url']
        return javdb_result

    if dmm_result:
        return dmm_result

    # 3차: DMM에서 영구 삭제된 절판작 ➔ 스루가야 레트로 아카이브 자동 구제
    suru_result = scrape_surugaya_archive(movie_id)
    if suru_result:
        return suru_result

    return None

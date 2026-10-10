import re
import time
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from collector.core.config import HTTP_SESSION, REQUEST_TIMEOUT

def is_dmm_cid_match(cid: str, prefix: str, num_int: int, suffix: str = '') -> bool:
    cid_clean = cid.lower()
    p_clean = prefix.lower()
    s_clean = suffix.lower()
    pattern = rf"{re.escape(p_clean)}0*{num_int}(?!\d)(?:{re.escape(s_clean)})?"
    return bool(re.search(pattern, cid_clean))

def filter_clean_genres(raw_genres: list) -> list:
    blocked_patterns = [
        r'(?i)^sale$', r'セール', r'キャンペーン', r'OFF', r'割引',
        r'特価', r'見放題', r'特集', r'期間限定', r'セット商品', r'まとめ買い'
    ]
    cleaned = []
    for g in raw_genres:
        g_str = g.strip()
        if not g_str:
            continue
        if any(re.search(pat, g_str) for pat in blocked_patterns):
            continue
        if g_str not in cleaned:
            cleaned.append(g_str)
    return cleaned

def scrape_dmm(movie_id: str):
    parts = movie_id.split('-')
    if len(parts) >= 2:
        prefix = parts[0].upper()
        num_m = re.search(r'\d+', parts[1])
        suffix = parts[1][num_m.end():].upper() if num_m else ''
        num_int = int(num_m.group(0)) if num_m else 0
        num_pad = str(num_int).zfill(5)
        cid_query = f"{prefix.lower()}{num_pad}{suffix.lower()}"
    else:
        prefix = movie_id.upper()
        num_int = 0
        suffix = ''
        cid_query = movie_id.replace('-', '').lower()

    search_q1 = quote(movie_id)
    search_q2 = quote(movie_id.replace('-', ' '))
    search_q3 = quote(movie_id.replace('-', ''))

    search_urls = [
        f"https://www.dmm.co.jp/mono/dvd/-/search/=/searchstr={search_q2}/",
        f"https://www.dmm.co.jp/mono/video/-/search/=/searchstr={search_q2}/",
        f"https://www.dmm.co.jp/digital/videoa/-/list/search/=/?searchstr={search_q2}",
        f"https://www.dmm.co.jp/mono/dvd/-/search/=/searchstr={search_q3}/",
        f"https://www.dmm.co.jp/mono/dvd/-/search/=/searchstr={search_q1}/",
        f"https://www.dmm.co.jp/search/=/searchstr={search_q1}/",
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Referer': 'https://www.dmm.co.jp/',
    }

    for s_url in search_urls:
        try:
            resp = HTTP_SESSION.get(s_url, headers=headers, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.content, 'html.parser')
            candidates = []

            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/detail/=/cid=' in href:
                    cid_m = re.search(r'cid=([a-zA-Z0-9_]+)', href)
                    if cid_m:
                        candidate_cid = cid_m.group(1)
                        if is_dmm_cid_match(candidate_cid, prefix, num_int, suffix):
                            full_url = urljoin('https://www.dmm.co.jp', href)
                            candidates.append((candidate_cid, full_url))

            if not candidates:
                continue

            target_cid, target_link = candidates[0]

            detail_resp = HTTP_SESSION.get(target_link, headers=headers, timeout=REQUEST_TIMEOUT)
            if detail_resp.status_code != 200:
                continue

            dsoup = BeautifulSoup(detail_resp.content, 'html.parser')

            # 1. 제목
            title = ""
            h1 = dsoup.find('h1', id='title') or dsoup.find('h1', class_='item-title')
            if h1:
                title = h1.text.strip()
            if not title or title.upper() == 'DOD':
                page_title = dsoup.find('title')
                if page_title:
                    raw_title = page_title.text.split('-')[0].split('|')[0].strip()
                    if raw_title:
                        title = raw_title

            # 2. 커버 이미지
            cover_url = ''
            cover_tag = (
                dsoup.find('a', id='package-src') or 
                dsoup.find('img', class_='tdmm') or 
                dsoup.find('a', class_='package') or
                dsoup.find('a', attrs={'name': 'package-image'}) or
                dsoup.find('img', attrs={'name': 'package-image'})
            )
            if cover_tag:
                raw_c = cover_tag.get('href') or cover_tag.get('src') or ''
                if not any(k in raw_c.lower() for k in ['nowprinting', 'noimage']):
                    cover_url = urljoin('https://www.dmm.co.jp', raw_c).replace('ps.jpg', 'pl.jpg').replace('pr.jpg', 'pl.jpg')

            if not cover_url:
                og_img = dsoup.find('meta', property='og:image') or dsoup.find('meta', attrs={'name': 'twitter:image'})
                if og_img and og_img.get('content'):
                    raw_og = og_img['content'].strip()
                    if not any(k in raw_og.lower() for k in ['nowprinting', 'noimage']):
                        cover_url = raw_og.replace('ps.jpg', 'pl.jpg').replace('pr.jpg', 'pl.jpg')

            # 3. 상세 정보 파싱
            premiered, runtime, director, studio, maker, label, series, rating = '', '', '', '', '', '', '', ''
            raw_genres, actors = [], []

            for tr in dsoup.find_all('tr'):
                text = tr.text
                if any(k in text for k in ['配信開始日', '発売日', '商品発売日', '貸出開始日']):
                    td = tr.find_all(['td', 'th'])[-1]
                    m = re.search(r'\d{4}[/-]\d{2}[/-]\d{2}', td.text)
                    if m: premiered = m.group(0).replace('/', '-')
                elif '収録時間' in text:
                    m = re.search(r'(\d+)', text)
                    if m: runtime = m.group(1)
                elif '監督' in text:
                    a_t = tr.find('a')
                    if a_t: director = a_t.text.strip()
                elif 'メーカー' in text:
                    a_t = tr.find('a')
                    if a_t: maker = a_t.text.strip()
                elif 'レーベル' in text:
                    a_t = tr.find('a')
                    if a_t: label = a_t.text.strip()
                elif 'シリーズ' in text:
                    a_t = tr.find('a')
                    if a_t: series = a_t.text.strip()
                elif 'ジャンル' in text:
                    for a in tr.find_all('a'):
                        g_txt = a.text.strip()
                        if g_txt and g_txt not in raw_genres:
                            raw_genres.append(g_txt)
                elif '出演者' in text or '名前' in text:
                    for act in tr.find_all('a'):
                        act_name = act.text.strip()
                        if act_name and act_name not in ['▼すべて表示する', 'すべて表示する']:
                            actors.append({'name': act_name, 'altname': '', 'thumb': ''})
                elif '平均評価' in text or '評価' in text:
                    m = re.search(r'(\d+(?:\.\d+)?)', text)
                    if m: rating = m.group(1)

            studio = maker or studio

            # 4. 줄거리(Plot)
            plot = ''
            plot_selectors = [
                dsoup.find('div', class_='mg-b20 lh4'),
                dsoup.find('div', class_='clear lh4'),
                dsoup.find('p', class_='mg-b20'),
                dsoup.find('div', class_='d-item__overview'),
                dsoup.find('p', class_='d-item__text'),
                dsoup.find('div', id='introduction'),
                dsoup.find('div', class_='item-description'),
                dsoup.find('div', class_='box-comment'),
            ]
            for ps in plot_selectors:
                if ps and ps.text.strip():
                    plot = ps.text.strip()
                    break

            if not plot:
                meta_desc = dsoup.find('meta', attrs={'name': 'description'}) or dsoup.find('meta', attrs={'property': 'og:description'})
                if meta_desc and meta_desc.get('content'):
                    desc_content = meta_desc['content'].strip()
                    desc_content = re.sub(r'(- DMM\.com|【FANZA】).*$', '', desc_content).strip()
                    if desc_content:
                        plot = desc_content

            # 5. 샘플 갤러리
            sample_images = []
            sample_area = dsoup.find('div', id='sample-image-block') or dsoup.find('div', class_='box-sample-image') or dsoup

            for img in sample_area.find_all('img'):
                src = img.get('data-src') or img.get('src') or ''
                if not src:
                    continue
                if re.search(r'j[sp]-\d+\.jpg', src, re.I):
                    high_res = re.sub(r'js-(\d+\.jpg)', r'jp-\1', src, flags=re.I)
                    full_url = urljoin('https://www.dmm.co.jp', high_res)
                    if full_url not in sample_images:
                        sample_images.append(full_url)
                elif re.search(r'pics\.dmm\.co\.jp/digital/video/.*-\d+\.jpg', src):
                    full_url = urljoin('https://www.dmm.co.jp', src)
                    if full_url not in sample_images:
                        sample_images.append(full_url)

            if title or cover_url:
                return {
                    'source': 'DMM',
                    'id': movie_id,
                    'content_id': target_cid,
                    'title': title,
                    'originaltitle': title,
                    'premiered': premiered,
                    'year': premiered.split('-')[0] if premiered else '',
                    'director': director,
                    'studio': studio,
                    'maker': maker,
                    'label': label,
                    'series': series,
                    'rating': rating,
                    'plot': plot,
                    'runtime': runtime,
                    'trailer': '',
                    'genres': filter_clean_genres(raw_genres),
                    'actors': actors,
                    'cover_url': cover_url,
                    'sample_images': sample_images,
                }
        except Exception:
            continue
    return None
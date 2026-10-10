import re
from bs4 import BeautifulSoup
from collector.core.config import HTTP_SESSION, REQUEST_TIMEOUT

def scrape_uncensored_date(date_id: str):
    """캐리비안(일반/PR), 1Pondo, 10Musume, Pacopacomama 날짜형(MMDDYY-NNN) 전방위 포획"""
    m = re.search(r'(\d{6})[-_](\d{3,4})', date_id)
    if not m:
        return None
    d_str, s_str = m.group(1), m.group(2)
    cid_hyphen = f"{d_str}-{s_str}"
    cid_under = f"{d_str}_{s_str}"
    rel_date = f"20{d_str[4:6]}-{d_str[0:2]}-{d_str[2:4]}"
    rel_year = f"20{d_str[4:6]}"

    headers_common = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
    }

    # 1. 一本道 (1Pondo) 공식 초고속 JSON API
    try:
        pondo_api = f"https://www.1pondo.tv/dyn/ren/movie_details/movie_id/{cid_under}.json"
        p_headers = headers_common.copy()
        p_headers['Referer'] = 'https://www.1pondo.tv/'
        resp = HTTP_SESSION.get(pondo_api, headers=p_headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and data.get('Title'):
                actors = [{'name': a, 'altname': '', 'thumb': ''} for a in data.get('Actresses', [])]
                cover = data.get('ThumbHigh') or data.get('ThumbMed') or f"https://www.1pondo.tv/assets/sample/{cid_under}/popu.jpg"
                return {
                    'source': '1Pondo-Official',
                    'id': cid_hyphen,
                    'title': data['Title'],
                    'originaltitle': data['Title'],
                    'premiered': data.get('Release', rel_date),
                    'year': rel_year,
                    'studio': '1Pondo',
                    'maker': '1Pondo',
                    'label': '1Pondo',
                    'director': '',
                    'rating': '',
                    'plot': data.get('Desc', ''),
                    'runtime': str(data.get('Duration', '')),
                    'trailer': '',
                    'genres': ['무삭제', '一本道'],
                    'actors': actors,
                    'cover_url': cover,
                    'sample_images': []
                }
    except Exception:
        pass

    # 2. 캐리비안컴 (Caribbeancom) & 캐리비안 프리미엄 (CaribbeancomPR)
    try:
        c_targets = [
            ("https://www.caribbeancom.com", f"https://www.caribbeancom.com/moviepages/{cid_hyphen}/index.html", f"https://www.caribbeancom.com/moviepages/{cid_hyphen}/images/l_l.jpg", "Caribbeancom"),
            ("https://www.caribbeancom.com", f"https://www.caribbeancom.com/moviepages/{cid_under}/index.html", f"https://www.caribbeancom.com/moviepages/{cid_under}/images/l_l.jpg", "Caribbeancom"),
            ("https://www.caribbeancompr.com", f"https://www.caribbeancompr.com/moviepages/{cid_hyphen}/index.html", f"https://www.caribbeancompr.com/moviepages/{cid_hyphen}/images/l_l.jpg", "Caribbeancom Premium"),
            ("https://www.caribbeancompr.com", f"https://www.caribbeancompr.com/moviepages/{cid_under}/index.html", f"https://www.caribbeancompr.com/moviepages/{cid_under}/images/l_l.jpg", "Caribbeancom Premium"),
        ]
        for base_site, c_url, c_cover, c_studio in c_targets:
            c_headers = headers_common.copy()
            c_headers['Referer'] = f"{base_site}/"
            resp = HTTP_SESSION.get(c_url, headers=c_headers, timeout=5)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                h1 = soup.find('h1', itemprop='name') or soup.find('div', class_='video-detail') or soup.find('h1')
                title = h1.text.strip() if h1 else f"{c_studio} {cid_hyphen}"
                actors = []
                for a in soup.find_all('a', href=re.compile(r'/search/|/moviepages/')):
                    act = a.text.strip()
                    if act and len(act) <= 10 and act not in ['カリビアンコム', '動画', 'プレミアム', 'Caribbeancom']:
                        if act not in [x['name'] for x in actors]:
                            actors.append({'name': act, 'altname': '', 'thumb': ''})
                plot_div = soup.find('p', itemprop='description') or soup.find('div', class_='movie-comment')
                plot = plot_div.text.strip() if plot_div else ''
                return {
                    'source': f'{c_studio}-Official',
                    'id': cid_hyphen,
                    'title': title,
                    'originaltitle': title,
                    'premiered': rel_date,
                    'year': rel_year,
                    'studio': c_studio,
                    'maker': c_studio,
                    'label': c_studio,
                    'director': '',
                    'rating': '',
                    'plot': plot,
                    'runtime': '',
                    'trailer': '',
                    'genres': ['무삭제', '노모'],
                    'actors': actors,
                    'cover_url': c_cover,
                    'sample_images': []
                }
    except Exception:
        pass

    # 3. 천연무스메 (10Musume) 공식 API
    try:
        musume_api = f"https://www.10musume.com/dyn/ren/movie_details/movie_id/{cid_under}.json"
        m_headers = headers_common.copy()
        m_headers['Referer'] = 'https://www.10musume.com/'
        resp = HTTP_SESSION.get(musume_api, headers=m_headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and data.get('Title'):
                actors = [{'name': a, 'altname': '', 'thumb': ''} for a in data.get('Actresses', [])]
                cover = data.get('ThumbHigh') or f"https://www.10musume.com/moviepages/{cid_under}/images/l_l.jpg"
                return {
                    'source': '10Musume-Official',
                    'id': cid_hyphen,
                    'title': data['Title'],
                    'originaltitle': data['Title'],
                    'premiered': data.get('Release', rel_date),
                    'year': rel_year,
                    'studio': '10Musume',
                    'maker': '10Musume',
                    'label': '10Musume',
                    'director': '',
                    'rating': '',
                    'plot': data.get('Desc', ''),
                    'runtime': '',
                    'trailer': '',
                    'genres': ['무삭제', '天然むすめ'],
                    'actors': actors,
                    'cover_url': cover,
                    'sample_images': []
                }
    except Exception:
        pass

    # 4. 파코파코마마 (Pacopacomama) 공식 API
    try:
        paco_api = f"https://www.pacopacomama.com/dyn/ren/movie_details/movie_id/{cid_under}.json"
        pa_headers = headers_common.copy()
        pa_headers['Referer'] = 'https://www.pacopacomama.com/'
        resp = HTTP_SESSION.get(paco_api, headers=pa_headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and data.get('Title'):
                actors = [{'name': a, 'altname': '', 'thumb': ''} for a in data.get('Actresses', [])]
                cover = data.get('ThumbHigh') or f"https://www.pacopacomama.com/moviepages/{cid_under}/images/l_l.jpg"
                return {
                    'source': 'Pacopacomama-Official',
                    'id': cid_hyphen,
                    'title': data['Title'],
                    'originaltitle': data['Title'],
                    'premiered': data.get('Release', rel_date),
                    'year': rel_year,
                    'studio': 'Pacopacomama',
                    'maker': 'Pacopacomama',
                    'label': 'Pacopacomama',
                    'director': '',
                    'rating': '',
                    'plot': data.get('Desc', ''),
                    'runtime': '',
                    'trailer': '',
                    'genres': ['무삭제', 'パコパコママ'],
                    'actors': actors,
                    'cover_url': cover,
                    'sample_images': []
                }
    except Exception:
        pass

    # 5. Jav321 다이렉트 릴레이
    try:
        from scrapers.jav321 import scrape_jav321
        for query_id in [cid_under, cid_hyphen]:
            j_res = scrape_jav321(query_id)
            if j_res and (j_res.get('title') or j_res.get('cover_url')):
                j_res['id'] = cid_hyphen
                return j_res
    except Exception:
        pass

    # 6. JavBus 노모관 다이렉트 릴레이
    try:
        from scrapers.javbus import scrape_javbus
        for q in [cid_hyphen, cid_under]:
            jb_res = scrape_javbus(q)
            if jb_res and (jb_res.get('title') or jb_res.get('cover_url')):
                jb_res['id'] = cid_hyphen
                return jb_res
    except Exception:
        pass

    return None

scrape_caribbean = scrape_uncensored_date

def scrape_fc2(fc2_id: str):
    """FC2 공식 성인 아카이브 + Jav321 연동"""
    m = re.search(r'\d{5,8}', fc2_id)
    if not m:
        return None
    num = m.group(0)

    try:
        from scrapers.jav321 import scrape_jav321
        for q in [num, f"FC2-{num}", f"FC2-PPV-{num}"]:
            j_res = scrape_jav321(q)
            if j_res and (j_res.get('title') or j_res.get('cover_url')):
                j_res['id'] = f"FC2-PPV-{num}"
                return j_res
    except Exception:
        pass

    url = f"https://adult.contents.fc2.com/article/{num}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://adult.contents.fc2.com/',
    }
    cookies = {'adult_checked': '1'}
    try:
        resp = HTTP_SESSION.get(url, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.content, 'html.parser')
            h3 = soup.find('h3') or soup.find('div', class_='items_article_headerInfo')
            title = h3.text.strip() if h3 else f"FC2-PPV-{num}"
            
            cover_url = ""
            img = soup.find('img', class_='items_article_MaincntTop')
            if not img and soup.find('section', class_='items_article_MaincntTop'):
                img = soup.find('section', class_='items_article_MaincntTop').find('img')
            if img and img.get('src'):
                src = img['src']
                cover_url = src if src.startswith('http') else f"https:{src}"
                
            return {
                'source': 'FC2-Official',
                'id': f"FC2-PPV-{num}",
                'title': title,
                'originaltitle': title,
                'premiered': '',
                'year': '',
                'studio': 'FC2-PPV',
                'maker': 'FC2-PPV',
                'label': 'FC2',
                'director': '',
                'rating': '',
                'plot': '',
                'runtime': '',
                'trailer': '',
                'genres': ['FC2', 'PPV'],
                'actors': [],
                'cover_url': cover_url,
                'sample_images': []
            }
    except Exception:
        pass

    return None

def scrape_heyzo(movie_id: str):
    """HEYZO 공식 사이트 직결 포획 (0331 및 331 규격 완벽 대응)"""
    m = re.search(r'\d{3,5}', movie_id)
    if not m:
        return None
    raw_num = m.group(0)
    num_4 = raw_num.zfill(4)      # 0331
    num_clean = str(int(raw_num))  # 331

    for n_str in [num_4, num_clean]:
        url = f"https://www.heyzo.com/moviepages/{n_str}/index.html"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
            'Referer': 'https://www.heyzo.com/',
        }
        try:
            resp = HTTP_SESSION.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                h1 = soup.find('h1')
                title = h1.text.strip() if h1 else f"HEYZO-{num_4}"
                cover = f"https://www.heyzo.com/contents/3000/{num_4}/gallery/001.jpg"
                
                actors = []
                act_tag = soup.find('span', class_='actor') or soup.find('tr', class_='table-actor')
                if act_tag:
                    for a in act_tag.find_all('a'):
                        act_name = a.text.strip()
                        if act_name:
                            actors.append({'name': act_name, 'altname': '', 'thumb': ''})

                return {
                    'source': 'HEYZO-Official',
                    'id': f"HEYZO-{num_4}",
                    'title': title,
                    'originaltitle': title,
                    'premiered': '',
                    'year': '',
                    'studio': 'HEYZO',
                    'maker': 'HEYZO',
                    'label': 'HEYZO',
                    'director': '',
                    'rating': '',
                    'plot': '',
                    'runtime': '',
                    'trailer': '',
                    'genres': ['무삭제', 'HEYZO'],
                    'actors': actors,
                    'cover_url': cover,
                    'sample_images': []
                }
        except Exception:
            continue
    return None

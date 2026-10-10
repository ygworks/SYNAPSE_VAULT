# [FILE] scrapers/javlibrary.py
import re
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from collector.core.config import HTTP_SESSION, REQUEST_TIMEOUT
from collector.core.parser import match_movie_id

def scrape_javlibrary(movie_id: str):
    """
    [JavLibrary 구작 전용 스크래퍼] 성인 인증 쿠키 및 Referer 헤더 우회 완비
    """
    url = f"https://www.javlibrary.com/ja/vl_searchbyid.php?keyword={quote(movie_id)}"
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        ),
        'Referer': 'https://www.javlibrary.com/ja/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
    }
    cookies = {
        'over18': '18',
        'locale': 'ja'
    }

    try:
        resp = HTTP_SESSION.get(url, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return None
        
        soup = BeautifulSoup(resp.content, 'html.parser')
        
        # 목록으로 나올 때 타깃 품번과 일치하는 항목 선택
        if 'vl_searchbyid' in resp.url and soup.find('div', class_='videos'):
            target_a = None
            for vid in soup.find_all('div', class_='video'):
                if match_movie_id(movie_id, vid.text):
                    target_a = vid.find('a')
                    break
            if not target_a:
                return None
            detail_url = urljoin("https://www.javlibrary.com/ja/", target_a['href'])
            resp = HTTP_SESSION.get(detail_url, headers=headers, cookies=cookies, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.content, 'html.parser')

        title_tag = soup.find('h3', class_='post-title')
        if not title_tag: 
            return None
        
        title = title_tag.text.strip()
        
        if not match_movie_id(movie_id, title):
            return None

        clean_title = re.sub(r'^[\[【(]?[a-zA-Z0-9-_]+[\]】)]?\s*', '', title).strip()

        cover_img = soup.find('img', id='video_jacket_img')
        cover_url = cover_img.get('src', '') if cover_img else ''
        if cover_url and not cover_url.startswith('http'): 
            cover_url = urljoin("https://www.javlibrary.com/ja/", cover_url)

        premiered, studio, label = '', '', ''
        genres, actors = [], []

        for row in soup.find_all('div', class_='item'):
            text = row.text
            if '発売日:' in text:
                m = re.search(r'\d{4}-\d{2}-\d{2}', text)
                if m: premiered = m.group(0)
            elif 'メーカー:' in text:
                a = row.find('a')
                if a: studio = a.text.strip()
            elif 'レーベル:' in text:
                a = row.find('a')
                if a: label = a.text.strip()
            elif 'ジャンル:' in text:
                for a in row.find_all('a'): 
                    genres.append(a.text.strip())
            elif '出演者:' in text:
                for a in row.find_all('a'):
                    actors.append({'name': a.text.strip(), 'altname': '', 'thumb': ''})

        return {
            'source': 'JavLibrary',
            'id': movie_id,
            'title': clean_title or title,
            'originaltitle': clean_title or title,
            'premiered': premiered,
            'year': premiered.split('-')[0] if premiered else '',
            'director': '',
            'studio': studio,
            'maker': studio,
            'label': label,
            'series': '',
            'rating': '',
            'plot': '',
            'runtime': '',
            'trailer': '',
            'genres': genres,
            'actors': actors,
            'cover_url': cover_url,
            'sample_images': []
        }
    except Exception:
        return None
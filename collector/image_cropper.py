import io
import os
import re
import shutil
from urllib.parse import urlparse
from PIL import Image, ImageFile, ImageStat
from collector.core.config import HTTP_SESSION, REQUEST_TIMEOUT

ImageFile.LOAD_TRUNCATED_IMAGES = True

DUMMY_URL_KEYWORDS = [
    'nowprinting', 'now_printing', 'noimage', 'no_image',
    'nopicture', 'dummy', 'placehold', 'default_cover'
]

def get_image_headers(url: str) -> dict:
    """도메인별 맞춤 Referer 헤더 주입 (FC2, 캐리비안, 1Pondo 403 차단 해제)"""
    u = url.lower()
    headers = {
        'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
        'Sec-Ch-Ua': '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'image',
        'Sec-Fetch-Mode': 'no-cors',
        'Sec-Fetch-Site': 'cross-site',
    }
    
    if 'fc2' in u:
        # [핵심] FC2 이미지 CDN 403 차단 완벽 해제
        headers['Referer'] = 'https://adult.contents.fc2.com/'
    elif 'dmm.co.jp' in u or 'dmm.com' in u:
        headers['Referer'] = 'https://www.dmm.co.jp/'
    elif 'javbus' in u or 'javcdn' in u:
        headers['Referer'] = 'https://www.javbus.com/'
    elif 'javdb' in u or 'jdbstatic' in u:
        headers['Referer'] = 'https://javdb.com/'
    elif 'javlibrary' in u:
        headers['Referer'] = 'https://www.javlibrary.com/'
    elif 'jav321' in u:
        headers['Referer'] = 'https://www.jav321.com/'
    elif 'r18.dev' in u:
        headers['Referer'] = 'https://r18.dev/'
    elif 'tokyo-hot' in u:
        headers['Referer'] = 'https://my.tokyo-hot.com/'
    elif 'caribbeancom' in u:
        headers['Referer'] = 'https://www.caribbeancom.com/'
    elif '1pondo' in u:
        headers['Referer'] = 'https://www.1pondo.tv/'
    elif 'heyzo' in u:
        headers['Referer'] = 'https://www.heyzo.com/'
    else:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            headers['Referer'] = f"{parsed.scheme}://{parsed.netloc}/"
            
    return headers

def is_blank_or_dummy_image(img: Image.Image) -> bool:
    try:
        w, h = img.size
        if w < 80 or h < 80:
            return True

        gray = img.convert('L')
        extrema = gray.getextrema()
        if extrema[0] == extrema[1]:
            return True

        stat = ImageStat.Stat(gray)
        if stat.stddev[0] < 3.0:
            return True

        return False
    except (OSError, ValueError):
        return True

def download_image_with_fallbacks(url: str):
    if not url:
        return None

    url = url.strip()
    if url.startswith('//'):
        url = 'https:' + url
    elif not url.startswith('http'):
        return None

    if any(k in url.lower() for k in DUMMY_URL_KEYWORDS):
        return None

    urls_to_try = [url]
    if 'pl.jpg' in url:
        urls_to_try.append(url.replace('pl.jpg', 'ps.jpg'))
        urls_to_try.append(url.replace('pl.jpg', 'pr.jpg'))
    elif '_b.jpg' in url:
        urls_to_try.append(url.replace('_b.jpg', '.jpg'))

    for u in list(dict.fromkeys(urls_to_try)):
        try:
            headers = get_image_headers(u)
            resp = HTTP_SESSION.get(u, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            
            if resp.status_code != 200:
                continue

            final_url = resp.url.lower()
            if any(k in final_url for k in DUMMY_URL_KEYWORDS):
                continue
            if any(any(k in r.url.lower() for k in DUMMY_URL_KEYWORDS) for r in resp.history):
                continue

            if len(resp.content) < 1200:
                continue

            with Image.open(io.BytesIO(resp.content)) as test_img:
                if is_blank_or_dummy_image(test_img):
                    continue

            return resp.content
        except (OSError, ValueError):
            continue
            
    return None

def is_file_valid_image(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        if os.path.getsize(path) < 100:
            return False
        with Image.open(path) as img:
            w, h = img.size
            if w < 10 or h < 10:
                return False
        return True
    except Exception:
        return False

def save_images(target_dir: str, file_stem: str, base_id: str, cover_url: str):
    poster_path = os.path.join(target_dir, f"{file_stem}-poster.jpg")
    fanart_path = os.path.join(target_dir, f"{file_stem}-fanart.jpg")

    if is_file_valid_image(poster_path) and is_file_valid_image(fanart_path):
        return poster_path

    exact_pattern = re.compile(rf'^{re.escape(base_id)}(?:[-_ ][a-zA-Z0-9가-힣]+)?-(poster|fanart)\.jpg$', re.I)
    try:
        existing_assets = [f for f in os.listdir(target_dir) if exact_pattern.match(f)]
        for ex in existing_assets:
            src = os.path.join(target_dir, ex)
            if ex.lower().endswith('-poster.jpg') and not is_file_valid_image(poster_path):
                shutil.copyfile(src, poster_path)
            elif ex.lower().endswith('-fanart.jpg') and not is_file_valid_image(fanart_path):
                shutil.copyfile(src, fanart_path)
    except OSError:
        pass

    if is_file_valid_image(poster_path) and is_file_valid_image(fanart_path):
        return poster_path

    img_bytes = download_image_with_fallbacks(cover_url)
    if not img_bytes:
        return None

    try:
        with Image.open(io.BytesIO(img_bytes)) as raw_img:
            if is_blank_or_dummy_image(raw_img):
                return None

            img = raw_img.convert('RGB') if raw_img.mode != 'RGB' else raw_img.copy()
            width, height = img.size

            if not is_file_valid_image(fanart_path):
                img.save(fanart_path, 'JPEG', quality=95)

            if not is_file_valid_image(poster_path):
                if width > height and (width / height) >= 1.25:
                    left = round(width / 1.895734597)
                    cropped = img.crop((left, 0, width, height))
                    cropped.save(poster_path, 'JPEG', quality=95)
                else:
                    img.save(poster_path, 'JPEG', quality=95)

        if is_file_valid_image(poster_path):
            return poster_path
        return None
    except Exception:
        return None

def sync_local_assets(root_dir: str, stem: str, prefix: str) -> tuple:
    poster_path = os.path.join(root_dir, f"{stem}-poster.jpg")
    fanart_path = os.path.join(root_dir, f"{stem}-fanart.jpg")

    has_poster = is_file_valid_image(poster_path)
    has_fanart = is_file_valid_image(fanart_path)

    if has_poster and has_fanart:
        return True, True

    base_stem = re.sub(r'(?i)[-_ ]+(?:[a-d]|pt\d+|part\d+|cd\d+|\d)$', '', stem)
    num_match = re.search(r'(\d{5,8}|\d{6}[-_]\d{3,4})', stem)
    clean_id = num_match.group(0) if num_match else base_stem

    try:
        for sib in os.listdir(root_dir):
            if sib.startswith(stem):
                continue
            if clean_id.lower() not in sib.lower():
                continue

            if sib.endswith('-poster.jpg') and not has_poster:
                src_p = os.path.join(root_dir, sib)
                if is_file_valid_image(src_p):
                    shutil.copyfile(src_p, poster_path)
                    has_poster = True
            if sib.endswith('-fanart.jpg') and not has_fanart:
                src_f = os.path.join(root_dir, sib)
                if is_file_valid_image(src_f):
                    shutil.copyfile(src_f, fanart_path)
                    has_fanart = True
    except OSError:
        pass

    if has_fanart and not has_poster:
        try:
            with Image.open(fanart_path) as f_img:
                w, h = f_img.size
                if w > h and (w / h) >= 1.25:
                    left = round(w / 1.895734597)
                    f_img.crop((left, 0, w, h)).convert('RGB').save(poster_path, 'JPEG', quality=95)
                    has_poster = True
        except Exception:
            pass

    return has_poster, has_fanart

def crop_wide_poster_safely(poster_path: str) -> dict:
    if not os.path.exists(poster_path) or not is_file_valid_image(poster_path):
        return None

    try:
        with Image.open(poster_path) as raw_img:
            w, h = raw_img.size
            if w <= h or (w / h) < 1.15:
                return {'status': 'skip', 'reason': '이미 정상 세로 포스터'}

            folder = os.path.dirname(poster_path)
            fname = os.path.basename(poster_path)
            stem = fname.replace('-poster.jpg', '')
            fanart_path = os.path.join(folder, f"{stem}-fanart.jpg")

            backup_dir = os.path.join(folder, "_재단전_원본포스터_백업")
            os.makedirs(backup_dir, exist_ok=True)
            backup_path = os.path.join(backup_dir, fname)
            shutil.copyfile(poster_path, backup_path)

            if not is_file_valid_image(fanart_path):
                shutil.copyfile(poster_path, fanart_path)

            target_w = int(round(h * 0.7039))
            left = max(0, w - target_w)
            cropped = raw_img.crop((left, 0, w, h)).convert('RGB')

            tmp_crop = poster_path + ".crop_tmp"
            cropped.save(tmp_crop, 'JPEG', quality=95)
            os.replace(tmp_crop, poster_path)

            return {
                'status': 'cropped',
                'file': fname,
                'orig_size': f"{w}x{h}",
                'crop_size': f"{cropped.size[0]}x{cropped.size[1]}",
                'backup_path': backup_path,
                'poster_path': poster_path
            }
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}

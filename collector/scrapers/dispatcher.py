import re
from collector.core.parser import match_movie_id, normalize_movie_id
from scrapers.classic import CLASSIC_MAKER_MAP, scrape_classic_rescue
from scrapers.dmm import scrape_dmm
from scrapers.jav321 import scrape_jav321
from scrapers.javbus import scrape_javbus
from scrapers.javlibrary import scrape_javlibrary
from scrapers.r18dev import scrape_r18dev
from scrapers.uncensored import scrape_caribbean, scrape_fc2, scrape_heyzo

def has_cjk(text: str) -> bool:
    if not text:
        return False
    return bool(re.search(r'[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]', text))

def is_classic_label(movie_id: str) -> bool:
    prefix, _ = normalize_movie_id(movie_id)
    return bool(prefix and prefix.upper() in CLASSIC_MAKER_MAP)

def clean_query_id(raw_id: str) -> str:
    c = re.sub(r'(?i)[-_ ]+[a-dA-D]$', '', raw_id.strip())
    c = re.sub(r'(?i)[-_ ]+(?:part|pt|cd)[-_ ]*\d+$', '', c)
    return c

def _merge_metadata(base_meta: dict, supplement_meta: dict) -> dict:
    if not base_meta:
        return supplement_meta
    if not supplement_meta:
        return base_meta

    if not base_meta.get('title') and supplement_meta.get('title'):
        base_meta['title'] = supplement_meta['title']
        base_meta['originaltitle'] = supplement_meta.get('originaltitle') or supplement_meta['title']

    b_plot = base_meta.get('plot', '') or ''
    s_plot = supplement_meta.get('plot', '') or ''
    if len(s_plot.strip()) > len(b_plot.strip()):
        base_meta['plot'] = s_plot

    b_actors = base_meta.get('actors', [])
    s_actors = supplement_meta.get('actors', [])
    if not b_actors and s_actors:
        base_meta['actors'] = s_actors
    elif b_actors and s_actors:
        if not has_cjk(b_actors[0].get('name', '')) and has_cjk(s_actors[0].get('name', '')):
            base_meta['actors'] = s_actors

    for key in ['cover_url', 'sample_images', 'maker', 'studio', 'label', 'series', 'runtime', 'premiered', 'year', 'director', 'rating']:
        if not base_meta.get(key) and supplement_meta.get(key):
            base_meta[key] = supplement_meta[key]

    if not base_meta.get('genres') and supplement_meta.get('genres'):
        base_meta['genres'] = supplement_meta['genres']

    return base_meta

def _fetch_single_target(target_id: str, scraper_opts=None, is_classic_mode=False):
    q_id = clean_query_id(target_id)
    auto_classic = is_classic_mode or is_classic_label(q_id)
    t_prefix, _ = normalize_movie_id(q_id)
    is_uncen_or_fc2 = (t_prefix in ['FC2', 'DATE']) or q_id.upper().startswith(('FC2', 'PPV', 'HEYZO', 'CWP', 'CWM'))

    primary = None
    saved_cover = ""

    def get_valid_data(scraper_func):
        try:
            data = scraper_func(q_id)
            if data:
                cand_text = f"{data.get('id', '')} {data.get('title', '')}"
                if match_movie_id(q_id, cand_text):
                    return data
        except Exception:
            pass
        return None

    # 트랙 1: 고전 80대 레이블
    if auto_classic:
        classic_data = scrape_classic_rescue(q_id)
        if classic_data:
            if not classic_data.get('is_partial') and classic_data.get('title') and classic_data.get('cover_url'):
                return classic_data
            saved_cover = classic_data.get('cover_url', '')
            primary = classic_data

    use_r18 = scraper_opts.get('r18dev', True) if scraper_opts else True
    use_dmm = scraper_opts.get('dmm', True) if scraper_opts else True
    use_javbus = scraper_opts.get('javbus', True) if scraper_opts else True
    use_javlib = scraper_opts.get('javlibrary', True) if scraper_opts else True
    use_jav321 = scraper_opts.get('jav321', True) if scraper_opts else True

    # 트랙 2: FC2, HEYZO 및 무삭제 유출작 공인 직결
    if is_uncen_or_fc2:
        if 'HEYZO' in q_id.upper():
            cand = scrape_heyzo(q_id)
            primary = _merge_metadata(primary, cand)
        elif t_prefix == 'DATE':
            cand = scrape_caribbean(q_id)
            primary = _merge_metadata(primary, cand)
        elif t_prefix == 'FC2' or 'FC2' in q_id.upper():
            cand = scrape_fc2(q_id)
            primary = _merge_metadata(primary, cand)

        if use_jav321 and (not primary or not primary.get('title')):
            cand = get_valid_data(scrape_jav321)
            primary = _merge_metadata(primary, cand)

        if not primary or not primary.get('title'):
            cand = scrape_classic_rescue(q_id)
            primary = _merge_metadata(primary, cand)

        if use_javbus and (not primary or not primary.get('title')):
            cand = get_valid_data(scrape_javbus)
            primary = _merge_metadata(primary, cand)

        if saved_cover and not primary.get('cover_url'):
            primary['cover_url'] = saved_cover
        return primary

    # 트랙 3 & 4: 일반 정규작 순차 릴레이
    if use_r18 and (not primary or not primary.get('title')):
        cand = get_valid_data(scrape_r18dev)
        primary = _merge_metadata(primary, cand)

    if use_dmm and (not primary or not primary.get('title')):
        cand = get_valid_data(scrape_dmm)
        primary = _merge_metadata(primary, cand)

    if use_javbus and (not primary or not primary.get('title')):
        cand = get_valid_data(scrape_javbus)
        primary = _merge_metadata(primary, cand)

    if use_javlib and (not primary or not primary.get('title')):
        cand = get_valid_data(scrape_javlibrary)
        primary = _merge_metadata(primary, cand)

    if use_jav321 and (not primary or not primary.get('title')):
        cand = get_valid_data(scrape_jav321)
        primary = _merge_metadata(primary, cand)

    if (not primary or not primary.get('title')) and not auto_classic:
        cand = scrape_classic_rescue(q_id)
        primary = _merge_metadata(primary, cand)

    if not primary:
        return None

    if saved_cover and not primary.get('cover_url'):
        primary['cover_url'] = saved_cover

    curr_plot = primary.get('plot', '') or ''
    has_samples = bool(primary.get('sample_images'))

    if (len(curr_plot.strip()) < 30 or not has_samples) and use_dmm:
        dmm_sup = get_valid_data(scrape_dmm)
        primary = _merge_metadata(primary, dmm_sup)
        curr_plot = primary.get('plot', '') or ''

    if len(curr_plot.strip()) < 30 and use_jav321:
        jav321_sup = get_valid_data(scrape_jav321)
        primary = _merge_metadata(primary, jav321_sup)

    return primary

def fetch_metadata(movie_id: str, candidate_ids=None, scraper_opts=None, is_classic_mode=False):
    if not candidate_ids:
        candidate_ids = [movie_id]
    elif movie_id not in candidate_ids:
        candidate_ids = [movie_id] + candidate_ids

    for cid in list(dict.fromkeys(candidate_ids)):
        meta = _fetch_single_target(cid, scraper_opts=scraper_opts, is_classic_mode=is_classic_mode)
        if meta and (meta.get('title') or meta.get('cover_url')):
            if not meta.get('id'):
                meta['id'] = movie_id
            return meta

    return None

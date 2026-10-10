import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

REQUEST_TIMEOUT = (3.05, 10.0)

def get_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504], raise_on_status=False)
    adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=retries)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'ja,ko;q=0.9,en-US;q=0.8,en;q=0.7',
    })
    session.cookies.set('age_check_done', '1', domain='.dmm.co.jp', path='/')
    session.cookies.set('over18', '18', domain='.dmm.co.jp', path='/')
    session.cookies.set('over18', '1', domain='.javdb.com', path='/')
    session.cookies.set('over18', '18', domain='.javlibrary.com', path='/')
    for domain in ['.caribbeancom.com', '.1pondo.tv', '.10musume.com', '.pacopacomama.com']:
        session.cookies.set('agree', '1', domain=domain, path='/')
    return session

HTTP_SESSION = get_session()

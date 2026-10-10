import re

def normalize_movie_id(raw_id: str):
    if not raw_id:
        return None, None
    date_m = re.search(r'(\d{6})[-_](\d{3,4})', raw_id)
    if date_m:
        return 'DATE', f"{date_m.group(1)}-{date_m.group(2)}"
    fc2_m = re.search(r'(?i)(?:fc2[-_ ]*(?:ppv)?|ppv)[-_ ]*(\d{5,8})', raw_id)
    if fc2_m:
        return 'FC2', int(fc2_m.group(1))
    if re.match(r'^\d{6,8}$', raw_id.strip()):
        return 'FC2', int(raw_id.strip())
    m = re.search(r'([a-zA-Z][a-zA-Z0-9]{0,14})[-_]?(\d{1,8})', raw_id)
    if m:
        return m.group(1).upper(), int(m.group(2))
    return None, None

def match_movie_id(target_id: str, candidate_text: str) -> bool:
    if not target_id or not candidate_text:
        return False
    t_prefix, t_num = normalize_movie_id(target_id)
    if not t_prefix or t_num is None:
        return False
    if t_prefix == 'DATE':
        return t_num in candidate_text.replace('_', '-')
    if t_prefix == 'FC2':
        return bool(re.search(rf'(?i)(?:fc2|ppv)?[-_ ]*{t_num}\b', candidate_text))
    candidates = re.findall(r'([a-zA-Z][a-zA-Z0-9]{0,14})[-_]?(\d{1,8})', candidate_text)
    for c_prefix, c_num_str in candidates:
        if c_prefix.upper() == t_prefix and int(c_num_str) == t_num:
            return True
    return False

from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from .timeline import parse_timeline_script, build_timeline_raw


_DT_KEY_MAP = {
    'スコア': 'score',
    '撃墜': 'kills',
    '被撃墜': 'deaths',
    '与ダメージ': 'damage_dealt',
    '被ダメージ': 'damage_received',
    'EXバーストダメージ': 'exburst_damage',
}


def _strip_query(url):
    return url.split('?')[0] if url else url


def _parse_team_members(box):
    """
    Parse panel1 team box.

    Returns {team_name, players: [{name, player_param, icon_url, mastery, prefecture}]}
    """
    team_name_el = box.select_one('h3 p.tag-name')
    team_name = team_name_el.get_text(strip=True) if team_name_el else ''

    players = []
    for li in box.select('li.item'):
        name_el = li.select_one('span.name')
        icon_el = li.select_one('img.item-icon-img[data-original]')
        mastery_el = li.select_one('span.mastery')
        pref_el = li.select_one('p.col-stand.fz-s')
        profile_a = li.select_one('a.right-arrow[href*="profile"]')

        name = name_el.get_text(strip=True) if name_el else ''
        icon_url = _strip_query(icon_el['data-original']) if icon_el else ''

        player_param = None
        if profile_a:
            qs = parse_qs(urlparse(profile_a['href']).query)
            player_param = qs.get('param', [None])[0]

        mastery = None
        if mastery_el:
            extra = [c for c in mastery_el.get('class', []) if c != 'mastery']
            mastery = extra[0] if extra else None

        prefecture = pref_el.get_text(strip=True) if pref_el else None

        players.append({
            'name': name,
            'player_param': player_param,
            'icon_url': icon_url,
            'mastery': mastery,
            'prefecture': prefecture,
        })

    return {'team_name': team_name, 'players': players}


def _parse_score_box(box):
    """
    Parse panel3 score box.

    Returns list of {icon_url, match_rank, score, kills, deaths,
                     damage_dealt, damage_received, exburst_damage}
    """
    player_scores = []
    for li in box.select('li.item'):
        icon_el = li.select_one('img.item-icon-img[data-original]')
        icon_url = _strip_query(icon_el['data-original']) if icon_el else ''

        match_rank = None
        for cls in li.get('class', []):
            if cls.startswith('rank-band'):
                try:
                    match_rank = int(cls.replace('rank-band', ''))
                except ValueError:
                    pass

        scores = {}
        for dl in li.find_all('dl'):
            dt = dl.find('dt')
            dd = dl.find('dd')
            if not (dt and dd):
                continue
            key = _DT_KEY_MAP.get(dt.get_text(strip=True))
            if key:
                raw = ''.join(t.strip() for t in dd.find_all(string=True, recursive=False)).strip()
                try:
                    scores[key] = int(raw)
                except ValueError:
                    scores[key] = raw

        player_scores.append({'icon_url': icon_url, 'match_rank': match_rank, **scores})
    return player_scores


def _merge_scores(team, score_list):
    """Merge score data into team players matched by icon_url."""
    used = set()
    for player in team['players']:
        for i, entry in enumerate(score_list):
            if i not in used and entry['icon_url'] == player['icon_url']:
                player.update({k: v for k, v in entry.items() if k != 'icon_url'})
                used.add(i)
                break


def parse_match(html, result_self, self_name):
    """
    Parse a match_detail page.

    Args:
        result_self: 'win' or 'lose' (from daily_detail anchor class)
        self_name:   the logged-in player's name

    Returns:
        {
            team_a: {team_name, result, players: [...]},
            team_b: {team_name, result, players: [...]},
            timeline_raw: {groups, events, game_end_cs, game_end_str} or None,
        }
    """
    soup = BeautifulSoup(html, 'html.parser')

    # --- Panel 1: Members ---
    panel1 = soup.find('div', id='panel1')
    p1_boxes = panel1.find_all('div', class_='box', recursive=False)

    team_a = _parse_team_members(p1_boxes[0])
    team_b = _parse_team_members(p1_boxes[1])

    for player in team_a['players']:
        player['is_self'] = player['name'] == self_name
    for player in team_b['players']:
        player['is_self'] = player['name'] == self_name

    # --- Panel 3: Scores ---
    panel3 = soup.find('div', id='panel3')
    p3_boxes = panel3.find_all('div', class_='box', recursive=False)

    _merge_scores(team_a, _parse_score_box(p3_boxes[0]))
    _merge_scores(team_b, _parse_score_box(p3_boxes[1]))

    # --- Result assignment ---
    team_a['result'] = result_self
    team_b['result'] = 'win' if result_self == 'lose' else 'lose'

    # --- Timeline (raw data only) ---
    script_tag = soup.select_one('#panel2 script')
    script_content = script_tag.get_text() if script_tag else ''

    if script_content.strip():
        groups, events, game_end_cs = parse_timeline_script(script_content)
        timeline_raw = build_timeline_raw(groups, events, game_end_cs)
    else:
        timeline_raw = None

    return {'team_a': team_a, 'team_b': team_b, 'timeline_raw': timeline_raw}

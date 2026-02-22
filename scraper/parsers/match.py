from bs4 import BeautifulSoup

from .timeline import parse_timeline_script, compute_timeline_stats


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
    """Return {team_name, players: [{name, icon_url, is_self}]}."""
    team_name_el = box.select_one('h3 p.tag-name')
    team_name = team_name_el.get_text(strip=True) if team_name_el else ''

    players = []
    for li in box.select('li.item'):
        name_el = li.select_one('span.name')
        icon_el = li.select_one('img.item-icon-img[data-original]')
        name = name_el.get_text(strip=True) if name_el else ''
        icon_url = _strip_query(icon_el['data-original']) if icon_el else ''
        players.append({'name': name, 'icon_url': icon_url})

    return {'team_name': team_name, 'players': players}


def _parse_score_box(box):
    """Return list of {icon_url, score, kills, deaths, damage_dealt, damage_received, exburst_damage}."""
    player_scores = []
    for li in box.select('li.item'):
        icon_el = li.select_one('img.item-icon-img[data-original]')
        icon_url = _strip_query(icon_el['data-original']) if icon_el else ''

        scores = {}
        for dl in li.find_all('dl'):
            dt = dl.find('dt')
            dd = dl.find('dd')
            if not (dt and dd):
                continue
            key = _DT_KEY_MAP.get(dt.get_text(strip=True))
            if key:
                # Get only direct text nodes (excludes <span>pt</span>)
                raw = ''.join(t.strip() for t in dd.find_all(string=True, recursive=False)).strip()
                try:
                    scores[key] = int(raw)
                except ValueError:
                    scores[key] = raw

        player_scores.append({'icon_url': icon_url, **scores})
    return player_scores


def _merge_scores(team, score_list):
    """Merge score data into team players matched by icon_url."""
    for player in team['players']:
        for entry in score_list:
            if entry['icon_url'] == player['icon_url']:
                player.update({k: v for k, v in entry.items() if k != 'icon_url'})
                break


def _team_timeline_stats(player_stats, team_prefix, team_result, opponent_prefix):
    """Compute team-level timeline stats."""
    own = {k: v for k, v in player_stats.items() if k.startswith(team_prefix + '-')}
    opp = {k: v for k, v in player_stats.items() if k.startswith(opponent_prefix + '-')}

    team_won = team_result == 'win'
    won_without_enemy_ol = team_won and all(
        not s['ol_available_occurred'] for s in opp.values()
    )
    lost_without_own_ol = (not team_won) and all(
        not s['ol_available_occurred'] for s in own.values()
    )
    first_player = f'{team_prefix}-1'
    xb_activations = player_stats.get(first_player, {}).get('xb_activations', 0)

    return {
        'won_without_enemy_ol': won_without_enemy_ol,
        'lost_without_own_ol': lost_without_own_ol,
        'xb_activations': xb_activations,
    }


def parse_match(html, result_self, self_name):
    """
    Parse a match_detail page.

    Args:
        result_self: 'win' or 'lose' (from daily_detail anchor class)
        self_name:   the logged-in player's name

    Returns:
        {
            team_a: {team_name, result, players: [...], timeline_stats},
            team_b: {team_name, result, players: [...], timeline_stats},
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
    result_b = 'win' if result_self == 'lose' else 'lose'
    team_a['result'] = result_self
    team_b['result'] = result_b

    # --- Timeline ---
    script_tag = soup.select_one('#panel2 script')
    script_content = script_tag.get_text() if script_tag else ''

    if script_content.strip():
        groups, events, game_end_cs = parse_timeline_script(script_content)
        player_stats = compute_timeline_stats(groups, events, game_end_cs)

        # Finalize burst_held_on_loss per player using team result
        for gid, pst in player_stats.items():
            if gid.startswith('team1-'):
                team_result = result_self
            else:
                team_result = result_b
            pst['burst_held_on_loss'] = pst.pop('burst_at_game_end') and (team_result == 'lose')

        # Assign per-player stats (team1-x → team_a[x-1], team2-x → team_b[x-1])
        for gid, pst in player_stats.items():
            parts = gid.rsplit('-', 1)
            idx = int(parts[1]) - 1
            if gid.startswith('team1-') and idx < len(team_a['players']):
                team_a['players'][idx]['timeline_stats'] = pst
            elif gid.startswith('team2-') and idx < len(team_b['players']):
                team_b['players'][idx]['timeline_stats'] = pst

        # Assign team-level stats
        team_a['timeline_stats'] = _team_timeline_stats(player_stats, 'team1', result_self, 'team2')
        team_b['timeline_stats'] = _team_timeline_stats(player_stats, 'team2', result_b, 'team1')

    return {'team_a': team_a, 'team_b': team_b}

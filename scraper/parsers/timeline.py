import re


def _date_to_cs(a, b, c):
    """Convert new Date(0, 0, 0, A, B, C) components to centiseconds."""
    return a * 6000 + b * 100 + c


def parse_timeline_script(script):
    """
    Parse the vis.js timeline script block.

    Returns:
        groups: dict {group_id: icon_url}  (query string stripped)
        events: list of dicts with keys:
            group, start_cs, end_cs, class_name, is_point
        game_end_cs: int (centiseconds from game start)
    """
    # --- Groups ---
    groups = {}
    for m in re.finditer(
        r"id:'(team\d+-\d+)',content:'<img src=\"([^\"]+)\"",
        script,
    ):
        group_id = m.group(1)
        icon_url = m.group(2).split('?')[0]
        groups[group_id] = icon_url

    # --- Events (line-by-line state machine) ---
    events = []
    current_start_cs = None
    current_end_cs = None

    _start_re = re.compile(
        r'var start_time\s*=\s*new Date\(0,\s*0,\s*0,\s*(\d+),\s*(\d+),\s*(\d+)\)'
    )
    _end_re = re.compile(
        r'var end_time\s*=\s*new Date\(0,\s*0,\s*0,\s*(\d+),\s*(\d+),\s*(\d+)\)'
    )
    _group_re = re.compile(r'group:\s*"(team\d+-\d+)"')
    _class_re = re.compile(r"className:\s*'([^']+)'")

    for line in script.splitlines():
        line = line.strip()

        m = _start_re.search(line)
        if m:
            current_start_cs = _date_to_cs(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            current_end_cs = None
            continue

        m = _end_re.search(line)
        if m:
            current_end_cs = _date_to_cs(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            continue

        if 'dataset.push(' in line:
            gm = _group_re.search(line)
            if not gm:
                continue
            cm = _class_re.search(line)
            is_point = "type:'point'" in line or "type: 'point'" in line
            events.append({
                'group': gm.group(1),
                'start_cs': current_start_cs,
                'end_cs': current_end_cs,
                'class_name': cm.group(1) if cm else None,
                'is_point': is_point,
            })

    # --- game_end_cs ---
    game_end_cs = None
    m = re.search(
        r"timeline\.addCustomTime\(new Date\(0,\s*0,\s*0,\s*(\d+),\s*(\d+),\s*(\d+)\),\s*'game-over'\)",
        script,
    )
    if m:
        game_end_cs = _date_to_cs(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return groups, events, game_end_cs


def compute_timeline_stats(groups, events, game_end_cs):
    """
    Compute per-player timeline stats.

    Returns dict keyed by group_id (e.g. 'team1-1') with keys:
        burst_type, burst_activations, burst_deaths,
        burst_at_game_end (bool; combine with result in match.py for burst_held_on_loss),
        ol_available_occurred, ol_activated,
        death_count, sortie_survival_times, xb_activations
    """
    # Bucket events by group
    player_events = {gid: [] for gid in groups}
    for ev in events:
        gid = ev['group']
        if gid in player_events:
            player_events[gid].append(ev)

    # First pass: raw xb counts per group (for team-level xb_activations)
    xb_raw = {
        gid: sum(1 for ev in evs if ev.get('class_name') == 'xb')
        for gid, evs in player_events.items()
    }

    stats = {}
    for gid in groups:
        evs = player_events[gid]

        # burst_type: first exbst-f/s/e event
        burst_type = None
        burst_map = {'exbst-f': 'fighting', 'exbst-s': 'shooting', 'exbst-e': 'extend'}
        for ev in evs:
            cn = ev.get('class_name', '')
            if cn in burst_map:
                burst_type = burst_map[cn]
                break

        burst_activations = sum(
            1 for ev in evs if ev.get('class_name') in burst_map
        )

        deaths = [ev for ev in evs if ev['is_point'] and ev['start_cs'] is not None]
        death_count = len(deaths)

        burst_intervals = [
            (ev['start_cs'], ev['end_cs'])
            for ev in evs
            if (ev.get('class_name') or '').startswith('exbst-')
            and ev['start_cs'] is not None
            and ev['end_cs'] is not None
        ]

        burst_deaths = 0
        for d in deaths:
            dt = d['start_cs']
            for start, end in burst_intervals:
                if start <= dt <= end:
                    burst_deaths += 1
                    break

        ex_intervals = [
            (ev['start_cs'], ev['end_cs'])
            for ev in evs
            if ev.get('class_name') == 'ex'
            and ev['start_cs'] is not None
            and ev['end_cs'] is not None
        ]

        # burst_at_game_end: game_over falls within ex (available) range
        burst_at_game_end = False
        if game_end_cs is not None:
            for start, end in ex_intervals:
                if start <= game_end_cs <= end:
                    burst_at_game_end = True
                    break

        ol_available_occurred = any(ev.get('class_name') == 'ov' for ev in evs)
        ol_activated = any(ev.get('class_name') == 'exbst-ov' for ev in evs)

        # sortie_survival_times: time from spawn to each death (last sortie excluded)
        death_times = sorted(d['start_cs'] for d in deaths)
        sortie_survival_times = []
        prev = 0
        for dt in death_times:
            sortie_survival_times.append(dt - prev)
            prev = dt

        # xb_activations: team-level value from team?-1
        team_base = '-'.join(gid.split('-')[:-1])  # e.g. 'team1'
        first_player = f'{team_base}-1'
        xb_activations = xb_raw.get(first_player, 0)

        stats[gid] = {
            'burst_type': burst_type,
            'burst_activations': burst_activations,
            'burst_deaths': burst_deaths,
            'burst_at_game_end': burst_at_game_end,
            'ol_available_occurred': ol_available_occurred,
            'ol_activated': ol_activated,
            'death_count': death_count,
            'sortie_survival_times': sortie_survival_times,
            'xb_activations': xb_activations,
        }

    return stats

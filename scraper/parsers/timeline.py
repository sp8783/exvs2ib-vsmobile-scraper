import re


def _date_to_cs(a, b, c):
    """Convert new Date(0, 0, 0, A, B, C) components to centiseconds."""
    return a * 6000 + b * 100 + c


def _cs_to_str(cs):
    """Convert centiseconds back to 'M:SS.CC' string matching the original JS Date args."""
    if cs is None:
        return None
    a = cs // 6000
    remainder = cs % 6000
    b = remainder // 100
    c = remainder % 100
    return f'{a}:{b:02d}.{c:02d}'


def parse_timeline_script(script):
    """
    Parse the vis.js timeline script block.

    Returns:
        groups: dict {group_id: icon_url}  (query string stripped)
        events: list of dicts with keys:
            group, start_cs, start_str, end_cs, end_str, class_name, is_point
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
                'start_str': _cs_to_str(current_start_cs),
                'end_cs': current_end_cs,
                'end_str': _cs_to_str(current_end_cs),
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


def build_timeline_raw(groups, events, game_end_cs):
    """
    Build the raw timeline data dict for JSON output.
    Suitable for reconstructing the vis.js visualization on a web app.
    """
    return {
        'groups': groups,
        'events': events,
        'game_end_cs': game_end_cs,
        'game_end_str': _cs_to_str(game_end_cs),
    }

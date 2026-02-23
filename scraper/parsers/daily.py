from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup


def parse_daily_page(html):
    """
    Parse a daily_detail page.

    Returns:
        {
            game_date: str,
            shop_name: str,
            max_page: int,
            matches: [{url, time, result_self, match_ts}],
            self_name: str,
        }
    """
    soup = BeautifulSoup(html, 'html.parser')

    date_el = soup.select_one('div.box h3 div.ta-l span.datetime')
    game_date = date_el.get_text(strip=True) if date_el else ''

    shop_el = soup.select_one('div.box h3 div.ta-r span.col-stand')
    shop_name = shop_el.get_text(strip=True) if shop_el else ''

    # Determine max page from pagination links (find highest page= value in non-disabled links)
    max_page = 1
    page_send = soup.find('div', class_='page-send')
    if page_send:
        for a in page_send.find_all('a', href=True):
            if 'disabled' in a.get('class', []):
                continue
            href = a['href']
            if 'page=' in href:
                qs = parse_qs(urlparse(href).query)
                try:
                    page = int(qs['page'][0])
                    max_page = max(max_page, page)
                except (KeyError, ValueError):
                    pass

    # Collect match entries
    matches = []
    for a in soup.select('li.item > a.vs-detail'):
        href = a['href']
        classes = a.get('class', [])
        result_self = 'win' if 'win' in classes else 'lose'

        time_el = a.select_one('p.datetime.fz-ss')
        match_time = time_el.get_text(strip=True) if time_el else ''

        qs = parse_qs(urlparse(href).query)
        try:
            match_ts = int(qs['ts'][0])
        except (KeyError, ValueError):
            match_ts = 0

        matches.append({
            'url': href,
            'time': match_time,
            'result_self': result_self,
            'match_ts': match_ts,
        })

    # Self player name: first bold player name in the match list
    p = soup.select_one('p.fz-xs.fw-b')
    self_name = p.get_text(strip=True) if p else ''

    return {
        'game_date': game_date,
        'shop_name': shop_name,
        'max_page': max_page,
        'matches': matches,
        'self_name': self_name,
    }

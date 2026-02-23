from bs4 import BeautifulSoup


def parse_top(html):
    """Return the daily_detail URL from the top (results/shop) page."""
    soup = BeautifulSoup(html, 'html.parser')
    for p in soup.select('p.col-stand.fw-b'):
        if '対戦履歴（過去30日）' in p.get_text():
            box = p.find_parent('div', class_='box')
            if box:
                a = box.find('a', href=lambda h: h and 'daily_detail' in h)
                if a:
                    return a['href']
    raise ValueError('daily_detail link not found in top page')

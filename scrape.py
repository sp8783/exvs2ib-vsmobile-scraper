#!/usr/bin/env python3
"""EXVS2IB VS.Mobile scraper — fetch match history from the portal."""

import argparse
import json
import sys
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from scraper.parsers.daily import parse_daily_page
from scraper.parsers.match import parse_match
from scraper.parsers.top import parse_top
from scraper.session import check_redirect, load_session

BASE_URL = 'https://web.vsmobile.jp/exvs2ib'
SHOP_URL = f'{BASE_URL}/results/shop'
SLEEP_SEC = 1.5


def _add_page_param(url, page):
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs['page'] = [str(page)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def main():
    parser = argparse.ArgumentParser(description='EXVS2IB VS.Mobile scraper')
    parser.add_argument('--cookies', default='cookies.json', help='Path to cookies JSON file')
    parser.add_argument('--output', default=None, help='Output JSON file path')
    args = parser.parse_args()

    output_path = args.output  # resolved after fetching game_date below

    session = load_session(args.cookies)

    # Step 1: Top page → daily_detail URL
    print('[1/4] Fetching top page...')
    resp = session.get(SHOP_URL)
    check_redirect(resp)
    try:
        daily_url = parse_top(resp.text)
    except ValueError as e:
        print(f'[ERROR] {e}', file=sys.stderr)
        sys.exit(1)
    print(f'  daily_detail URL: {daily_url}')

    # Step 2: First daily page → metadata + match list
    print('[2/4] Fetching daily detail pages...')
    resp = session.get(daily_url)
    check_redirect(resp)
    first_page = parse_daily_page(resp.text)

    self_name = first_page['self_name']
    all_matches = list(first_page['matches'])
    max_page = first_page['max_page']

    # "2026/02/14(土)" → "20260214"
    game_date_str = first_page['game_date'].split('(')[0].replace('/', '')
    if not output_path:
        output_path = f'output_{self_name}_{game_date_str}.json'

    print(f'  Date : {first_page["game_date"]}')
    print(f'  Shop : {first_page["shop_name"]}')
    print(f'  Self : {self_name!r}  |  pages: {max_page}')

    for page in range(2, max_page + 1):
        time.sleep(SLEEP_SEC)
        page_url = _add_page_param(daily_url, page)
        resp = session.get(page_url)
        check_redirect(resp)
        page_data = parse_daily_page(resp.text)
        all_matches.extend(page_data['matches'])
        print(f'  Page {page}/{max_page}: +{len(page_data["matches"])} matches')

    print(f'  Total matches collected: {len(all_matches)}')

    # Step 3: Fetch each match detail
    print('[3/4] Fetching match details...')
    results = []
    for i, m in enumerate(all_matches, 1):
        time.sleep(SLEEP_SEC)
        resp = session.get(m['url'])
        check_redirect(resp)
        match_data = parse_match(resp.text, m['result_self'], self_name)
        match_data['match_ts'] = m['match_ts']
        match_data['time'] = m['time']
        match_data['game_date'] = first_page['game_date']
        match_data['shop_name'] = first_page['shop_name']
        results.append(match_data)
        print(f'  [{i:3d}/{len(all_matches)}] ts={m["match_ts"]}  {m["result_self"]}')

    # Step 4: Sort by match timestamp and write output
    print('[4/4] Writing output...')
    results.sort(key=lambda r: r['match_ts'])

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f'Done. {len(results)} matches written to {output_path}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""EXVS2IB VS.Mobile scraper — fetch match history from the portal."""

import argparse
import json
import os
import sys
import time
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from scraper.parsers.daily import parse_daily_page
from scraper.parsers.match import parse_match
from scraper.parsers.top import parse_top
from scraper.session import AuthRedirectError, build_session, check_redirect, load_session

BASE_URL = 'https://web.vsmobile.jp/exvs2ib'
SHOP_URL = f'{BASE_URL}/results/shop'
SLEEP_SEC = 1.5


def _add_page_param(url, page):
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    qs['page'] = [str(page)]
    new_query = urlencode(qs, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def _run_scraping(session):
    """Run the full scraping pipeline for a session.

    Returns (results, game_date_str, self_name).
    Raises AuthRedirectError if the session is expired.
    """
    # Step 1: Top page → daily_detail URL
    print('[1/3] Fetching top page...')
    resp = session.get(SHOP_URL)
    check_redirect(resp)
    try:
        daily_url = parse_top(resp.text)
    except ValueError as e:
        print(f'[ERROR] {e}', file=sys.stderr)
        sys.exit(1)
    print(f'  daily_detail URL: {daily_url}')

    # Step 2: Daily pages → metadata + match list
    print('[2/3] Fetching daily detail pages...')
    resp = session.get(daily_url)
    check_redirect(resp)
    first_page = parse_daily_page(resp.text)

    self_name = first_page['self_name']
    all_matches = list(first_page['matches'])
    max_page = first_page['max_page']

    game_date_str = first_page['game_date'].split('(')[0].replace('/', '')

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
    print('[3/3] Fetching match details...')
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

    return results, game_date_str, self_name


def _run_single(cookies_path, output_path):
    session = load_session(cookies_path)
    try:
        results, game_date_str, self_name = _run_scraping(session)
    except AuthRedirectError as e:
        print(f'[ERROR] {e}', file=sys.stderr)
        sys.exit(1)

    results.sort(key=lambda r: r['match_ts'])
    out = output_path or f'output/{self_name}_{game_date_str}.json'
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    payload = {'matches': results, 'expired_users': []}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'Done. {len(results)} matches written to {out}')


def _run_all(cookies_all_path, output_path):
    with open(cookies_all_path, encoding='utf-8') as f:
        all_cookies = json.load(f)

    all_results = []
    seen_ts = set()
    game_date_str = None
    failed = []

    for user_name, cookies in all_cookies.items():
        print(f'\n=== User: {user_name} ===')
        session = build_session(cookies)
        try:
            results, gd, _ = _run_scraping(session)
        except AuthRedirectError as e:
            print(f'[WARN] Skipping {user_name!r}: {e}', file=sys.stderr)
            failed.append(user_name)
            continue

        if game_date_str is None:
            game_date_str = gd

        added = 0
        for r in results:
            if r['match_ts'] not in seen_ts:
                seen_ts.add(r['match_ts'])
                all_results.append(r)
                added += 1
        print(f'  {len(results)} matches, {added} new unique (total unique: {len(all_results)})')

    if not all_results:
        print('[ERROR] No results collected.', file=sys.stderr)
        sys.exit(1)

    all_results.sort(key=lambda r: r['match_ts'])
    out = output_path or f'output/all_{game_date_str}.json'
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    payload = {'matches': all_results, 'expired_users': failed}
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f'\nDone. {len(all_results)} unique matches written to {out}')

    if failed:
        print(f'[WARN] Cookie expired for: {", ".join(failed)}', file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description='EXVS2IB VS.Mobile scraper')
    parser.add_argument('--cookies', default='cookies/cookies.json', help='Path to cookies JSON file')
    parser.add_argument(
        '--cookies-all',
        nargs='?',
        const='cookies/all.json',
        metavar='PATH',
        help='Path to merged cookies JSON (default: cookies/all.json); run all users and merge output',
    )
    parser.add_argument('--output', default=None, help='Output JSON file path')
    args = parser.parse_args()

    if args.cookies_all is not None:
        _run_all(args.cookies_all, args.output)
    else:
        _run_single(args.cookies, args.output)


if __name__ == '__main__':
    main()

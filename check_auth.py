#!/usr/bin/env python3
"""Check whether cookies are valid by verifying no auth redirect occurs."""

import argparse
import json
import sys

from scraper.session import AuthRedirectError, build_session, check_redirect

BASE_URL = 'https://web.vsmobile.jp/exvs2ib'
SHOP_URL = f'{BASE_URL}/results/shop'


def _check_single(name, cookies):
    """Return True if the session is valid, False if expired."""
    session = build_session(cookies)
    resp = session.get(SHOP_URL)
    try:
        check_redirect(resp)
        return True
    except AuthRedirectError:
        return False


def _run_single(cookies_path):
    with open(cookies_path, encoding='utf-8') as f:
        cookies = json.load(f)

    print(f'[CHECK] {cookies_path} ... ', end='', flush=True)
    ok = _check_single(cookies_path, cookies)
    print('OK' if ok else f'EXPIRED')
    return ok


def _run_all(cookies_all_path):
    with open(cookies_all_path, encoding='utf-8') as f:
        all_cookies = json.load(f)

    results = {}
    for name, cookies in all_cookies.items():
        print(f'[CHECK] {name} ... ', end='', flush=True)
        ok = _check_single(name, cookies)
        results[name] = ok
        print('OK' if ok else 'EXPIRED')

    ok_count = sum(1 for v in results.values() if v)
    expired_count = len(results) - ok_count
    print(f'\nResult: {ok_count} OK / {expired_count} EXPIRED')
    return expired_count == 0


def main():
    parser = argparse.ArgumentParser(description='Check VS.Mobile cookie validity')
    parser.add_argument('--cookies', default='cookies/cookies.json', help='Path to cookies JSON file')
    parser.add_argument(
        '--all',
        nargs='?',
        const='cookies/all.json',
        metavar='PATH',
        help='Path to merged cookies JSON (default: cookies/all.json); check all users',
    )
    args = parser.parse_args()

    if args.all is not None:
        ok = _run_all(args.all)
    else:
        ok = _run_single(args.cookies)

    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()

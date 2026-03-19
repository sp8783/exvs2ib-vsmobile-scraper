#!/usr/bin/env python3
"""Merge cookies/*.json files into a single cookies/all.json for batch scraping."""

import glob
import json
import os
import sys

COOKIES_DIR = 'cookies'
OUTPUT = os.path.join(COOKIES_DIR, 'all.json')

SESSION_DOMAIN = 'web.vsmobile.jp'
SESSION_NAME = 'laravel_session'


def _extract_session_cookie(cookies):
    """Extract only the laravel_session cookie from a cookie list."""
    for c in cookies:
        if c.get('name') == SESSION_NAME and SESSION_DOMAIN in c.get('domain', ''):
            return [{'name': c['name'], 'value': c['value'], 'domain': c['domain']}]
    return []


def main():
    pattern = os.path.join(COOKIES_DIR, '*.json')
    files = sorted(f for f in glob.glob(pattern) if f != OUTPUT)
    if not files:
        print(f'[ERROR] No cookie files found in {COOKIES_DIR}/', file=sys.stderr)
        sys.exit(1)

    all_cookies = {}
    for path in files:
        name = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding='utf-8') as f:
            cookies = json.load(f)
        session_cookie = _extract_session_cookie(cookies)
        if not session_cookie:
            print(f'  [WARN] {path!r}: laravel_session not found, skipping', file=sys.stderr)
            continue
        all_cookies[name] = session_cookie
        print(f'  Loaded: {path!r} → user={name!r}')

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(all_cookies, f, ensure_ascii=False, indent=2)

    print(f'Done. {len(all_cookies)} users written to {OUTPUT}')


if __name__ == '__main__':
    main()

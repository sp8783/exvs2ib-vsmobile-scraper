#!/usr/bin/env python3
"""Merge cookies_*.json files into a single cookies_all.json for batch scraping."""

import glob
import json
import sys

PATTERN = 'cookies_*.json'
OUTPUT = 'cookies_all.json'
EXCLUDE = {OUTPUT}


def main():
    files = sorted(f for f in glob.glob(PATTERN) if f not in EXCLUDE)
    if not files:
        print(f'[ERROR] No cookie files found matching {PATTERN!r}', file=sys.stderr)
        sys.exit(1)

    all_cookies = {}
    for path in files:
        name = path[len('cookies_'):-len('.json')]
        with open(path, encoding='utf-8') as f:
            cookies = json.load(f)
        all_cookies[name] = cookies
        print(f'  Loaded: {path!r}  ({len(cookies)} cookies) → user={name!r}')

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(all_cookies, f, ensure_ascii=False, indent=2)

    print(f'Done. {len(all_cookies)} users written to {OUTPUT}')


if __name__ == '__main__':
    main()

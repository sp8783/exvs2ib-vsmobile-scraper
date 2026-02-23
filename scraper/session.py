import json
import sys

import requests


def load_session(path):
    session = requests.Session()
    session.headers.update({
        'User-Agent': (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) '
            'Version/17.0 Mobile/15E148 Safari/604.1'
        )
    })
    with open(path, encoding='utf-8') as f:
        cookies = json.load(f)
    for cookie in cookies:
        session.cookies.set(
            cookie['name'],
            cookie['value'],
            domain=cookie.get('domain', 'web.vsmobile.jp'),
        )
    return session


def check_redirect(response):
    url = response.url
    for keyword in ('login', 'oauth', 'bandainamcoid.com'):
        if keyword in url:
            print(f'[ERROR] Cookie expired or session invalid. Redirected to: {url}', file=sys.stderr)
            sys.exit(1)

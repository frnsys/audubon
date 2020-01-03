import re

TWITTER_RE = re.compile('https?:\/\/twitter\.com')

def is_twitter_url(url):
    return TWITTER_RE.match(url) is not None


def try_load(path, type, default):
    try:
        with open(path, 'r') as f:
            val = type(f.read())
    except FileNotFoundError:
        val = default
    return val


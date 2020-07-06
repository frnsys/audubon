import re
import json

TWITTER_RE = re.compile('https?:\/\/twitter\.com')

def is_twitter_url(url):
    return TWITTER_RE.match(url) is not None

def try_load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


import requests
import lxml.html

headers = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:64.0) Gecko/20100101 Firefox/64.0',
}

def _get(d, *keys, default=None):
    for k in keys:
        v = d.get(k)
        if v is not None: return v
    else:
        return default


def get_metadata(url):
    resp = requests.head(url, headers=headers, timeout=5)
    resp.raise_for_status()

    if 'text/html' not in resp.headers.get('Content-Type'):
        return {'url': url}

    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    html = lxml.html.fromstring(resp.content.decode('utf8'))
    tags = html.cssselect('meta[property], meta[name]')

    meta = {}
    for tag in tags:
        prop = tag.attrib.get('property', tag.attrib.get('name'))
        data = tag.attrib.get('content')
        if data is not None:
            meta[prop] = data

    can = html.cssselect('link[rel="canonical"]')
    if can:
        meta['canonical'] = can[0].attrib['href']

    # Canonical data
    meta['url'] = _get(meta, 'canonical', 'og:url', default=url)
    meta['description'] = _get(meta, 'description', 'og:description', 'twitter:description')
    meta['title'] = _get(meta, 'og:title', 'twitter:title', url)

    return meta
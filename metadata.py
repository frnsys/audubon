import requests
import lxml.html


def _get(d, *keys, default=None):
    for k in keys:
        v = d.get(k)
        if v is not None: return v
    else:
        return default


def get_metadata(url):
    resp = requests.get(url)
    resp.raise_for_status()

    html = lxml.html.fromstring(resp.content)
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
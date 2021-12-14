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

# <https://github.com/html5lib/html5lib-python/issues/96#issuecomment-625190231>
# A regex matching the "invalid XML character range"
ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1F\uD800-\uDFFF\uFFFE\uFFFF]")
def remove_control_characters(html):
    # type: (t.Text) -> t.Text
    """
    Strip invalid XML characters that `lxml` cannot parse.
    """
    # See: https://github.com/html5lib/html5lib-python/issues/96
    #
    # The XML 1.0 spec defines the valid character range as:
    # Char ::= #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
    #
    # We can instead match the invalid characters by inverting that range into:
    # InvalidChar ::= #xb | #xc | #xFFFE | #xFFFF | [#x0-#x8] | [#xe-#x1F] | [#xD800-#xDFFF]
    #
    # Sources:
    # https://www.w3.org/TR/REC-xml/#charsets,
    # https://lsimons.wordpress.com/2011/03/17/stripping-illegal-characters-out-of-xml-in-python/
    def strip_illegal_xml_characters(s, default, base=10):
        # Compare the "invalid XML character range" numerically
        n = int(s, base)
        if n in (0xb, 0xc, 0xFFFE, 0xFFFF) or 0x0 <= n <= 0x8 or 0xe <= n <= 0x1F or 0xD800 <= n <= 0xDFFF:
            return ""
        return default

    # We encode all non-ascii characters to XML char-refs, so for example "💖" becomes: "&#x1F496;"
    # Otherwise we'd remove emojis by mistake on narrow-unicode builds of Python
    # html = html.encode("ascii", "xmlcharrefreplace").decode("utf-8")
    html = re.sub(r"&#(\d+);?", lambda c: strip_illegal_xml_characters(c.group(1), c.group(0)), html)
    html = re.sub(r"&#[xX]([0-9a-fA-F]+);?", lambda c: strip_illegal_xml_characters(c.group(1), c.group(0), base=16), html)
    html = ILLEGAL_XML_CHARS_RE.sub("", html)
    return html

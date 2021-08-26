#!/usr/bin/env python3

import re
import argparse
from db import Database
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer

LINK_RE = re.compile('(https:\/\/t.co\/[A-Za-z0-9]+)')

parser = argparse.ArgumentParser(description='A simple server to view saved links in-context')
parser.add_argument('-p', '--port', type=int, dest='PORT', default=8888, help='Port for server')
args = parser.parse_args()


def process_contexts(contexts):
    tweets = {}
    retweets = {}
    text_to_id = {} # For deduping tweets
    for c in contexts:
        # Group the same retweets together
        if c['text'].startswith('RT @'):
            for s in c['sub']:
                id = s['id']
                if id not in retweets:
                    retweets[id] = {
                        'id': id,
                        'user': s['user'],
                        'text': make_links(s['text']),
                        'retweeters': []
                    }
                retweets[id]['retweeters'].append(c['user'])
        else:
            text = c['text']
            if text in text_to_id:
                id = text_to_id[text]
                tweets[id]['repeats'] += 1
            else:
                id = c['id']
                text_to_id[text] = id
                tweets[id] = c
                tweets[id]['text']  = make_links(c['text'])
                tweets[id]['repeats'] = 0
    return tweets.values(), retweets.values()


def make_links(text):
    return LINK_RE.sub(r'<a href="\1">\1</a>', text)


class AudubonRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        db = Database('data/main/db')

        params = parse_qs(urlparse(self.path).query)
        query = params.get('query')
        if query is not None:
            query = query[0]
            results = db.search(query)
        else:
            cutoff = datetime.now() - timedelta(days=2)
            results = db.since(cutoff.timestamp(), min_count=2, with_context=True)

        # Reverse chron
        results.reverse()

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        html = ['''
            <html>
                <head>
                    <meta charset="utf8">
                    <meta name="viewport" content="width=device-width,initial-scale=1">
                    <title>audubon</title>
                    <style>
                        html {
                            overflow-x: hidden;
                        }
                        article {
                            margin: 4em auto;
                            max-width: 720px;
                            line-height: 1.4;
                            padding-bottom: 4em;
                            border-bottom: 2px solid black;
                            font-family: sans-serif;
                        }
                        h4 {
                            position: sticky;
                            top: 0;
                            background: #fff;
                        }
                        .user {
                            color: #fff;
                            background: #333;
                            display: inline-block;
                            padding: 0 0.2em;
                            border-radius: 0.2em;
                        }
                        .context {
                            padding: 0.5em;
                            margin-bottom: 1em;
                            background: #d0e5f2;
                            border-radius: 0.2em;
                        }
                        .meta {
                            display: flex;
                            justify-content: space-between;
                            font-size: 0.8em;
                            margin: 1em 0 0;
                        }
                        .repeats {
                            font-style: italic;
                            color: #888;
                        }
                        a {
                            color: #1e5ae8;
                        }
                        ul, li {
                            list-style-type: none;
                        }
                        form {
                            width: 100%;
                            max-width: 720px;
                            margin: 1em auto;
                            display: flex;
                        }
                        form input[type="text"] {
                            flex: 1;
                            margin-right: 0.5em;
                        }
                    </style>
                </head>
                <body>
                    <form method="get" action="/">
                        <input type="text" placeholder="Search for url" name="query" />
                        <input type="submit" value="Search">
                    </form>
                ''']


        for item in results:
            html.append('''
                <article>
                    <h4><a href="{href}">{href}</a></h4>'''.format(href=item['url']))
            tweets, retweets = process_contexts(item['contexts'])
            for t in tweets:
                html.append('''
                    <div class="context">
                        <div class="user">{user}</div>
                        {text}
                        <ul class="subs">{subs}</ul>
                        <div class="meta">
                            <div class="repeats">{repeats}</div>
                            <a href="https://twitter.com/i/web/status/{id}">Permalink</a>
                        </div>
                    </div>
                '''.format(
                    id=t['id'],
                    user=t['user'],
                    text=t['text'],
                    repeats='Repeats {} times'.format(t['repeats']) if t['repeats'] > 0 else '',
                    subs='\n'.join('<li><em class="user">{user}</em>: {text}</li>'.format(
                        user=s['user'],
                        text=LINK_RE.sub(r'<a href="\1">\1</a>', s['text'])) for s in t['sub'])))
            for t in retweets:
                html.append('''
                    <div class="context">
                        <div class="user">{user}</div>
                        {text}
                        <div class="meta">
                            <div class="retweeters">Retweeted by: {retweeters}</div>
                            <a href="https://twitter.com/i/web/status/{id}">Permalink</a>
                        </div>
                    </div>
                '''.format(
                    id=t['id'],
                    user=t['user'],
                    text=t['text'],
                    retweeters=' '.join('<span class="user">{}</span>'.format(u) for u in set(t['retweeters']))))
            html.append('</article>')

        html.append('</body></html>')

        # Response
        html = '\n'.join(html).encode('utf8')
        self.wfile.write(html)


if __name__ == '__main__':
    print('Running on port', args.PORT)
    server = HTTPServer(('localhost', args.PORT), AudubonRequestHandler)
    server.serve_forever()
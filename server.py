#!/usr/bin/env python3

import re
import argparse
from db import Database
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

LINK_RE = re.compile('(https:\/\/t.co\/[A-Za-z0-9]+)')

parser = argparse.ArgumentParser(description='A simple server to view saved links in-context')
parser.add_argument('-p', '--port', type=int, dest='PORT', default=8888, help='Port for server')
args = parser.parse_args()

class AudubonRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        db = Database('data/main/db')
        cutoff = datetime.now() - timedelta(days=30)
        recent = db.since(cutoff.timestamp(), min_count=2, with_context=True)

        # Reverse chron
        recent.reverse()

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        html = ['''
            <html>
                <head>
                    <meta charset="utf8">
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
                            color: #888;
                        }
                        .context {
                            padding: 0.5em;
                            background: #f0f0f0;
                            margin-bottom: 1em;
                        }
                        a {
                            color: blue;
                        }
                        ul, li {
                            list-style-type: none;
                        }
                    </style>
                </head>
                <body>''']


        for item in recent:
            html.append('''
                <article>
                    <h4><a href="{href}">{href}</a></h4>'''.format(href=item['url']))
            for c in item['contexts']:
                html.append('''
                    <div class="context">
                        <div class="user">{user}</div>
                        {text}
                        <ul class="subs">{subs}</ul>
                    </div>
                '''.format(
                    user=c['user'],
                    text=LINK_RE.sub(r'<a href="\1">\1</a>', c['text']),
                    subs='\n'.join('<li><em class="user">{user}</em>: {text}</li>'.format(
                        user=s['user'],
                        text=LINK_RE.sub(r'<a href="\1">\1</a>', s['text'])) for s in c['sub'])
                ))
            html.append('</article>')

        html.append('</body></html>')

        # Response
        html = '\n'.join(html).encode('utf8')
        self.wfile.write(html)


if __name__ == '__main__':
    print('Running on port', args.PORT)
    server = HTTPServer(('localhost', args.PORT), AudubonRequestHandler)
    server.serve_forever()
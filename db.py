import json
import sqlite3
from hashlib import md5
from datetime import datetime
from collections import defaultdict

class Database:
    def __init__(self, path):
        self.con = sqlite3.connect(path)
        self.cur = self.con.cursor()
        self.cur.execute('CREATE TABLE IF NOT EXISTS urls \
                         (url text primary key,\
                         users text not null default "",\
                         count integer not null default 0,\
                         last_seen integer)')
        self.cur.execute('CREATE TABLE IF NOT EXISTS context \
                         (key text primary key,\
                         id text not null,\
                         url text not null,\
                         user text not null,\
                         text text not null,\
                         sub text not null default "")')

    def inc(self, url, user):
        ts = datetime.now().timestamp()
        self.cur.execute('INSERT OR IGNORE INTO urls(url) VALUES (?)', (url,))

        users = self.users(url)
        if user not in users:
            users.append(user)
        count = len(users)

        self.cur.execute('UPDATE urls SET count = ?, last_seen = ?, users = ? WHERE url = ?',
                         (count, ts, ','.join(users), url))
        self.con.commit()

    def add_context(self, id, url, user, text, sub):
        key = '{}-{}'.format(id, md5(url.encode('utf8')).hexdigest())
        sub = json.dumps(sub)
        self.cur.execute('INSERT OR IGNORE INTO context VALUES (?, ?, ?, ?, ?, ?)', (key, id, url, user, text, sub))

    def since(self, timestamp, min_count=1, with_context=False):
        if with_context:
            s = 'SELECT urls.*, context.id, context.user, context.text, context.sub FROM urls INNER JOIN context \
                ON urls.url=context.url WHERE urls.last_seen >= ? AND urls.count >= ?'
            results = self.cur.execute(s, (timestamp, min_count)).fetchall()
            grouped = {}
            for url, users, count, last_seen, id, user, text, sub in results:
                if url not in grouped:
                    grouped[url] = {
                        'url': url,
                        'users': users,
                        'count': count,
                        'last_seen': last_seen,
                        'contexts': []
                    }
                grouped[url]['contexts'].append({
                    'id': id,
                    'user': user,
                    'text': text,
                    'sub': json.loads(sub)
                })
            return sorted(grouped.values(), key=lambda r: r['last_seen'])
        else:
            s = 'SELECT * FROM urls WHERE last_seen >= ? AND count >= ?'
            results = self.cur.execute(s, (timestamp, min_count)).fetchall()
            return [{
                'url': url,
                'users': users,
                'count': count,
                'last_seen': last_seen
            } for url, users, count, last_seen in results]

    def users(self, url):
        users, = self.cur.execute('SELECT users FROM urls WHERE url == ?', (url,)).fetchone()
        return users.split(',') if users else []

    def search(self, query):
        results = []
        query = '%{}%'.format(query)
        s = 'SELECT urls.*, context.id, context.user, context.text, context.sub FROM urls INNER JOIN context \
            ON urls.url=context.url WHERE urls.url LIKE ?'
        results = self.cur.execute(s, (query,)).fetchall()
        grouped = {}
        for url, users, count, last_seen, id, user, text, sub in results:
            if url not in grouped:
                grouped[url] = {
                    'url': url,
                    'users': users,
                    'count': count,
                    'last_seen': last_seen,
                    'contexts': []
                }
            grouped[url]['contexts'].append({
                'id': id,
                'user': user,
                'text': text,
                'sub': json.loads(sub)
            })
        return sorted(grouped.values(), key=lambda r: r['last_seen'])
        return results


if __name__ == '__main__':
    db = Database('data/db')
    for r in db.since(0):
        print(r)
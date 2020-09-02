import json
import sqlite3
from hashlib import md5
from datetime import datetime

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
        self.cur.execute('INSERT INTO context VALUES (?, ?, ?, ?, ?, ?)', (key, id, url, user, text, sub))

    def since(self, timestamp, min_count=1):
        return self.cur.execute('SELECT * FROM urls WHERE last_seen >= ? AND count >= ?',
                                (timestamp, min_count)).fetchall()

    def users(self, url):
        users, = self.cur.execute('SELECT users FROM urls WHERE url == ?', (url,)).fetchone()
        return users.split(',') if users else []

    def search(self, query):
        results = []
        query = '%{}%'.format(query)
        matches = self.cur.execute('SELECT users, url, last_seen FROM urls WHERE url LIKE ?', (query,)).fetchall()
        for users, url, timestamp in matches:
            context = self.cur.execute('SELECT id, user, text, sub FROM context WHERE url == ?', (url,)).fetchall()

            tweets = []
            for id, user, text, sub in context:
                subs = json.loads(sub)
                tweets.append({
                    'id': id,
                    'user': user,
                    'text': text,
                    'sub': subs
                })

            results.append({
                'url': url,
                'users': users.split(','),
                'datetime': datetime.fromtimestamp(timestamp),
                'timestamp': timestamp,
                'tweets': tweets
            })
        return results


if __name__ == '__main__':
    db = Database('data/db')
    for r in db.since(0):
        print(r)
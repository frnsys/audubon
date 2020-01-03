import sqlite3
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

    def since(self, timestamp, min_count=1):
        return self.cur.execute('SELECT * FROM urls WHERE last_seen >= ? AND count >= ?',
                                (timestamp, min_count)).fetchall()

    def users(self, url):
        users, = self.cur.execute('SELECT users FROM urls WHERE url == ?', (url,)).fetchone()
        return users.split(',') if users else []
import sys
from db import Database
from datetime import datetime

if __name__ == '__main__':
    query = sys.argv[1]
    db = Database('data/db')
    for users, url, timestamp in db.search(query):
        print(url)
        print(' ', users)
        print(' ', datetime.fromtimestamp(timestamp).isoformat())
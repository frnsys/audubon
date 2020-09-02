import sys
from db import Database
from datetime import datetime

if __name__ == '__main__':
    query = sys.argv[1]
    db = Database('data/db')
    for result in db.search(query):
        print(result['url'])
        print('users: ', ', '.join(result['users']))
        print('datetime: ', result['datetime'].isoformat())
        for t in result['tweets']:
            print('   ', t['user'])
            print('   ', t['text'])
            for sub in t['sub']:
                print('    >', sub['user'])
                print('    >', sub['text'])
        print('=='*20)
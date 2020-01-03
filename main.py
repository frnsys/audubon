import json
import util
import config
import tweepy
from db import Database
from datetime import datetime
from metadata import get_metadata
from PyRSS2Gen import RSS2, RSSItem
from apscheduler.schedulers.blocking import BlockingScheduler

auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

def main():
    db = Database('data/db')

    last_seen = util.try_load('data/last_seen', int, None)
    last_updated = util.try_load('data/last_updated', float, 0)

    tweets = api.home_timeline(count=200, since_id=last_seen)
    for list in config.LISTS:
        user, slug = list.split('/')
        tweets += api.list_timeline(slug=slug, owner_screen_name=user, since_id=last_seen)

    for t in tweets:
        user = t.user.screen_name

        urls = t.entities['urls']
        if hasattr(t, 'retweeted_status'):
            urls += t.retweeted_status.entities['urls']
        if hasattr(t, 'quoted_status'):
            urls += t.quoted_status.entities['urls']

        for url in urls:
            url = url['expanded_url']
            if util.is_twitter_url(url): continue

            meta = get_metadata(url)
            url = meta['url']
            if util.is_twitter_url(url): continue

            db.inc(url, user)

        if last_seen is None or t.id > last_seen: last_seen = t.id

    with open('data/last_seen', 'w') as f:
        f.write(str(last_seen))

    # Compile RSS
    urls = db.since(last_updated, min_count=config.MIN_COUNT)
    if urls:
        try:
            feed = json.load(open('data/feed'))
        except FileNotFoundError:
            feed = []

        for url, users, _, _ in urls:
            meta = get_metadata(url)
            feed.append({
                'title': meta['title'],
                'link': url,
                'description': '[Saved by {}]\t{}'.format(users, meta['description']),
                'pubDate': datetime.now().isoformat()
            })

        items=[RSSItem(
            title=item['title'],
            link=item['link'],
            description=item['description'],
            pubDate=item['pubDate']
        ) for item in feed[::-1]]

        rss = RSS2(
            title='twitter chitter',
            description='twitter chitter',
            link=config.URL,
            lastBuildDate=datetime.now(),
            items=items)

        rss.write_xml(open(config.RSS_PATH, 'w'))

        with open('data/last_updated', 'w') as f:
            f.write(str(datetime.now().timestamp()))
        with open('data/feed', 'w') as f:
            json.dump(feed, f)


if __name__ == '__main__':
    scheduler = BlockingScheduler()
    scheduler.add_job(main, trigger='interval', minutes=config.UPDATE_INTERVAL)
    scheduler.start()
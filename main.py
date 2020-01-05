import json
import util
import config
import tweepy
import logging
from db import Database
from datetime import datetime
from metadata import get_metadata
from PyRSS2Gen import RSS2, RSSItem
from apscheduler.schedulers.blocking import BlockingScheduler

auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S %Z')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def main():
    logger.info('Running...')
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

            try:
                meta = get_metadata(url)
            except Exception as e:
                logger.info('Error getting metadata for {}: {}'.format(url, e))
                continue

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

        seen = [i['link'] for i in feed]

        for url, users, _, _ in urls:
            if url in seen: continue
            try:
                meta = get_metadata(url)
            except Exception as e:
                logger.info('Error getting metadata for {}: {}'.format(url, e))
                continue

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
    logger.info('Done')


if __name__ == '__main__':
    main()

    scheduler = BlockingScheduler()
    scheduler.add_job(main, trigger='interval', minutes=config.UPDATE_INTERVAL)
    scheduler.start()
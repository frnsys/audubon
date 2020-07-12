import json
import util
import config
import tweepy
import logging
from dateutil import tz
from db import Database
from datetime import datetime
from metadata import get_metadata
from feedgen.feed import FeedGenerator
from apscheduler.schedulers.blocking import BlockingScheduler

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S %Z')
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def main():
    logger.info('Running...')

    auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
    auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)
    db = Database('data/db')

    now = datetime.now().timestamp()
    last_seen = util.try_load_json('data/last_seen')
    last_updated = util.try_load_json('data/last_updated')
    last_update = max(last_updated.values()) if last_updated else 0

    users = list(tweepy.Cursor(api.friends_ids).items())
    for l in config.LISTS:
        user, slug = l.split('/')
        users += [u.id for u in tweepy.Cursor(api.list_members, slug=slug, owner_screen_name=user).items()]
    users = set(users)
    users = {u: last_updated.get(u) for u in users}
    users = sorted(list(users), key=lambda u: last_seen.get(u, -1))
    logger.info('{} users'.format(len(users)))

    metadata = {}
    try:
        for user in users:
            last = last_seen.get(user, None)
            tweets = api.user_timeline(user_id=user, count=200, since_id=last)
            for t in tweets:
                user = t.user.screen_name
                user_id = t.user.id

                urls = t.entities['urls']
                if hasattr(t, 'retweeted_status'):
                    urls += t.retweeted_status.entities['urls']
                if hasattr(t, 'quoted_status'):
                    urls += t.quoted_status.entities['urls']

                urls = [url['expanded_url'] for url in urls]
                for url in set(urls):
                    if util.is_twitter_url(url): continue

                    try:
                        if url not in metadata:
                            metadata[url] = get_metadata(url)
                        meta = metadata[url]
                    except Exception as e:
                        logger.info('Error getting metadata for {}: {}'.format(url, e))
                        meta = {'url': url}

                    url = meta['url']
                    if util.is_twitter_url(url): continue

                    logger.info('@{}: {}'.format(user, url))
                    db.inc(url, user)

                last = last_seen.get(user_id, None)
                last_updated[user_id] = now
                if last is None or t.id > last: last_seen[user_id] = t.id

            with open('data/last_seen', 'w') as f:
                json.dump(last_seen, f)
            with open('data/last_updated', 'w') as f:
                json.dump(last_updated, f)

    except tweepy.error.RateLimitError:
        logger.info('Rate limited')

    # Compile RSS
    fg = FeedGenerator()
    fg.link(href=config.URL)
    fg.description('twitter chitter')
    fg.title('twitter chitter')
    urls = db.since(last_update, min_count=config.MIN_COUNT)
    if urls:
        try:
            feed = json.load(open('data/feed'))
        except FileNotFoundError:
            feed = []

        seen = [i['link'] for i in feed]

        for url, users, _, _ in urls:
            if url in seen: continue

            logger.info('Adding: {}'.format(url))
            try:
                meta = get_metadata(url)
            except Exception as e:
                logger.info('Error getting metadata for {}: {}'.format(url, e))
                continue

            feed.append({
                'title': meta['title'],
                'link': url,
                'description': '[Saved by {}]\t{}'.format(users, meta['description']),
                'pubDate': datetime.now(tz.tzlocal()).isoformat()
            })

        for item in feed[::-1]:
            fe = fg.add_entry()
            fe.title(item['title'])
            fe.link(href=item['link'])
            fe.description(item['description'])
            fe.pubDate(item['pubDate'])

        fg.rss_file(config.RSS_PATH)

        with open('data/feed', 'w') as f:
            json.dump(feed, f)
    logger.info('Done')


if __name__ == '__main__':
    main()

    scheduler = BlockingScheduler()
    scheduler.add_job(main, trigger='interval', minutes=config.UPDATE_INTERVAL)
    scheduler.start()
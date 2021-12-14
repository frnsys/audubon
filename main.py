import os
import json
import util
import config
import tweepy
import logging
from time import sleep
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


def process_feed(api, feed_conf, friends_cache, users_cache, urls_cache):
    data_dir = 'data/{}'.format(feed_conf['id'])
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    db = Database(os.path.join(data_dir, 'db'))
    now = datetime.now().timestamp()
    last_seen_path = os.path.join(data_dir, 'last_seen')
    last_seen = util.try_load_json(last_seen_path)
    last_updated_path = os.path.join(data_dir, 'last_updated')
    last_updated = util.try_load_json(last_updated_path)
    last_update = max(last_updated.values()) if last_updated else 0
    logger.info('Last updated: {}'.format(last_update))

    compile_rss(db, last_update, data_dir, feed_conf)

    if 'friends' not in friends_cache:
        friends_cache['friends'] = [str(u_id) for u_id in tweepy.Cursor(api.friends_ids).items()]
    users = friends_cache['friends']
    for l in feed_conf['lists']:
        if l not in friends_cache:
            user, slug = l.split('/')
            list_users = [str(u.id) for u in tweepy.Cursor(api.list_members, slug=slug, owner_screen_name=user).items()]
            friends_cache[l] = list_users
        users += friends_cache[l]
    users = set(users)
    users = {u: last_updated.get(u, -1) for u in users}
    users = sorted(list(users), key=lambda u: users[u])
    logger.info('{} users'.format(len(users)))

    try:
        keywords = feed_conf.get('keywords', [])
        for i, user_id in enumerate(users):
            last = last_seen.get(user_id, None)
            logger.info('Fetching user {}, last fetched id: {}'.format(user_id, last))
            try:
                if user_id in users_cache:
                    tweets = users_cache[user_id]
                else:
                    tweets = api.user_timeline(user_id=user_id, count=200, since_id=last, tweet_mode='extended')
                    users_cache[user_id] = tweets
            except tweepy.TweepError:
                logger.error('Failed to fetch tweets for user {}, their tweets may be protected'.format(user_id))
                continue

            for t in tweets:
                if not keywords or any(kw in t.full_text.lower() for kw in keywords):
                    user = t.user.screen_name

                    sub_statuses = []
                    urls = [url['expanded_url'] for url in t.entities['urls']]
                    for attr in ['retweeted_status', 'quoted_status']:
                        if hasattr(t, attr):
                            sub_status = getattr(t, attr)
                            urls += [url['expanded_url'] for url in sub_status.entities['urls']]
                            sub_statuses.append({
                                'id': sub_status.id_str,
                                'user': sub_status.user.screen_name,
                                'text': sub_status.full_text,
                            })

                    for url in set(urls):
                        if util.is_twitter_url(url): continue

                        try:
                            if url not in urls_cache:
                                logger.info('Fetching metadata: {}'.format(url))
                                urls_cache[url] = get_metadata(url)
                            meta = urls_cache[url]
                        except Exception as e:
                            logger.info('Error getting metadata for {}: {}'.format(url, e))
                            meta = {'url': url}

                        # Sometimes the metadata canonical url will be a relative path,
                        # if that's the case just stick with the url we have
                        if meta['url'].startswith('http'):
                            url = meta['url']
                            if util.is_twitter_url(url): continue

                        logger.info('@{}: {}'.format(user, url))
                        db.inc(url, user)
                        db.add_context(t.id_str, url, user, t.full_text, sub_statuses)

                last = last_seen.get(user_id, None)
                if last is None or t.id > last: last_seen[user_id] = t.id

            last_updated[user_id] = now
            with open(last_seen_path, 'w') as f:
                json.dump(last_seen, f)
            with open(last_updated_path, 'w') as f:
                json.dump(last_updated, f)

            if i % 100 == 0:
                compile_rss(db, last_update, data_dir, feed_conf)

    except tweepy.error.RateLimitError:
        logger.info('Rate limited')

    compile_rss(db, last_update, data_dir, feed_conf)
    logger.info('Done: {}'.format(feed_conf['id']))


def compile_rss(db, last_update, data_dir, feed_conf):
    logger.info('Saving RSS...')

    # Compile RSS
    fg = FeedGenerator()
    fg.link(href=feed_conf['url'])
    fg.description('twitter chitter')
    fg.title('twitter chitter')
    feed_path = os.path.join(data_dir, 'feed')
    results = db.since(last_update, min_count=feed_conf['min_count'])

    try:
        feed = json.load(open(feed_path))
    except FileNotFoundError:
        feed = []

    if results:
        seen = [i['link'] for i in feed]

        for res in results:
            url = res['url']
            users = res['users']
            if url in seen: continue

            logger.info('Adding: {}'.format(url))
            try:
                meta = get_metadata(url)
            except Exception as e:
                logger.info('Error getting metadata for {}: {}'.format(url, e))
                continue

            feed.append({
                'title': meta.get('title', '(No title)'),
                'link': url,
                'description': '[Saved by {}]\t{}'.format(users, meta.get('description', '(No description)')),
                'pubDate': datetime.now(tz.tzlocal()).isoformat()
            })

    for item in feed[::-1][:config.MAX_ITEMS]:
        fe = fg.add_entry()
        fe.title(item['title'])
        fe.link(href=item['link'])
        fe.description(util.remove_control_characters(item['description']))
        fe.pubDate(item['pubDate'])

    fg.rss_file(feed_conf['rss_path'])

    with open(feed_path, 'w') as f:
        json.dump(feed, f)

    logger.info('Saved RSS to: {}'.format(feed_conf['rss_path']))


def main():
    logger.info('Running...')

    auth = tweepy.OAuthHandler(config.CONSUMER_KEY, config.CONSUMER_SECRET)
    auth.set_access_token(config.ACCESS_TOKEN, config.ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

    # Use api.lists_all() to check list slugs,
    # not always what you'd expect

    users_cache = {}
    friends_cache = {}
    urls_cache = {}
    for feed_conf in config.FEEDS:
        succeeded = False
        while not succeeded:
            try:
                process_feed(api, feed_conf, friends_cache, users_cache, urls_cache)
                succeeded = True
            except tweepy.error.RateLimitError:
                logger.info('Rate limited. Sleeping...')
                sleep(60*15)


if __name__ == '__main__':
    main()

    scheduler = BlockingScheduler()
    scheduler.add_job(main, trigger='interval', minutes=config.UPDATE_INTERVAL)
    scheduler.start()
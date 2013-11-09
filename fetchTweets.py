import logging, time, json, yaml, MySQLdb, re, unicodedata
from twitter import *

logger = logging.getLogger('fetchTweets')
hdlr = logging.FileHandler('./log/fetchTweets.log')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)

logger.info('Start time')

def load_config():
    global config
    config = yaml.load(open('config.yaml'))
    logger.debug('loaded config yaml')

def connect_db():
    global db
    db = MySQLdb.connect(host = config['database']['host'], user = config['database']['user'], passwd = config['database']['passwd'], db = config['database']['db'])
    logger.debug('db connected')

def load_api():
    global regions
    regions = yaml.load(open("twitter.yaml", 'r'))['regions']
    logger.debug('loaded twitter yaml')

def connect_api():
    global api
    api = Twitter(auth=OAuth(config['twitter']['access_token'], config['twitter']['access_token_secret'], config['twitter']['consumer_key'], config['twitter']['consumer_secret']))
    logger.debug('api loaded')

def query_twitter(lat, long, range):
    geocode_string = str(lat) + ","+ str(long) + "," + str(range)
    return api.search.tweets(q='',geocode=geocode_string,count=100,result_type='recent')

def to_esc_sql(text):
    return re.escape(text.replace("\\_", "_")).encode('utf8')

def insert_tweet(tweet):
    created_at = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(tweet['created_at'],'%a %b %d %H:%M:%S +0000 %Y'))
    if tweet['coordinates'] is not None:
        lat = tweet['coordinates']['coordinates'][0]
        long = tweet['coordinates']['coordinates'][1]
    else:
        lat = 'NULL'
        long = 'NULL'
    if tweet['retweeted'] is False:
        retweeted = 0
    else:
        retweeted = 1
    organised_tweets['tweets'].append([{
        'id': tweet['id'],
        'usr_id': tweet['user']['id'],
        'text': tweet['text'].encode('ascii', 'ignore'),
        'retweeted': retweeted,
        'created_at': created_at,
        'lat': lat,
        'long': long
        }])

def insert_region(tweet, region):
    organised_tweets['regions'].append([{
        'tweet_id': tweet['id'],
        'region': region
        }])

def insert_user(user):
    created_at = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(user['created_at'],'%a %b %d %H:%M:%S +0000 %Y'))
    organised_tweets['users'].append([{
        'id': user['id'],
        'screen_name': user['screen_name'],
        'name': user['name'],
        'location': user['location'],
        'followers_count': user['followers_count'],
        'friends_count': user['friends_count'],
        'statuses_count': user['statuses_count'],
        'time_zone': user['time_zone'],
        'profile_image_url': user['profile_image_url'],
        'created_at': created_at
        }])

def insert_user_mentions(tweet_id, usr_id):
    organised_tweets['user_mentions'].append([{
        'tweet_id': tweet_id,
        'usr_id': usr_id
        }])

def insert_hashtags(tweet_id, hashtag):
    organised_tweets['hashtags'].append([{
        'tweet_id': tweet_id,
        'hashtag': hashtag
        }])

def insert_url(tweet_id, url):
    organised_tweets['urls'].append([{
        'tweet_id': tweet_id,
        'url': url
        }])

def organise_raw_tweets(raw_tweets, region):
    global organised_tweets
    organised_tweets = dict()
    organised_tweets['tweets'] = list()
    organised_tweets['regions'] = list()
    organised_tweets['users'] = list()
    organised_tweets['user_mentions'] = list()
    organised_tweets['hashtags'] = list()
    organised_tweets['urls'] = list()
    for tweet in raw_tweets['statuses']:
        insert_tweet(tweet)
        insert_region(tweet, region)
        insert_user(tweet['user'])
        print tweet
        for user in tweet['entities']['user_mentions']:
            insert_user_mentions(tweet['id'], user['id'])

        for hashtag in tweet['entities']['hashtags']:
            insert_hashtags(tweet['id'], hashtag['text'])

        for url in tweet['entities']['urls']:
            insert_url(tweet['id'], url['expanded_url'])

    return organised_tweets

def insert_data():
    for tweet in organised_tweets['tweets']:
        print tweet
        query = """
          INSERT IGNORE INTO `Tweets`
          SET
            `id` = {id},
            `usr_id` = {usr_id},
            `lat` = {lat},
            `long` = {long},
            `text` = '{text}',
            `retweeted` = {retweeted},
            `created_at` = '{created_at}';""".format(
                id=tweet[0]['id'],
                usr_id=tweet[0]['usr_id'],
                lat=tweet[0]['lat'],
                long=tweet[0]['long'],
                retweeted=tweet[0]['retweeted'],
                text=to_esc_sql(tweet[0]['text']),
                created_at=tweet[0]['created_at'])
        print query
        cur = db.cursor()
        cur.execute(query)
        db.commit()

    for region in organised_tweets['regions']:
        print region
        query = """
          INSERT IGNORE INTO `TweetRegions`
          SET
            `tweet_id` = {tweet_id},
            `region` = '{region}';""".format(
                tweet_id=region[0]['tweet_id'],
                region=region[0]['region'])
        print query
        cur = db.cursor()
        cur.execute(query)
        db.commit()

    for user in organised_tweets['users']:
        print user
        query = """
          INSERT IGNORE INTO `TwitterUsers`
          SET
            `id` = {id},
            `screen_name` = '{screen_name}',
            `name` = '{name}',
            `location` = '{location}',
            `followers_count` = {followers_count},
            `friends_count` = {friends_count},
            `statuses_count` = {statuses_count},
            `profile_image_url` = '{profile_image_url}',
            `created_at` = '{created_at}';""".format(
                id=user[0]['id'],
                screen_name=to_esc_sql(user[0]['screen_name']),
                name=to_esc_sql(user[0]['name']),
                location=to_esc_sql(user[0]['location']),
                followers_count=user[0]['followers_count'],
                friends_count=user[0]['friends_count'],
                statuses_count=user[0]['statuses_count'],
                profile_image_url=to_esc_sql(user[0]['profile_image_url']),
                created_at=tweet[0]['created_at'])
        print query
        cur = db.cursor()
        cur.execute(query)
        db.commit()

    for user_mention in organised_tweets['user_mentions']:
        print user_mention
        query = """
          INSERT IGNORE INTO `TweetUserMentions`
          SET
            `tweet_id` = {tweet_id},
            `usr_id` = {usr_id};""".format(
                tweet_id=user_mention[0]['tweet_id'],
                usr_id=user_mention[0]['usr_id'])
        print user_mention
        cur = db.cursor()
        cur.execute(query)
        db.commit()

    for hashtag in organised_tweets['hashtags']:
        print hashtag
        query = """
          INSERT IGNORE INTO `TweetHashtags`
          SET
            `tweet_id` = {tweet_id},
            `hashtag` = '{hashtag}';""".format(
                tweet_id=hashtag[0]['tweet_id'],
                hashtag=to_esc_sql(hashtag[0]['hashtag']))
        print hashtag
        cur = db.cursor()
        cur.execute(query)
        db.commit()

    for url in organised_tweets['urls']:
        print url
        query = """
          INSERT IGNORE INTO `TweetUrls`
          SET
            `tweet_id` = {tweet_id},
            `url` = '{url}';""".format(
                tweet_id=url[0]['tweet_id'],
                url=to_esc_sql(url[0]['url']))
        print url
        cur = db.cursor()
        cur.execute(query)
        db.commit()

load_config()
connect_db()
load_api()
connect_api()

for region in regions:
    for area in regions[region]['areas']:
        organise_raw_tweets(query_twitter(area['lat'], area['long'], area['range']),region)
        insert_data()
        print organised_tweets
        time.sleep(5)
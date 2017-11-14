import sys
import logging
from logging import config
from datetime import datetime

import json
import redis

import constants


def get_redis_db():
    return redis.Redis(host='redis', port=6379, db=0, decode_responses=True)


def normalize_timestamp(t):
    # 10000 miliseconds -> 10s
    return int(t / 10000) * 10000


def config_logging():
    logging.config.fileConfig('logging.conf')


def get_logger(name=constants.LOGGER_NAME):
    return logging.getLogger(name)


def get_token(name):
    return constants.SUPPORTED_TOKENS[name]


def init_deposit(balance, user, tokens, amount):
    for token in tokens:
        balance.deposit(user, token, amount)


def setup_data(rdb):
    if constants.MODE == 'simulation':
        # import simulation data
        data_imported = rdb.get('IMPORTED_SIMULATION_DATA')
        if not data_imported:
            logger.info('Import simulation data ...')
            ob_file = 'data/full_ob.dat'
            # ob_file = 'data/sample_ob.dat'
            try:
                copy_order_books_to_db(ob_file, rdb)
            except FileNotFoundError:
                sys.exit('Data is missing.')
            rdb.set('IMPORTED_SIMULATION_DATA', True)
            logger.info('Finish setup process.')


logger = logging.getLogger(constants.LOGGER_NAME)


def copy_order_books_to_db(ob_file, rdb):

    def load_order_books(ob_file):
        with open(ob_file, 'r')as f:
            for line in f:
                e = json.loads(line)
                for pair in e['data']:
                    base, quote = pair.lower().split('-')
                    for exchange in e['data'][pair]:
                        if exchange == 'liqui':
                            ob = e['data'][pair][exchange]
                            yield(base, quote, exchange, ob)

    order_books = load_order_books(ob_file)
    all_timestamp = set()

    for idx, ob in enumerate(order_books):
        base, quote, exchange, order_book = ob

        timestamp = order_book['Timestamp']
        all_timestamp.add(timestamp)
        timestamp = normalize_timestamp(timestamp)

        # handle the old format with 'BuyPrices' and 'SellPrices'
        if 'BuyPrices' in order_book:
            order_book['Asks'] = order_book['BuyPrices']
            order_book.pop('BuyPrices')
        if 'SellPrices' in order_book:
            order_book['Bids'] = order_book['SellPrices']
            order_book.pop('SellPrices')

        key = '_'.join(map(str, [exchange, base, quote, timestamp]))
        rdb.set(key, json.dumps(order_book))
        # if idx % 1000 == 0:
        # logger.debug('Timestamp: {}'.format(timestamp))
        # logger.debug('Base-Quote: {}-{}'.format(base, quote))  # e.g OMG-ETH
        # logger.debug('Exchange: {}'.format(exchange))  # e.g liqui
        # logger.debug('Key: {}'.format(key))
        # logger.debug('-' * 100)

    all_timestamp = list(all_timestamp)
    all_timestamp.sort()
    first, last = all_timestamp[0] / 1000, all_timestamp[-1] / 1000

    # logger.debug("First timestamp: {}".format(datetime.fromtimestamp(first)))
    # logger.debug("Last timestamp: {}".format(datetime.fromtimestamp(last)))

    with open('data/time_stamps.json', 'w') as f:
        f.write(json.dumps(all_timestamp))


def convert_ob_json_file(ob_json_file, new_file):
    """Convert order book json file to a new format
    """
    with open(ob_json_file, 'r') as ob_json:
        obs = json.loads(ob_json.read())
        with open(new_file, 'w') as new_f:
            for ob in obs:
                new_f.write(json.dumps(ob) + '\n')


if __name__ == '__main__':
    src, dst = 'data/full_ob', 'data/full_ob.dat'
    # src, dst = 'data/sample_ob', 'data/sample_ob.dat'
    convert_ob_json_file(src, dst)

    # import time

    # start = time.time()
    # rdb = get_redis_db()
    # copy_order_books_to_db(dst, rdb)
    # end = time.time()
    # print("Import time: {}s".format(end - start))

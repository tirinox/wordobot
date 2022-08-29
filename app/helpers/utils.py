import asyncio
import binascii
import hashlib
import inspect
import json
import logging
import os
import pickle
import random
import re
import time
from collections import deque, defaultdict
from functools import wraps, partial
from itertools import tee

import aiofiles
import aiohttp

from helpers.date_utils import today_str


def a_result_cached(ttl=60):
    def decorator(func):
        last_update_ts = -1.0
        last_result = None

        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal last_result, last_update_ts
            if last_update_ts < 0 or time.monotonic() - ttl > last_update_ts:
                last_result = await func(*args, **kwargs)
                last_update_ts = time.monotonic()
            return last_result

        return wrapper

    return decorator


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def async_wrap(func):
    @wraps(func)
    async def run(*args, loop=None, executor=None, **kwargs):
        if loop is None:
            loop = asyncio.get_event_loop()
        pfunc = partial(func, *args, **kwargs)
        return await loop.run_in_executor(executor, pfunc)

    return run


def circular_shuffled_iterator(lst):
    """
    Shuffle list, go round it, shuffle again.
    Infinite iterator.
    Guaranteed no duplicates (except of border cases sometimes)
    """
    if not lst:
        return None

    lst = list(lst)
    random.shuffle(lst)
    d = deque(lst)
    shifts = 0
    while True:
        yield d[0]
        d.rotate(1)
        shifts += 1
        if shifts >= len(d):
            random.shuffle(d)
            shifts = 0


def setup_logs(log_level):
    logging.basicConfig(
        level=logging.getLevelName(log_level),
        format='%(asctime)s %(levelname)s:%(name)s:%(funcName)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    logging.info('-' * 100)
    logging.info(f"Log level: {log_level}")


def pairwise(iterable):
    """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)


def load_pickle(path):
    try:
        if path and os.path.exists(path):
            with open(path, 'rb') as f:
                data = pickle.load(f)
                logging.info(f'Loaded pickled data of type {type(data)} from "{path}"')
                return data
    except Exception as e:
        logging.error(f'Failed to load pickled data "{path}"! Error is "{e!r}".')
        return None


def save_pickle(path, data):
    if path:
        with open(path, 'wb') as f:
            logging.info(f'Saving pickle to "{path}"...')
            pickle.dump(data, f)
            logging.info(f'Saving pickle to "{path}" done!')


def random_hex(length=12):
    return binascii.b2a_hex(os.urandom(length))


def class_logger(self):
    return logging.getLogger(self.__class__.__name__)


def parse_list_from_string(text: str, upper=False, lower=False, strip=True):
    items = re.split('[;,\n\t]', text)

    if lower:
        items = map(str.lower, items)
    elif upper:
        items = map(str.upper, items)

    if strip:
        items = map(str.strip, items)

    return [x for x in items if x]


def invert_dict_of_iterables(d: dict, factory=set, op=set.add):
    result = defaultdict(factory)
    for k, v in d.items():
        for item in v:
            # noinspection PyArgumentList
            op(result[item], k)
    return dict(result)


def invert_dict(d: dict):
    return dict(zip(d.values(), d.keys()))


def nested_set(dic, keys, value):
    if not keys:
        raise KeyError
    original = dic
    for key in keys[:-1]:
        dic = dic.setdefault(key, {})
    dic[keys[-1]] = value
    return original


def nested_get(dic, keys, default=None):
    if not keys:
        return default
    for key in keys[:-1]:
        dic = dic.get(key, {})
    return dic.get(keys[-1], default)


def tree_factory():
    return defaultdict(tree_factory)


def make_nested_default_dict(d):
    if not isinstance(d, dict):
        return d
    return defaultdict(tree_factory, {k: make_nested_default_dict(v) for k, v in d.items()})


def unique_ident(args, prec='full'):
    items = [today_str(prec), *map(str, args)]
    full_string = ''.join(items)
    return hashlib.md5(full_string.encode()).hexdigest()


async def download_file(url, target_path):
    async with aiohttp.ClientSession() as session:
        if not url:
            raise FileNotFoundError

        logging.info(f'Downloading file from {url}...')
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(target_path, mode='wb')
                await f.write(await resp.read())
                await f.close()

            return resp.status


class TooManyTriesException(BaseException):
    pass


def retries(times):
    assert times > 0

    def func_wrapper(f):
        async def wrapper(*args, **kwargs):
            outer_exc = None
            for time_no in range(times):
                # noinspection PyBroadException
                try:
                    return await f(*args, **kwargs)
                except Exception as exc:
                    outer_exc = exc
                logging.warning(f'Retrying {f} for {time_no + 1} time...')
            raise TooManyTriesException() from outer_exc

        return wrapper

    return func_wrapper


def run_once_async(f):
    """Runs a function (successfully) only once (async).
    The running can be reset by setting the `has_run` attribute to False
    """

    @wraps(f)
    async def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            result = await f(*args, **kwargs)
            wrapper.has_run = True
            return result

    wrapper.has_run = False
    return wrapper


nested_dict = lambda: defaultdict(nested_dict)


def safe_get(dct, *keys):
    for key in keys:
        try:
            dct = dct[key]
        except (KeyError, TypeError):
            return None
    return dct


class WithLogger:
    def __init__(self):
        self.logger = class_logger(self)


def json_cached_to_file_async(filename):
    def decorator(func):
        @wraps(func)
        async def inner(*args, **kwargs):
            try:
                with open(filename, 'r') as f:
                    return json.load(f)
            except Exception:
                result = await func(*args, **kwargs)
                with open(filename, 'w') as f:
                    json.dump(result, f)
                return result

        return inner

    return decorator


def vertical_text(t: str):
    return '\n'.join(t)


def filter_kwargs_according_function_signature(dict_to_filter, thing_with_kwargs):
    sig = inspect.signature(thing_with_kwargs)
    filter_keys = [param.name for param in sig.parameters.values() if param.kind == param.POSITIONAL_OR_KEYWORD]
    return {filter_key: dict_to_filter[filter_key] for filter_key in filter_keys}

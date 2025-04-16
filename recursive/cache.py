import fcntl
from loguru import logger
import threading
import os
from copy import deepcopy

from recursive.utils.helpers import (
    obj_to_hash,
    get_data_list_from_jsonl,
    append_jsonl,
    get_datatime,
    get_omit_json,
)


class FileLock:
    def __init__(self, file_path):
        self.file_path = file_path
        self.file = None

    def __enter__(self):
        self.file = open(self.file_path, "a")
        fcntl.flock(self.file, fcntl.LOCK_EX)
        return self.file

    def __exit__(self, exc_type, exc_value, traceback):
        fcntl.flock(self.file, fcntl.LOCK_UN)
        self.file.close()


class Cache:
    name_mode_to_cache = {}
    cache_lock = threading.Lock()

    def __init__(self, fn, mode="rw"):
        self.fn = fn
        self.info_fn = f"{fn}_info.jsonl"
        self.mode = mode
        if "r" in mode:
            try:
                self.cache_kv = self.read_cache()
            except Exception as e:
                print(f"Fail to fetch in cache {fn=}, {e=}")
                self.cache_kv = {}
        else:
            self.cache_kv = {}

        if "w" in mode:
            os.makedirs(os.path.dirname(fn), exist_ok=True)

        # print(f'cache_size: {len(self.cache_kv)}')

    @staticmethod
    def get_cache(fn, mode="rw"):
        os.makedirs(os.path.dirname(fn), exist_ok=True)
        with FileLock(f"{fn}.lock"):
            with Cache.cache_lock:
                key = (fn, mode)
                d = Cache.name_mode_to_cache
                if key not in d:
                    value = Cache(fn, mode)
                    d[key] = value

        return d[key]

    def read_cache(self):
        if not os.path.isfile(self.fn):
            return {}

        data_list = get_data_list_from_jsonl(self.fn)
        cache_kv = {}
        for data in data_list:
            key = data["key"]
            value = data["value"]
            cache_kv[key] = value

        return cache_kv

    def add(self, key, value, hint=None):
        if "w" not in self.mode:
            return

        with FileLock(f"{self.fn}.lock"):
            with Cache.cache_lock:
                # Overwrite
                # if self.has(key):
                #     return
                self.cache_kv[key] = value
                if value is not None:
                    data = dict(key=key, value=value)
                    data["add_time"] = get_datatime(mode=1)
                    if hint is not None:
                        data["hint"] = hint

                    append_jsonl(self.fn, data)

    def get(self, key):
        return self.cache_kv.get(key)

    def has(self, key):
        return key in self.cache_kv

    def get_cache(self, name, call_args_dict):
        obj = deepcopy(call_args_dict)
        obj["cache_name"] = name
        key = obj_to_hash(obj)
        if self.has(key):
            logger.debug(f"HIT cache：{name=}: {key=}")
            return self.get(key)
        else:
            return None

    def save_cache(self, name, call_args_dict, value):
        obj = deepcopy(call_args_dict)
        obj["cache_name"] = name
        show_obj = get_omit_json(obj)
        key = obj_to_hash(obj)

        if value is not None:
            logger.debug(f"ADD cache：{name=}: {key=}")
            self.add(key, value, hint=show_obj)

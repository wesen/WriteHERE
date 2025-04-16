import copy
import datetime
import hashlib
import json


def string_to_md5(string):
    md5 = hashlib.md5()
    md5.update(string.encode("utf-8"))
    return md5.hexdigest()


def json_default_dumps(data):
    if isinstance(data, set):
        return sorted(data, key=lambda _x: str(_x))

    if hasattr(data, "to_json") and callable(data.to_json):
        return data.to_json()

    if hasattr(data, "__dict__") and hasattr(data, "__class__"):
        ret = dict(
            cls_name=str(data.__class__),
            attr=data.__dict__,
        )
        return ret

    if hasattr(data, "__class__"):
        return str(data.__class__)

    return str(data)


def obj_to_hash(obj):
    s = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=json_default_dumps)
    ret = string_to_md5(s)
    return ret


def get_data_list_from_jsonl(fn):
    with open(fn) as f:
        data_list = [json.loads(line) for line in f]

    return data_list


def append_jsonl(fn, data):
    with open(fn, "a") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def get_datatime(mode=0):
    current_date = datetime.datetime.now()
    if mode == 0:
        formatted_date = current_date.strftime("%Y%m%d%H%M%S")
    elif mode == 1:
        formatted_date = current_date.strftime("%Y-%m-%d_%H:%M:%S")

    return formatted_date


def get_omit_json(data, max_str_len=100, max_list_len=10, to_str=True):
    data = copy.deepcopy(data)
    max_str_len = 10000

    def dfs(cur_data):
        if isinstance(cur_data, (list, tuple)):
            ret = [dfs(e) for e in cur_data[:max_list_len]]
            omit_cnt = len(cur_data) - max_list_len
            if omit_cnt > 0:
                ret.append(f"... Omiting #{omit_cnt} data")

            return ret

        if isinstance(cur_data, str):
            omit_cnt = len(cur_data) - max_str_len
            ret = cur_data[:max_str_len]
            if omit_cnt > 0:
                ret += f"...Omiting #{omit_cnt} chars"

            return ret

        if isinstance(cur_data, dict):
            return {key: dfs(value) for key, value in cur_data.items()}

        return cur_data

    data = dfs(data)
    ret = json.dumps(data, indent=2, ensure_ascii=False) if to_str else data
    return ret

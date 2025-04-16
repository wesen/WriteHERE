import json
from typing import List, Dict


def read_jsonl(filename: str, jsonl_format=True) -> List[Dict]:
    with open(filename, "r") as f:
        if filename.endswith(".jsonl") or jsonl_format:
            data = []
            for line in f.readlines():
                try:
                    data.append(json.loads(line))
                except SyntaxError as e:
                    print("load jsonl line error, msg: {}".format(str(e)))
                    continue
        else:
            data = json.load(f)

    return data

import re


def parse_tag_result(content, tag):
    start = False
    results = []
    for line in content.split("\n"):
        line = line.strip()
        if line == "<{}>".format(tag):
            start = True
        if line == "</{}>".format(tag):
            start = False
        if start:
            results.append(line)
    if len(results) > 0:
        results = results[1:]
        return "\n".join(results)
    if len(results) == 0:
        pattern = r"<{0}>(.*?)</{0}>".format(re.escape(tag))
        results = re.findall(pattern, content, re.DOTALL)
        match_res = []
        for result in results:
            match_res.append(result)
        match_res = "\n".join(match_res)
        return match_res
    return ""


def parse_hierarchy_tags_result(res, tags):
    if len(tags) == 0:
        raise Exception("len(tags) == 0")
    if isinstance(tags, str):
        tags = [tags]
    for tag in tags:
        res = parse_tag_result(res, tag)
    return res

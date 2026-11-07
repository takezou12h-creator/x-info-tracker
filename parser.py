import re
import json

def parse_sns_count(text_val):
    if not text_val or text_val == "不明":
        return 0
    cleaned = text_val.replace(",", "").strip()
    try:
        if '万' in cleaned or 'W' in cleaned or 'w' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 10000)
        elif 'K' in cleaned or 'k' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 1000)
        elif 'M' in cleaned or 'm' in cleaned:
            num_part = re.findall(r"[\d\.]+", cleaned)[0]
            return int(float(num_part) * 1000000)
        else:
            num_part = re.findall(r"\d+", cleaned)
            return int(num_part[0]) if num_part else 0
    except:
        return 0

def parse_saved_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    platform = data["platform"]
    username = data["username"]
    html = data["html"]
    json_str = json.dumps(data["json_list"], ensure_ascii=False)
    combined = json_str + "\n" + html

    metrics = {"following": 0, "followers": 0, "posts": 0}

    # 各SNSの内部データやメタ情報から正確な数値を探索
    if platform == "x":
        f_m = (re.search(r'"normal_followers_count"\s*:\s*(\d+)', combined) or
               re.search(r'"followers_count"\s*:\s*(\d+)', combined))
        fg_m = (re.search(r'"friends_count"\s*:\s*(\d+)', combined) or
                re.search(r'"following_count"\s*:\s*(\d+)', combined))
        p_m = (re.search(r'"statuses_count"\s*:\s*(\d+)', combined) or
               re.search(r'"media_count"\s*:\s*(\d+)', combined))

        if f_m: metrics["followers"] = int(f_m.group(1))
        if fg_m: metrics["following"] = int(fg_m.group(1))
        if p_m: metrics["posts"] = int(p_m.group(1))

    elif platform in ["instagram", "threads"]:
        # OGメタタグからの救済
        og_f_m = re.search(r'property="og:description"\s+content="([\d,.]+[\万KMwW]?)\s+Followers', html, re.IGNORECASE)
        if og_f_m:
            metrics["followers"] = parse_sns_count(og_f_m.group(1))

        f_m = (re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined) or
               re.search(r'"follower_count"\s*:\s*(\d+)', combined))
        fg_m = (re.search(r'"edge_follow"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined) or
                re.search(r'"following_count"\s*:\s*(\d+)', combined))
        p_m = (re.search(r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined) or
               re.search(r'"media_count"\s*:\s*(\d+)', combined))

        if f_m and metrics["followers"] == 0: metrics["followers"] = int(f_m.group(1))
        if fg_m: metrics["following"] = int(fg_m.group(1))
        if p_m: metrics["posts"] = int(p_m.group(1))

    return {
        "platform": platform,
        "username": username,
        **metrics
    }

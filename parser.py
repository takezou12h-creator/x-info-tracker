import re
import json

def parse_sns_count(text_val):
    if not text_val or text_val == "不明":
        return 0
    cleaned = str(text_val).replace(",", "").strip()
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

    platform = data.get("platform", "").lower()
    username = data.get("username", "")
    metrics = {"following": 0, "followers": 0, "posts": 0}

    # ---------------------------------------------------------
    # 1. X (fxtwitter / vxtwitter JSONアダプタ)
    # ---------------------------------------------------------
    if platform == "x":
        # 新方式（fxtwitter / vxtwitter の user オブジェクト）
        if "user" in data and isinstance(data["user"], dict):
            user = data["user"]
            source = data.get("source", "fxtwitter")
            if source == "vxtwitter":
                metrics["followers"] = int(user.get("followers_count") or 0)
                metrics["following"] = int(user.get("following_count") or 0)
                metrics["posts"] = int(user.get("tweet_count") or 0)
            else:
                metrics["followers"] = int(user.get("followers") or 0)
                metrics["following"] = int(user.get("following") or 0)
                metrics["posts"] = int(user.get("tweets") or 0)
            return {
                "platform": platform,
                "username": username,
                **metrics
            }

        # 旧方式フォールバック（念のため残置）
        html = data.get("html", "")
        json_str = json.dumps(data.get("json_list", []), ensure_ascii=False)
        combined = json_str + "\n" + html
        f_m = (re.search(r'"normal_followers_count"\s*:\s*(\d+)', combined) or
               re.search(r'"followers_count"\s*:\s*(\d+)', combined))
        fg_m = (re.search(r'"friends_count"\s*:\s*(\d+)', combined) or
                re.search(r'"following_count"\s*:\s*(\d+)', combined))
        p_m = (re.search(r'"statuses_count"\s*:\s*(\d+)', combined) or
               re.search(r'"media_count"\s*:\s*(\d+)', combined))
        if f_m: metrics["followers"] = int(f_m.group(1))
        if fg_m: metrics["following"] = int(fg_m.group(1))
        if p_m: metrics["posts"] = int(p_m.group(1))

    # ---------------------------------------------------------
    # 2. Instagram / Threads の解析（既存維持）
    # ---------------------------------------------------------
    elif platform in ["instagram", "threads"]:
        html = data.get("html", "")
        json_str = json.dumps(data.get("json_list", []), ensure_ascii=False)
        combined = json_str + "\n" + html

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

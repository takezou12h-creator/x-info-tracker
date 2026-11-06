import re
import json
import os

def parse_saved_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    platform = data["platform"]
    username = data["username"]
    html = data["html"]
    json_str = json.dumps(data["json_list"], ensure_ascii=False)

    combined_source = json_str + "\n" + html
    metrics = {"following": 0, "followers": 0, "posts": 0}

    if platform == "x":
        f_m = (re.search(r'"normal_followers_count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"followers_count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"name"\s*:\s*"Follows"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', combined_source))
        
        fg_m = (re.search(r'"friends_count"\s*:\s*(\d+)', combined_source) or
                re.search(r'"name"\s*:\s*"Friends"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', combined_source))
        
        p_m = (re.search(r'"statuses_count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"media_count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"name"\s*:\s*"Tweets"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', combined_source))

        if f_m: metrics["followers"] = int(f_m.group(1))
        if fg_m: metrics["following"] = int(fg_m.group(1))
        if p_m: metrics["posts"] = int(p_m.group(1))

    elif platform in ["instagram", "threads"]:
        # InstagramのOGタグ（シェア時メタ情報）や内部JSONからフォロワー数を強引に抜くパターンを追加
        og_f_m = re.search(r'property="og:description"\s+content="([\d,]+)\s+Followers', html, re.IGNORECASE)
        if og_f_m:
            metrics["followers"] = int(og_f_m.group(1).replace(",", ""))

        f_m = (re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"follower_count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"edge_followed_by":\{"count":(\d+)\}', combined_source))
        
        fg_m = (re.search(r'"edge_follow"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined_source) or
                re.search(r'"following_count"\s*:\s*(\d+)', combined_source))
        
        p_m = (re.search(r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"media_count"\s*:\s*(\d+)', combined_source))

        if f_m and metrics["followers"] == 0: metrics["followers"] = int(f_m.group(1))
        if fg_m: metrics["following"] = int(fg_m.group(1))
        if p_m: metrics["posts"] = int(p_m.group(1))

    # --- AIによる自動修復（フォールバック） ---
    if (metrics["followers"] == 0 or metrics["posts"] == 0) and os.environ.get("GEMINI_API_KEY"):
        print(f"  🤖 数値が不足しているためAI解析を実行中: @{username}")
        ai_metrics = extract_with_gemini(combined_source, username, platform)
        if ai_metrics.get("followers", 0) > 0 and metrics["followers"] == 0:
            metrics["followers"] = ai_metrics["followers"]
        if ai_metrics.get("following", 0) > 0 and metrics["following"] == 0:
            metrics["following"] = ai_metrics["following"]
        if ai_metrics.get("posts", 0) > 0 and metrics["posts"] == 0:
            metrics["posts"] = ai_metrics["posts"]

    return {
        "platform": platform,
        "username": username,
        **metrics
    }

def extract_with_gemini(source_text, username, platform):
    try:
        from google import genai
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        
        keywords = ["follower", "Follows", "following", "media_count", "statuses_count", "edge_followed_by", "Followers"]
        chunks = []
        for kw in keywords:
            for m in re.finditer(kw, source_text, re.IGNORECASE):
                start = max(0, m.start() - 150)
                end = min(len(source_text), m.end() + 250)
                chunks.append(source_text[start:end])
        
        snippet = "\n---\n".join(chunks)[:25000]
        if not snippet:
            snippet = source_text[:25000]

        prompt = f"""
        あなたはデータ抽出エンジンです。以下の{platform}の内部データ断片から、
        アカウント「{username}」の「フォロー数(following)」「フォロワー数(followers)」「投稿数(posts)」の正確な整数を見つけてください。
        省略表記（万やK）ではなく、1桁単位の正確な整数を優先してください。
        回答は以下のJSON形式のみを出力してください。見つからない項目は0にしてください。
        {{"following": 0, "followers": 0, "posts": 0}}

        データ断片:
        {snippet}
        """
        res = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
        match = re.search(r'\{.*?\}', res.text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"  ⚠️ AI解析失敗: {e}")
    
    return {"following": 0, "followers": 0, "posts": 0}

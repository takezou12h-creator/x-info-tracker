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

    # HTML内の<script>タグと裏通信のJSONを合体させて検索対象にする
    combined_source = json_str + "\n" + html
    metrics = {"following": 0, "followers": 0, "posts": 0}

    # --- 1. 正規表現による1桁単位の厳密な整数抽出 ---
    if platform == "x":
        # XのGraphQLデータ（UserByScreenName）または構造化データ(ld+json)を狙う
        f_m = (re.search(r'"normal_followers_count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"followers_count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"name"\s*:\s*"Follows"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', combined_source))
        
        fg_m = (re.search(r'"friends_count"\s*:\s*(\d+)', combined_source) or
                re.search(r'"name"\s*:\s*"Friends"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', combined_source))
        
        p_m = (re.search(r'"statuses_count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"name"\s*:\s*"Tweets"\s*,\s*"userInteractionCount"\s*:\s*(\d+)', combined_source))

        if f_m: metrics["followers"] = int(f_m.group(1))
        if fg_m: metrics["following"] = int(fg_m.group(1))
        if p_m: metrics["posts"] = int(p_m.group(1))

    elif platform in ["instagram", "threads"]:
        # Instagram / Threads の内部JSONキーを狙う
        f_m = (re.search(r'"edge_followed_by"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"follower_count"\s*:\s*(\d+)', combined_source))
        
        fg_m = (re.search(r'"edge_follow"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined_source) or
                re.search(r'"following_count"\s*:\s*(\d+)', combined_source))
        
        p_m = (re.search(r'"edge_owner_to_timeline_media"\s*:\s*\{\s*"count"\s*:\s*(\d+)', combined_source) or
               re.search(r'"media_count"\s*:\s*(\d+)', combined_source))

        if f_m: metrics["followers"] = int(f_m.group(1))
        if fg_m: metrics["following"] = int(fg_m.group(1))
        if p_m: metrics["posts"] = int(p_m.group(1))

    # --- 2. AIによる自動修復（フォールバック） ---
    # 仕様変更などでフォロワー数が取れなかった場合、Gemini APIで自動解析する
    if metrics["followers"] == 0 and os.environ.get("GEMINI_API_KEY"):
        print(f"  🤖 仕様変更を検知。AI自動修復を実行中: @{username}")
        ai_metrics = extract_with_gemini(combined_source, username, platform)
        if ai_metrics.get("followers", 0) > 0:
            metrics = ai_metrics

    return {
        "platform": platform,
        "username": username,
        **metrics
    }

def extract_with_gemini(source_text, username, platform):
    try:
        from google import genai
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        
        # 数値が含まれそうな箇所の前後だけを抜き出してAIに渡す（文字数制限対策）
        keywords = ["follower", "Follows", "friends_count", "statuses_count", "edge_followed_by"]
        chunks = []
        for kw in keywords:
            for m in re.finditer(kw, source_text, re.IGNORECASE):
                start = max(0, m.start() - 200)
                end = min(len(source_text), m.end() + 300)
                chunks.append(source_text[start:end])
        
        snippet = "\n---\n".join(chunks)[:25000]
        if not snippet:
            snippet = source_text[:25000]

        prompt = f"""
        あなたはデータ抽出エンジンです。以下の{platform}の内部データ断片から、
        アカウント「{username}」の「フォロー数(following)」「フォロワー数(followers)」「投稿数(posts)」の正確な整数を見つけてください。
        省略表記（万やK）ではなく、JSON等に含まれる1桁単位の正確な整数を優先してください。
        回答は以下のJSON形式のみを出力してください。見つからない項目は0にしてください。
        {{"following": 0, "followers": 0, "posts": 0}}

        データ断片:
        {snippet}
        """
        res = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        match = re.search(r'\{.*?\}', res.text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        print(f"  ⚠️ AI解析失敗: {e}")
    
    return {"following": 0, "followers": 0, "posts": 0}

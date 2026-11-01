import os
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials

# SNSごとのシート（タブ）名の定義
SHEET_NAMES = {
    "x": "X",
    "instagram": "Instagram",
    "threads": "Threads"
}

def get_or_create_worksheet(spreadsheet, sheet_title):
    """指定した名前のシートを取得する。存在しない場合は新規作成してヘッダーを入れる"""
    try:
        return spreadsheet.worksheet(sheet_title)
    except gspread.exceptions.WorksheetNotFound:
        print(f"  🆕 シート「{sheet_title}」が存在しないため新規作成します...")
        ws = spreadsheet.add_worksheet(title=sheet_title, rows="2000", cols="10")
        # 1行目に画像と同じ見出しを自動挿入
        ws.append_row(["日付", "ID", "フォロー数", "フォロワー数", "ポスト数"], value_input_option="USER_ENTERED")
        return ws

def write_to_spreadsheet(parsed_results):
    if not parsed_results:
        print("⚠️ 書き込むデータがありません。")
        return

    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GCP_JSON_KEY"]),
        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    )
    spreadsheet = gspread.authorize(creds).open_by_key(os.environ["SPREADSHEET_ID"])

    # 日本時間（JST）で今日の日付を取得
    jst = datetime.timezone(datetime.timedelta(hours=9))
    today_str = datetime.datetime.now(jst).strftime("%Y-%m-%d")

    # SNS（platform）ごとにデータを振り分ける
    grouped_rows = {"x": [], "instagram": [], "threads": []}
    for item in parsed_results:
        platform = item["platform"].lower()
        row = [
            today_str,
            item["username"],
            item["following"],
            item["followers"],
            item["posts"]
        ]
        if platform in grouped_rows:
            grouped_rows[platform].append(row)
        else:
            grouped_rows.setdefault(platform, []).append(row)

    # SNSごとに該当のタブを開いて一括書き込み
    for platform, rows in grouped_rows.items():
        if not rows:
            continue
        
        sheet_title = SHEET_NAMES.get(platform, platform.upper())
        ws = get_or_create_worksheet(spreadsheet, sheet_title)
        
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📝 シート「{sheet_title}」に {len(rows)} 件のデータを一括記録しました！")

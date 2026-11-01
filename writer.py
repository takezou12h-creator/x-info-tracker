import os
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials

def write_to_spreadsheet(parsed_results):
    if not parsed_results:
        print("⚠️ 書き込むデータがありません。")
        return

    creds = Credentials.from_service_account_info(
        json.loads(os.environ["GCP_JSON_KEY"]),
        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    )
    ws = gspread.authorize(creds).open_by_key(os.environ["SPREADSHEET_ID"]).get_worksheet(0)

    # 日本時間（JST）で今日の日付を取得
    jst = datetime.timezone(datetime.timedelta(hours=9))
    today_str = datetime.datetime.now(jst).strftime("%Y-%m-%d")

    rows_to_append = []
    for item in parsed_results:
        # 複数SNSを混ぜても分かるようにしたい場合は、f"{item['username']} ({item['platform']})" に変更可能
        # 現状は画像に合わせてユーザーIDのみを記録します
        row = [
            today_str,
            item["username"],
            item["following"],
            item["followers"],
            item["posts"]
        ]
        rows_to_append.append(row)

    # 全アカウント分を1回の通信で一括書き込み（API制限エラー対策）
    ws.append_rows(rows_to_append, value_input_option="USER_ENTERED")
    print(f"📝 スプレッドシートに {len(rows_to_append)} 件のデータを一括記録しました！")

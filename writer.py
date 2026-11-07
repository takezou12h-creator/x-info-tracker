import os
import json
import datetime
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAMES = {
    "x": "X",
    "instagram": "Instagram",
    "threads": "Threads"
}

def get_or_create_worksheet(spreadsheet, sheet_title):
    try:
        return spreadsheet.worksheet(sheet_title)
    except gspread.exceptions.WorksheetNotFound:
        print(f"  🆕 タブ「{sheet_title}」が存在しないため新規作成します...")
        ws = spreadsheet.add_worksheet(title=sheet_title, rows="2000", cols="10")
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

    jst = datetime.timezone(datetime.timedelta(hours=9))
    today_str = datetime.datetime.now(jst).strftime("%Y-%m-%d")

    grouped_rows = {"x": [], "instagram": [], "threads": []}
    for item in parsed_results:
        platform = item["platform"].lower()
        row = [today_str, item["username"], item["following"], item["followers"], item["posts"]]
        if platform in grouped_rows:
            grouped_rows[platform].append(row)

    for platform, rows in grouped_rows.items():
        if not rows:
            continue
        sheet_title = SHEET_NAMES.get(platform, platform.upper())
        ws = get_or_create_worksheet(spreadsheet, sheet_title)
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        print(f"📝 タブ「{sheet_title}」に {len(rows)} 件のデータを一括記録しました！")

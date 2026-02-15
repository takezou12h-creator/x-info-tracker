import os
import json
import gspread
from google.oauth2.service_account import Credentials

def test_connection():
    print("🚀 接続テスト開始...")
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        env_key = os.environ.get("GCP_JSON_KEY")
        info = json.loads(env_key)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get("SPREADSHEET_ID")
        sh = client.open_by_key(sheet_id)
        ws = sh.get_worksheet(0) # 一番左のシート
        
        ws.append_row(["テスト実行", "成功"])
        print("✅ スプレッドシートへの書き込みに成功しました！")
        
    except Exception as e:
        print(f"❌ エラーが発生しました:\n{e}")

if __name__ == "__main__":
    test_connection()

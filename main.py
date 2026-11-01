import sys
from fetcher import fetch_all_targets
from parser import parse_saved_file
from writer import write_to_spreadsheet

def load_targets(csv_path="targets.csv"):
    targets = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip().replace("@", "") for p in line.split(",")]
            if len(parts) >= 2:
                targets.append((parts[0].lower(), parts[1]))
            else:
                # カンマがない従来の書き方の場合は自動的に「x」として扱う
                targets.append(("x", parts[0]))
    return targets

def main():
    print("🚀 SNSフォロワー集計システムを開始します")
    targets = load_targets()
    print(f"📋 対象アカウント数: {len(targets)}件\n")

    # Step 1: データの取得と保存
    saved_files = fetch_all_targets(targets)

    # Step 2: 保存したデータの解析
    print("\n🔍 保存データの解析を開始します...")
    valid_results = []
    for filepath in saved_files:
        res = parse_saved_file(filepath)
        if res["followers"] > 0 or res["following"] > 0:
            print(f"  ✅ [{res['platform'].upper()}] @{res['username']} -> フォロー:{res['following']:,} / フォロワー:{res['followers']:,} / 投稿:{res['posts']:,}")
            valid_results.append(res)
        else:
            print(f"  ❌ [{res['platform'].upper()}] @{res['username']} -> 数値の抽出に失敗しました")

    # Step 3: スプレッドシートへの記録
    print("\n📊 スプレッドシートへの書き込みを開始します...")
    if valid_results:
        write_to_spreadsheet(valid_results)
    else:
        print("❌ 有効なデータが0件のため、書き込みをスキップしました。")
        sys.exit(1)

if __name__ == "__main__":
    sys.stdout.reconfigure(line_buffering=True)
    main()

"""
CLI Script to Search X (Twitter) Accounts by Keyword & Topic
Usage:
    python search_accounts.py "крипта"
    python search_accounts.py "alpha caller" --limit 5
    python search_accounts.py "solana" --min-followers 1000 --export
"""

import sys
import json
import argparse
from modules.account_searcher import AccountSearcher

# Ensure utf-8 on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Search Twitter (X) Accounts by Topic / Keyword")
    parser.add_argument("keyword", nargs="?", default="крипта", help="Keyword or topic to search (e.g. крипта, alpha caller, solana, angel)")
    parser.add_argument("--limit", "-l", type=int, default=6, help="Maximum number of accounts to return (default: 6)")
    parser.add_argument("--min-followers", type=int, default=500, help="Minimum follower count (default: 500)")
    parser.add_argument("--export", "-e", action="store_true", help="Export results to found_accounts.json")

    args = parser.parse_args()

    print("\n" + "=" * 70)
    print(f"  🔍 ПОИСК АККАУНТОВ X (TWITTER) ПО ТЕМЕ: \"{args.keyword}\"")
    print("=" * 70)
    print(f"[*] Сбор и фильтрация аккаунтов (лимит: {args.limit}, мин. фолловеров: {args.min_followers})...\n")

    searcher = AccountSearcher()
    results = searcher.search_accounts(keyword=args.keyword, limit=args.limit, min_followers=args.min_followers)

    if not results:
        print("[!] По данному запросу не найдено подходящих аккаунтов.")
        return

    print(f"[+] Найдено {len(results)} релевантных аккаунтов:\n")

    for i, acc in enumerate(results, 1):
        clean_bio = (acc.get("bio") or "").replace("\n", " ").strip()
        badge = " ✔ (Verified)" if acc.get("is_blue_verified") else ""
        print(f"----------------------------------------------------------------------")
        print(f"#{i} {acc['name']} (@{acc['screen_name']}){badge} | Матч: {acc['match_score']}%")
        print(f"    Категория:  {acc['category']}")
        print(f"    Подписчики: {acc['followers_count']:,} | Твитов: {acc['tweets_count']:,}")
        print(f"    Ссылка:     {acc['url']}")
        if clean_bio:
            print(f"    Bio:        {clean_bio[:120]}...")
        print(f"\n    ✉️  ГОТОВЫЙ АУТРИЧ ОТ rutraderbtc:")
        print(f"    \"{acc['outreach_pitch']}\"")
        print()

    print("=" * 70)

    if args.export:
        export_file = "found_accounts.json"
        with open(export_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[+] Результаты успешно экспортированы в {export_file}")


if __name__ == "__main__":
    main()

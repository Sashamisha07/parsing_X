"""
X (Twitter) Profile & Content Analyzer
Analyzes parsed tweets and profile data:
- Overall stats & Engagement Rates (ER)
- Cashtags & Crypto assets breakdown
- Top viral posts (views, likes, retweets)
- Posting activity and timeline patterns
- Generates Markdown analytical report
"""

import sys
import json
from datetime import datetime
from collections import Counter
from typing import Dict, Any, List
import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


class XAnalyzer:
    def __init__(self, data_path: str = "rutradebtc_data.json"):
        with open(data_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.profile = self.data.get("profile", {})
        self.tweets = self.data.get("tweets", [])
        self.df = pd.DataFrame(self.tweets)

    def analyze(self) -> Dict[str, Any]:
        if self.df.empty:
            return {"error": "No tweets to analyze"}

        total_tweets = len(self.df)
        total_views = int(self.df["views"].sum())
        total_likes = int(self.df["likes"].sum())
        total_retweets = int(self.df["retweets"].sum())
        total_replies = int(self.df["replies"].sum())
        total_bookmarks = int(self.df["bookmarks"].sum())

        avg_views = total_views / total_tweets if total_tweets else 0
        avg_likes = total_likes / total_tweets if total_tweets else 0
        avg_retweets = total_retweets / total_tweets if total_tweets else 0
        avg_replies = total_replies / total_tweets if total_tweets else 0

        # Engagement Rate on Impressions / Views: (Likes + RT + Replies) / Views * 100
        er_views = ((total_likes + total_retweets + total_replies) / total_views * 100) if total_views > 0 else 0

        # Engagement Rate on Followers
        followers = self.profile.get("followers_count") or 1
        er_followers = ((avg_likes + avg_retweets + avg_replies) / followers * 100)

        # Cashtag frequency and performance
        all_cashtags = []
        cashtag_stats = {}
        for _, row in self.df.iterrows():
            tags = row.get("cashtags", [])
            for tag in tags:
                all_cashtags.append(tag)
                if tag not in cashtag_stats:
                    cashtag_stats[tag] = {"count": 0, "views": [], "likes": []}
                cashtag_stats[tag]["count"] += 1
                cashtag_stats[tag]["views"].append(row["views"])
                cashtag_stats[tag]["likes"].append(row["likes"])

        cashtag_summary = []
        for tag, stats in cashtag_stats.items():
            cashtag_summary.append({
                "ticker": f"${tag}",
                "mentions": stats["count"],
                "avg_views": round(sum(stats["views"]) / len(stats["views"])),
                "avg_likes": round(sum(stats["likes"]) / len(stats["likes"]))
            })
        cashtag_summary.sort(key=lambda x: x["mentions"], reverse=True)

        # Contract addresses
        contracts = []
        for c_list in self.df["contract_addresses"]:
            if isinstance(c_list, list):
                contracts.extend(c_list)
        contracts = list(set(contracts))

        # Top posts by views
        top_by_views = self.df.sort_values(by="views", ascending=False).head(3).to_dict(orient="records")

        # Top posts by likes
        top_by_likes = self.df.sort_values(by="likes", ascending=False).head(3).to_dict(orient="records")

        return {
            "summary": {
                "sample_size": total_tweets,
                "total_views": total_views,
                "total_likes": total_likes,
                "total_retweets": total_retweets,
                "total_replies": total_replies,
                "avg_views": round(avg_views, 1),
                "avg_likes": round(avg_likes, 1),
                "avg_retweets": round(avg_retweets, 1),
                "avg_replies": round(avg_replies, 1),
                "er_views_pct": round(er_views, 2),
                "er_followers_pct": round(er_followers, 4)
            },
            "cashtags": cashtag_summary,
            "contracts": contracts,
            "top_by_views": top_by_views,
            "top_by_likes": top_by_likes
        }

    def print_report(self, results: Dict[str, Any]):
        p = self.profile
        s = results["summary"]

        print("=" * 60)
        print(f"       АНАЛИЗ ПРОФИЛЯ X: @{p.get('screen_name')} ({p.get('name')})")
        print("=" * 60)
        print(f"Подписчики:         {p.get('followers_count', 0):,}")
        print(f"Подписки:           {p.get('following_count', 0):,}")
        print(f"Всего постов в X:   {p.get('tweets_count', 0):,}")
        print(f"Верификация:        {'Да (Blue Verified)' if p.get('is_blue_verified') else 'Нет'}")
        print(f"Описание / Bio:     {p.get('bio')}")
        print("-" * 60)
        print(f"Выборка постов для анализа: {s['sample_size']} шт.")
        print(f"Всего просмотров выборки:   {s['total_views']:,}")
        print(f"Средние просмотры на пост:  {s['avg_views']:,}")
        print(f"Средние лайки на пост:      {s['avg_likes']}")
        print(f"Средние ретвиты на пост:    {s['avg_retweets']}")
        print(f"Средние ответы на пост:     {s['avg_replies']}")
        print(f"Вовлеченность (ER просмотры): {s['er_views_pct']}%")
        print(f"Вовлеченность (ER подписчики): {s['er_followers_pct']}%")
        print("-" * 60)

        print("\nТОП УПОМИНАЕМЫХ КРИПТО-АКТИВОВ ($TICKERS):")
        if results["cashtags"]:
            for ct in results["cashtags"]:
                print(f"  • {ct['ticker']:<10} | Упоминаний: {ct['mentions']} | Ср. просмотров: {ct['avg_views']:,} | Ср. лайков: {ct['avg_likes']}")
        else:
            print("  (Нет каштагов в текущей выборке)")

        if results["contracts"]:
            print("\nОБНАРУЖЕННЫЕ АДРЕСА СМАРТ-КОНТРАКТОВ:")
            for c in results["contracts"]:
                print(f"  • {c}")

        print("\nТОП-3 ПОСТА ПО ПРОСМОТРАМ (VIEWS):")
        for i, post in enumerate(results["top_by_views"], 1):
            print(f"  {i}. [{post['created_at']}] Просмотров: {post['views']:,} | Лайков: {post['likes']} | RT: {post['retweets']}")
            print(f"     URL: {post['url']}")
            clean_text = post['text'].replace('\n', ' ')[:100]
            print(f"     Текст: {clean_text}...\n")

        print("=" * 60)

    def export_markdown_report(self, results: Dict[str, Any], output_path: str = "analysis_report.md"):
        p = self.profile
        s = results["summary"]

        md = []
        md.append(f"# Аналитический отчет по профилю X: @{p.get('screen_name')}\n")
        md.append(f"- **Имя автора:** {p.get('name')}")
        md.append(f"- **Ссылка:** https://x.com/{p.get('screen_name')}")
        md.append(f"- **Подписчики:** {p.get('followers_count', 0):,}")
        md.append(f"- **Подписки:** {p.get('following_count', 0):,}")
        md.append(f"- **Всего твитов на аккаунте:** {p.get('tweets_count', 0):,}")
        md.append(f"- **Верификация:** {'Blue Verified' if p.get('is_blue_verified') else 'Обычный'}")
        md.append(f"- **Bio:** {p.get('bio')}\n")

        md.append("## 1. Метрики вовлеченности (Engagement Metrics)\n")
        md.append("| Метрика | Значение |")
        md.append("|---|---|")
        md.append(f"| Размер исследованной выборки | {s['sample_size']} твитов |")
        md.append(f"| Суммарные просмотры (Views) | {s['total_views']:,} |")
        md.append(f"| Средние просмотры на твит | {s['avg_views']:,} |")
        md.append(f"| Средние лайки на твит | {s['avg_likes']} |")
        md.append(f"| Средние репосты (RT) | {s['avg_retweets']} |")
        md.append(f"| Средние комментарии | {s['avg_replies']} |")
        md.append(f"| Engagement Rate (от просмотров) | {s['er_views_pct']}% |")
        md.append(f"| Engagement Rate (от подписчиков) | {s['er_followers_pct']}% |\n")

        md.append("## 2. Анализ криптовалютных тикеров и сигналов\n")
        if results["cashtags"]:
            md.append("| Тикер | Упоминаний | Средние просмотры | Средние лайки |")
            md.append("|---|---|---|---|")
            for ct in results["cashtags"]:
                md.append(f"| **{ct['ticker']}** | {ct['mentions']} | {ct['avg_views']:,} | {ct['avg_likes']} |")
            md.append("")

        if results["contracts"]:
            md.append("### Смарт-контракты в публикациях:")
            for c in results["contracts"]:
                md.append(f"- `{c}`")
            md.append("")

        md.append("## 3. Топ публикаций по охвату\n")
        for i, post in enumerate(results["top_by_views"], 1):
            md.append(f"### #{i} — [{post['created_at']}] ({post['views']:,} просмотров)")
            md.append(f"- **Ссылка:** {post['url']}")
            md.append(f"- **Статистика:** {post['likes']} лайков, {post['retweets']} ретвитов, {post['replies']} комментариев")
            md.append(f"- **Текст:**\n> {post['text'].replace(chr(10), chr(10) + '> ')}\n")

        report_text = "\n".join(md)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"[+] Отчет сохранен в файл: {output_path}")


if __name__ == "__main__":
    analyzer = XAnalyzer("rutradebtc_data.json")
    results = analyzer.analyze()
    analyzer.print_report(results)
    analyzer.export_markdown_report(results)

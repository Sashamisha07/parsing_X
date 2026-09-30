"""
CLI Interface for Crypto Twitter & DexScreener Outreach
Run from terminal to analyze influencers, discover similar coins, and export leads to Excel/CSV.
"""

import sys
import argparse
from modules.similarity_engine import SimilarityEngine
from modules.outreach_manager import OutreachManager

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Crypto X & DexScreener Outreach Studio")
    parser.add_argument("--target", "-t", default="rutradebtc", help="Target Twitter username or URL (default: rutradebtc)")
    parser.add_argument("--chain", "-c", default="all", help="Target blockchain (solana, robinhood, base, ethereum, bsc, all)")
    parser.add_argument("--min-fdv", type=float, default=50_000, help="Minimum Market Cap / FDV in USD")
    parser.add_argument("--max-fdv", type=float, default=25_000_000, help="Maximum Market Cap / FDV in USD")
    parser.add_argument("--min-liq", type=float, default=20_000, help="Minimum Liquidity in USD")
    parser.add_argument("--min-vol", type=float, default=50_000, help="Minimum 24h Volume in USD")
    parser.add_argument("--limit", type=int, default=30, help="Limit number of similar projects")
    parser.add_argument("--find-influencers", action="store_true", default=True, help="Find and display similar Twitter influencers/callers")
    parser.add_argument("--pitch", action="store_true", help="Generate sample outreach pitches for influencer and dev leads")
    parser.add_argument("--export", action="store_true", help="Export results to outreach_leads.xlsx and outreach_leads.csv")

    args = parser.parse_args()

    engine = SimilarityEngine()
    outreach = OutreachManager("outreach_leads.json")

    print("\n" + "=" * 65)
    print(f"  1. АНАЛИЗ ПРОФИЛЯ ТВИТТЕР: {args.target}")
    print("=" * 65)

    inf_data = engine.analyze_influencer(args.target)
    prof = inf_data["profile"]
    coins = inf_data["promoted_coins"]
    dna = inf_data["influencer_dna"]

    print(f"Автор: {prof['name']} (@{prof['screen_name']})")
    print(f"Подписчики: {prof['followers_count']:,} | Твитов: {prof['tweets_count']:,}")
    print(f"Bio: {prof['bio']}")
    print(f"\nОбнаружено {len(coins)} активов на DexScreener:")

    for c in coins:
        twitter = c.get("twitter_url") or "—"
        tg = c.get("telegram_url") or "—"
        print(f"  • ${c['symbol']:<10} | Сеть: {c['chain_id']:<10} | Капа: ${c['fdv']:>12,.0f} | Ликвидность: ${c['liquidity_usd']:>10,.0f}")
        if c.get("sample_tweet_text"):
            clean_snippet = " ".join(c['sample_tweet_text'].split())[:80]
            print(f"    📝 Пост: \"{clean_snippet}...\"")
        print(f"    𝕏 Twitter: {twitter} | TG: {tg}")

    print("\n" + "=" * 65)
    print("  2. РЕКОМЕНДУЕМЫЙ ПРОФИЛЬ (ASSET DNA):")
    print("=" * 65)
    print(f"Распределение сетей: {dna.get('chains_distribution')}")
    print(f"Рекомендуемая сеть:  {dna.get('recommended_chain')}")
    print(f"Диапазон капы:       ${dna.get('min_fdv'):,.0f} - ${dna.get('max_fdv'):,.0f}")
    print(f"Мин. ликвидность:    ${dna.get('min_liquidity'):,.0f}")

    if args.find_influencers:
        print("\n" + "=" * 65)
        print("  3. ПОХОЖИЕ TWITTER-АККАУНТЫ (КОЛЛЕРЫ / ИНФЛЮЕНСЕРЫ):")
        print("=" * 65)
        similar_infs = engine.find_similar_influencers(prof, coins, limit=5)
        if similar_infs:
            for i, inf in enumerate(similar_infs, 1):
                clean_bio = (inf.get('bio') or '').replace('\n', ' ')[:90]
                print(f"  {i}. {inf['name']} (@{inf['screen_name']}) [{inf['similarity_score']}% Матч]")
                print(f"     Подписчики: {inf['followers_count']:,} | 𝕏: {inf['url']}")
                print(f"     Bio: {clean_bio}...")
                if inf.get('recent_coins'):
                    print(f"     Монеты в ленте: {inf['recent_coins']}")
                print()
        else:
            print("  Похожие аккаунты не обнаружены.")

    selected_chain = args.chain if args.chain != "all" else dna.get("recommended_chain", "all")
    print("\n" + "=" * 65)
    print(f"  4. ПОИСК ПОХОЖИХ ПРОЕКТОВ НА DEXSCREENER (Сеть: {selected_chain})")
    print("=" * 65)

    res = engine.find_matching_projects(
        chain=selected_chain,
        min_fdv=args.min_fdv,
        max_fdv=args.max_fdv,
        min_liquidity=args.min_liq,
        min_volume=args.min_vol,
        require_socials=True,
        source_influencer=prof["screen_name"],
        limit=args.limit,
    )

    found_coins = res["coins"]
    print(f"\nНайдено {len(found_coins)} подходящих проектов:")

    for i, c in enumerate(found_coins[:15], 1):
        print(f"\n{i}. ${c['symbol']} ({c['name']}) [Матч: {c.get('similarity_score', 0)}%]")
        print(f"   Сеть: {c['chain_id']} | FDV: ${c['fdv']:,.0f} | Ликвидность: ${c['liquidity_usd']:,.0f} | Объем 24ч: ${c['volume_24h']:,.0f}")
        print(f"   𝕏 Twitter: {c.get('twitter_url') or '—'}")
        print(f"   💬 TG дева: {c.get('telegram_url') or '—'}")
        print(f"   📈 График: {c.get('dex_url')}")

    if args.pitch:
        from modules.outreach_generator import OutreachGenerator
        print("\n" + "=" * 65)
        print("  5. ПРИМЕРЫ СГЕНЕРИРОВАННЫХ OUTREACH-ПИТЧЕЙ:")
        print("=" * 65)
        inf_pitches = OutreachGenerator.generate_pitches_for_influencer(
            influencer_profile=prof,
            coin_data=coins[0] if coins else None,
            my_project_name="AlphaX Protocol",
            my_chain=dna.get("recommended_chain", "Solana")
        )
        print("\n[Питч для инфлюенсера (RU)]:")
        print("-" * 40)
        print(inf_pitches.get("ru_collab_pitch"))
        print("-" * 40)
        print("\n[Питч для инфлюенсера (EN)]:")
        print("-" * 40)
        print(inf_pitches.get("en_sponsored_call"))
        print("-" * 40)

        if found_coins:
            dev_pitches = OutreachGenerator.generate_pitches_for_dev(
                candidate_project=found_coins[0],
                influencer_profile=prof
            )
            print(f"\n[Питч для разработчиков ${found_coins[0]['symbol']} (RU)]:")
            print("-" * 40)
            print(dev_pitches.get("ru_dev_marketing"))
            print("-" * 40)

    if args.export:
        xlsx = engine.outreach.export_excel("outreach_leads.xlsx")
        csv = engine.outreach.export_csv("outreach_leads.csv")
        print("\n" + "=" * 65)
        print(f"[+] Успешно экспортировано {len(engine.outreach.leads)} лидов:")
        print(f"    - Excel: {xlsx}")
        print(f"    - CSV:   {csv}")
        print("=" * 65)


if __name__ == "__main__":
    main()

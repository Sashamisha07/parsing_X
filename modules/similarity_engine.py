"""
Similarity Engine Module
Orchestrates the workflow:
1. Twitter Influencer Extraction -> 2. DexScreener Profiling -> 3. Similar Project Search -> 4. Dev Outreach Leads
"""

import math
from typing import Dict, List, Any, Optional
from modules.twitter_collector import TwitterCollector
from modules.dexscreener_client import DexScreenerClient
from modules.outreach_manager import OutreachManager
from modules.influencer_finder import InfluencerFinder


class SimilarityEngine:
    def __init__(self, auth_token: Optional[str] = None, ct0: Optional[str] = None):
        self.collector = TwitterCollector(auth_token=auth_token, ct0=ct0)
        self.dex = DexScreenerClient()
        self.outreach = OutreachManager()
        self.influencer_finder = InfluencerFinder(collector=self.collector)
        self._influencer_cache: Dict[str, Dict[str, Any]] = {}

    def analyze_influencer(self, username_or_url: str) -> Dict[str, Any]:
        """
        Step 1 & 2:
        Scrapes Twitter profile -> Extracts crypto assets -> Resolves via DexScreener
        """
        clean_key = self.collector.clean_handle(username_or_url).lower()
        if clean_key in self._influencer_cache:
            print(f"[*] Returning cached analysis for @{clean_key}")
            return self._influencer_cache[clean_key]

        print(f"[*] Scraping Twitter account: {username_or_url}")
        tw_data = self.collector.fetch_user_data(username_or_url)
        profile = tw_data["profile"]
        promoted_assets = tw_data["promoted_assets"]

        print(f"[*] Found {len(promoted_assets)} candidate assets in tweets. Resolving on DexScreener...")
        resolved_coins: List[Dict[str, Any]] = []

        for asset in promoted_assets:
            resolved = self.dex.resolve_asset(asset)
            if resolved:
                resolved_coins.append(resolved)

        print(f"[+] Successfully resolved {len(resolved_coins)} coins on DexScreener!")
        influencer_dna = self.dex.analyze_influencer_dna(resolved_coins)

        result = {
            "profile": profile,
            "tweets": tw_data["tweets"],
            "promoted_coins": resolved_coins,
            "influencer_dna": influencer_dna,
        }
        self._influencer_cache[clean_key] = result
        return result

    def calculate_similarity_score(
        self, candidate: Dict[str, Any], target_chain: Optional[str], median_fdv: float, median_liq: float
    ) -> int:
        """
        Calculates similarity score (0 - 100) based on:
        - Chain alignment (30 pts)
        - FDV proximity (30 pts)
        - Liquidity proximity (20 pts)
        - Active socials (20 pts)
        """
        score = 0

        # Chain score
        if target_chain and target_chain != "all":
            if (candidate.get("chain_id") or "").lower() == target_chain.lower():
                score += 30
        else:
            score += 30

        # FDV score (closer in log scale = higher score)
        cand_fdv = candidate.get("fdv") or 1
        if median_fdv > 0 and cand_fdv > 0:
            diff_ratio = abs(math.log10(cand_fdv) - math.log10(median_fdv))
            fdv_score = max(0, 30 - int(diff_ratio * 15))
            score += fdv_score

        # Liquidity score
        cand_liq = candidate.get("liquidity_usd") or 1
        if median_liq > 0 and cand_liq > 0:
            diff_ratio_liq = abs(math.log10(cand_liq) - math.log10(median_liq))
            liq_score = max(0, 20 - int(diff_ratio_liq * 10))
            score += liq_score

        # Socials score (Twitter and Telegram are critical for dev outreach)
        if candidate.get("twitter_url"):
            score += 10
        if candidate.get("telegram_url"):
            score += 10

        return min(100, max(1, score))

    def find_matching_projects(
        self,
        chain: Optional[str] = "all",
        min_fdv: float = 50_000,
        max_fdv: float = 25_000_000,
        min_liquidity: float = 20_000,
        min_volume: float = 50_000,
        require_socials: bool = True,
        source_influencer: str = "",
        limit: int = 40,
    ) -> Dict[str, Any]:
        """
        Step 3 & 4:
        Searches DexScreener for projects matching filter criteria,
        ranks them by similarity and volume, and extracts dev contact info.
        """
        print(f"[*] Searching DexScreener for similar coins: Chain={chain}, FDV=${min_fdv:,.0f}-${max_fdv:,.0f}, MinLiq=${min_liquidity:,.0f}")
        coins = self.dex.find_similar_coins(
            chain=chain,
            min_fdv=min_fdv,
            max_fdv=max_fdv,
            min_liquidity=min_liquidity,
            min_volume=min_volume,
            require_socials=require_socials,
            limit=limit,
        )

        target_chain = chain if chain and chain != "all" else None
        median_fdv = (min_fdv + max_fdv) / 2 if max_fdv < 100_000_000 else 1_000_000
        median_liq = max(min_liquidity * 2, 50_000)

        for c in coins:
            c["similarity_score"] = self.calculate_similarity_score(c, target_chain, median_fdv, median_liq)

        # Sort primarily by similarity score, then volume
        coins.sort(key=lambda x: (x.get("similarity_score", 0), x.get("volume_24h", 0)), reverse=True)

        # Save into Outreach Leads
        added = self.outreach.add_or_update_leads(coins, source_influencer=source_influencer)
        print(f"[+] Added/Updated {added} leads in the outreach database.")

        return {
            "total_found": len(coins),
            "coins": coins,
            "applied_filters": {
                "chain": chain,
                "min_fdv": min_fdv,
                "max_fdv": max_fdv,
                "min_liquidity": min_liquidity,
                "min_volume": min_volume,
            },
        }

    def find_similar_influencers(
        self, target_profile: Dict[str, Any], promoted_coins: List[Dict[str, Any]], limit: int = 8
    ) -> List[Dict[str, Any]]:
        """Discovers similar Twitter influencers/callers in the same crypto niche."""
        return self.influencer_finder.find_similar_influencers(
            target_profile=target_profile, promoted_coins=promoted_coins, limit=limit
        )


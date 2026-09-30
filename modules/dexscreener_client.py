"""
DexScreener Client Module
Interacts with DexScreener Public REST API to:
1. Search and profile assets promoted by Twitter influencers.
2. Calculate the influencer's "Asset Profile / DNA" (typical chains, FDV, liquidity, volume).
3. Discover similar tokens using DexScreener Boosts, Profiles, and trending pools.
4. Extract official Twitter, Telegram, and developer contacts.
"""

import time
from typing import Dict, List, Any, Optional
from curl_cffi import requests


class DexScreenerClient:
    BASE_URL = "https://api.dexscreener.com"

    def __init__(self):
        self.session = requests.Session(impersonate="chrome124")

    def search_pairs(self, query: str) -> List[Dict[str, Any]]:
        """Searches DexScreener for pairs matching a contract or ticker."""
        try:
            url = f"{self.BASE_URL}/latest/dex/search?q={query}"
            res = self.session.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data.get("pairs") or []
        except Exception as e:
            print(f"[!] DexScreener search error for '{query}': {e}")
        return []

    def get_tokens_batch(self, token_addresses: List[str]) -> List[Dict[str, Any]]:
        """Batch fetches full pair info for up to 30 token addresses at once."""
        if not token_addresses:
            return []
        
        all_pairs = []
        # Chunk into slices of 30
        for i in range(0, len(token_addresses), 30):
            chunk = token_addresses[i : i + 30]
            addrs_str = ",".join(chunk)
            url = f"{self.BASE_URL}/latest/dex/tokens/{addrs_str}"
            try:
                res = self.session.get(url, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    pairs = data.get("pairs") or []
                    all_pairs.extend(pairs)
            except Exception as e:
                print(f"[!] DexScreener batch tokens error: {e}")
            time.sleep(0.2)
        return all_pairs

    def extract_socials(self, pair: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts and normalizes Twitter, Telegram, Discord, and Website links."""
        info = pair.get("info") or {}
        socials_list = info.get("socials") or []
        websites_list = info.get("websites") or []

        twitter_url = None
        telegram_url = None
        discord_url = None
        website_url = websites_list[0].get("url") if websites_list else None

        for s in socials_list:
            stype = (s.get("type") or "").lower()
            url = s.get("url") or ""
            if "twitter" in stype or "x.com" in url or "twitter.com" in url:
                if not twitter_url:
                    twitter_url = url
            elif "telegram" in stype or "t.me" in url:
                if not telegram_url:
                    telegram_url = url
            elif "discord" in stype or "discord.gg" in url:
                if not discord_url:
                    discord_url = url

        twitter_handle = None
        if twitter_url:
            clean = twitter_url.strip().rstrip("/").split("?")[0]
            parts = clean.split("/")
            if parts and parts[-1] and parts[-1].lower() not in ["x.com", "twitter.com", "status", "i"]:
                twitter_handle = parts[-1].lstrip("@")

        return {
            "twitter_url": twitter_url,
            "twitter_handle": twitter_handle,
            "telegram_url": telegram_url,
            "discord_url": discord_url,
            "website_url": website_url,
            "has_socials": bool(twitter_url or telegram_url),
        }

    def resolve_asset(self, asset: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Resolves a detected asset against DexScreener to get market data & socials."""
        query = asset["query"]
        pairs = self.search_pairs(query)
        if not pairs:
            return None

        # Filter out dead pairs (with 0 liquidity) if possible
        valid_pairs = [p for p in pairs if (p.get("liquidity") or {}).get("usd", 0) > 0]
        if not valid_pairs:
            valid_pairs = pairs

        # Pick primary pair by highest liquidity
        primary_pair = max(
            valid_pairs,
            key=lambda p: (
                (p.get("liquidity") or {}).get("usd", 0),
                (p.get("volume") or {}).get("h24", 0),
            ),
        )

        base_token = primary_pair.get("baseToken") or {}
        liq = (primary_pair.get("liquidity") or {}).get("usd") or 0
        vol = (primary_pair.get("volume") or {}).get("h24") or 0
        fdv = primary_pair.get("fdv") or primary_pair.get("marketCap") or 0
        socials = self.extract_socials(primary_pair)

        return {
            "query": query,
            "symbol": base_token.get("symbol") or asset.get("symbol") or query,
            "name": base_token.get("name") or query,
            "chain_id": primary_pair.get("chainId"),
            "token_address": base_token.get("address"),
            "pair_address": primary_pair.get("pairAddress"),
            "dex_url": primary_pair.get("url"),
            "price_usd": primary_pair.get("priceUsd"),
            "fdv": fdv,
            "liquidity_usd": liq,
            "volume_24h": vol,
            "price_change_24h": (primary_pair.get("priceChange") or {}).get("h24"),
            "pair_created_at": primary_pair.get("pairCreatedAt"),
            "mentions": asset.get("mentions", 1),
            "total_views": asset.get("total_views", 0),
            "sample_tweet_url": asset.get("sample_tweet_url"),
            "sample_tweet_text": asset.get("sample_tweet_text"),
            **socials,
        }

    def analyze_influencer_dna(self, resolved_assets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates the influencer's asset DNA:
        - Common chains
        - Recommended Market Cap (FDV) range
        - Typical Liquidity and Volume
        """
        if not resolved_assets:
            return {
                "chains": [],
                "recommended_chain": "all",
                "min_fdv": 100_000,
                "max_fdv": 20_000_000,
                "min_liquidity": 30_000,
                "min_volume": 50_000,
            }

        chains_count: Dict[str, int] = {}
        fdv_values = []
        liq_values = []
        vol_values = []

        for a in resolved_assets:
            chain = a.get("chain_id")
            if chain:
                chains_count[chain] = chains_count.get(chain, 0) + 1
            if a.get("fdv") and a["fdv"] > 0:
                fdv_values.append(a["fdv"])
            if a.get("liquidity_usd") and a["liquidity_usd"] > 0:
                liq_values.append(a["liquidity_usd"])
            if a.get("volume_24h") and a["volume_24h"] > 0:
                vol_values.append(a["volume_24h"])

        sorted_chains = sorted(chains_count.items(), key=lambda x: x[1], reverse=True)
        dominant_chain = sorted_chains[0][0] if sorted_chains else "all"

        min_fdv = min(fdv_values) * 0.5 if fdv_values else 100_000
        max_fdv = max(fdv_values) * 1.5 if fdv_values else 20_000_000
        min_liq = min(liq_values) * 0.5 if liq_values else 20_000
        min_vol = min(vol_values) * 0.5 if vol_values else 50_000

        return {
            "chains_distribution": sorted_chains,
            "recommended_chain": dominant_chain,
            "min_fdv": round(max(min_fdv, 10_000)),
            "max_fdv": round(max(max_fdv, 500_000)),
            "min_liquidity": round(max(min_liq, 10_000)),
            "min_volume": round(max(min_vol, 10_000)),
            "sample_assets_count": len(resolved_assets),
        }

    def fetch_active_tokens(self) -> List[Dict[str, Any]]:
        """
        Gathers active & boosted candidate tokens from DexScreener:
        - /token-boosts/top/v1 (tokens paying for advertising/boosts)
        - /token-boosts/latest/v1 (newest boosts)
        - /token-profiles/latest/v1 (newest token profiles)
        - /token-profiles/recent-updates/v1
        """
        candidate_map: Dict[str, Dict[str, Any]] = {}

        endpoints = [
            "/token-boosts/top/v1",
            "/token-boosts/latest/v1",
            "/token-profiles/latest/v1",
            "/token-profiles/recent-updates/v1",
        ]

        for ep in endpoints:
            try:
                res = self.session.get(f"{self.BASE_URL}{ep}", timeout=10)
                if res.status_code == 200:
                    items = res.json()
                    if isinstance(items, list):
                        for item in items:
                            t_addr = item.get("tokenAddress")
                            c_id = item.get("chainId")
                            if t_addr and t_addr not in candidate_map:
                                candidate_map[t_addr] = {
                                    "token_address": t_addr,
                                    "chain_id": c_id,
                                    "dex_url": item.get("url"),
                                    "source": ep,
                                }
            except Exception as e:
                print(f"[!] Error fetching {ep}: {e}")

        candidates = list(candidate_map.values())
        print(f"[*] Fetched {len(candidates)} unique candidate tokens from DexScreener feeds.")
        return candidates

    def find_similar_coins(
        self,
        chain: Optional[str] = None,
        min_fdv: float = 0,
        max_fdv: float = float("inf"),
        min_liquidity: float = 0,
        min_volume: float = 0,
        require_socials: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Scans DexScreener active tokens, batch hydrates pair market metrics,
        and filters by user criteria to find matching coins for dev outreach.
        """
        candidates = self.fetch_active_tokens()
        if not candidates:
            return []

        # If a specific chain is requested, pre-filter by chainId if present
        if chain and chain.lower() != "all":
            filtered_candidates = [
                c for c in candidates if not c.get("chain_id") or c.get("chain_id").lower() == chain.lower()
            ]
        else:
            filtered_candidates = candidates

        addresses = [c["token_address"] for c in filtered_candidates]
        print(f"[*] Hydrating metrics for {len(addresses)} tokens...")

        pairs = self.get_tokens_batch(addresses)
        print(f"[*] Retrieved {len(pairs)} pairs from DexScreener.")

        results: List[Dict[str, Any]] = []
        seen_tokens = set()

        for p in pairs:
            base_token = p.get("baseToken") or {}
            token_addr = base_token.get("address")
            if not token_addr or token_addr in seen_tokens:
                continue

            pair_chain = p.get("chainId")
            if chain and chain.lower() != "all" and pair_chain and pair_chain.lower() != chain.lower():
                continue

            fdv = p.get("fdv") or p.get("marketCap") or 0
            if fdv < min_fdv or fdv > max_fdv:
                continue

            liq = (p.get("liquidity") or {}).get("usd") or 0
            if liq < min_liquidity:
                continue

            vol = (p.get("volume") or {}).get("h24") or 0
            if vol < min_volume:
                continue

            socials = self.extract_socials(p)
            if require_socials and not (socials["twitter_url"] or socials["telegram_url"]):
                continue

            seen_tokens.add(token_addr)
            results.append(
                {
                    "symbol": base_token.get("symbol"),
                    "name": base_token.get("name"),
                    "chain_id": pair_chain,
                    "token_address": token_addr,
                    "pair_address": p.get("pairAddress"),
                    "dex_url": p.get("url"),
                    "price_usd": p.get("priceUsd"),
                    "fdv": fdv,
                    "liquidity_usd": liq,
                    "volume_24h": vol,
                    "price_change_24h": (p.get("priceChange") or {}).get("h24"),
                    "pair_created_at": p.get("pairCreatedAt"),
                    **socials,
                }
            )

        # Sort results by volume and liquidity
        results.sort(key=lambda x: (x["volume_24h"], x["liquidity_usd"]), reverse=True)
        return results[:limit]

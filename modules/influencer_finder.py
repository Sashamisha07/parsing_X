"""
Influencer Finder Module
Discovers similar Twitter (X) crypto influencers, callers, and alpha channels
using a hybrid multi-strategy engine:
1. Dynamic Niche Graph (categorized by niche: 100x callers, Solana degen, Robinhood chain, Base alpha).
2. Live Search Engine Discovery (DuckDuckGo with bot-resilience).
3. Real-time Live Hydration via TwitterCollector (follower counts, bio, active coins).
"""

import re
import time
import math
import urllib.parse
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from curl_cffi import requests
from modules.twitter_collector import TwitterCollector


class InfluencerFinder:
    SYSTEM_HANDLES = {
        "home", "explore", "search", "notifications", "messages", "settings", "i",
        "hashtag", "tos", "privacy", "about", "help", "support", "login", "signup",
        "twitter", "x", "verified_followers", "following", "with_replies", "media",
        "status", "communities"
    }

    # Curated registry of active crypto callers & alpha channels across specific ecosystems
    NICHE_CALLERS = {
        "100x_gems": [
            "EricCryptoman", "nehalzzzz1", "ShotCaller100x", "crypto100xcalls",
            "baron100xcalls", "Crypt_bencall1x", "wulfcryptox", "Crypto100xGems_",
            "Billi976764", "AlphaCryptoGems", "gem_call100x"
        ],
        "solana_meme": [
            "blknoiz06", "MustStopMurad", "toptickcrypto", "ansem", "POW3R_crypto",
            "SolanaFloor", "solbull_", "theunipcs", "RelxBull", "PaidDogeX"
        ],
        "robinhood_chain": [
            "EricCryptoman", "nehalzzzz1", "rutradebtc", "crossrate_hood",
            "DiamondPons_", "deltaliquidity"
        ],
        "base_evm": [
            "Cryptic_Web3", "0xDefiGuru", "TheDeFiInvestor", "rektdiomedes",
            "CryptoGemsCom", "AltcoinGordon"
        ]
    }

    def __init__(self, collector: Optional[TwitterCollector] = None):
        self.collector = collector or TwitterCollector()
        self.session = requests.Session(impersonate="chrome124")
        self._user_cache: Dict[str, Dict[str, Any]] = {}

    def get_candidate_handles_by_niche(self, profile: Dict[str, Any], promoted_coins: List[Dict[str, Any]]) -> List[str]:
        """Selects relevant candidate handles based on the influencer's bio and promoted chains."""
        bio = (profile.get("bio") or "").lower()
        chains = [c.get("chain_id", "").lower() for c in promoted_coins if c.get("chain_id")]

        candidates: List[str] = []

        # 1. Check for 100x / alpha / gems
        if "100x" in bio or "1000x" in bio or "sendor" in bio or "gem" in bio:
            candidates.extend(self.NICHE_CALLERS["100x_gems"])

        # 2. Check chains
        if "solana" in chains:
            candidates.extend(self.NICHE_CALLERS["solana_meme"])
        if "robinhood" in chains:
            candidates.extend(self.NICHE_CALLERS["robinhood_chain"])
        if "base" in chains or "ethereum" in chains:
            candidates.extend(self.NICHE_CALLERS["base_evm"])

        # Default fallback to 100x and solana if no specific match
        if not candidates:
            candidates.extend(self.NICHE_CALLERS["100x_gems"])
            candidates.extend(self.NICHE_CALLERS["solana_meme"])

        return list(dict.fromkeys(candidates))

    def search_candidates_ddg(self, query: str) -> List[str]:
        """Queries DuckDuckGo HTML search with bot challenge resilience."""
        handles = []
        try:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            }
            res = self.session.get(url, headers=headers, timeout=8)
            if res.status_code in [200, 202]:
                soup = BeautifulSoup(res.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    # Check text
                    text = a.get_text().strip()
                    parts = text.split("/")
                    if len(parts) >= 2 and parts[0] in ["x.com", "twitter.com"]:
                        h = parts[1].strip()
                        clean = re.sub(r"[^A-Za-z0-9_]", "", h)
                        if clean and clean.lower() not in self.SYSTEM_HANDLES and len(clean) >= 3:
                            handles.append(clean)

                    # Check uddg parameter
                    href = a["href"]
                    if "uddg=" in href:
                        try:
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                            target = parsed.get("uddg", [""])[0]
                            m = re.search(r"https?://(?:www\.)?(?:twitter|x)\.com/([A-Za-z0-9_]{3,25})(?:/|$|\?)", target)
                            if m:
                                h = m.group(1).strip()
                                if h.lower() not in self.SYSTEM_HANDLES:
                                    handles.append(h)
                        except Exception:
                            pass
        except Exception as e:
            print(f"[!] Live search error for '{query}': {e}")
        return list(dict.fromkeys(handles))

    def calculate_similarity_score(
        self, target_profile: Dict[str, Any], candidate_profile: Dict[str, Any], candidate_assets: List[Any]
    ) -> int:
        """Calculates similarity percentage (25% - 99%)."""
        score = 0

        # 1. Follower tier match
        t_followers = target_profile.get("followers_count") or 1000
        c_followers = candidate_profile.get("followers_count") or 1000
        if t_followers > 0 and c_followers > 0:
            diff_ratio = abs(math.log10(c_followers) - math.log10(t_followers))
            follower_score = max(0, 35 - int(diff_ratio * 20))
            score += follower_score

        # 2. Bio keywords overlap
        c_bio = (candidate_profile.get("bio") or "").lower()
        crypto_terms = ["100x", "gem", "gems", "call", "calls", "alpha", "telegram", "tg", "solana", "og", "sendor", "trader", "shitcoin", "meme", "early"]
        matches = sum(1 for term in crypto_terms if term in c_bio)
        score += min(35, matches * 12)

        # 3. Active crypto assets in recent tweets
        if candidate_assets:
            score += min(30, len(candidate_assets) * 8)

        return min(99, max(30, score))

    def find_similar_influencers(
        self,
        target_profile: Dict[str, Any],
        promoted_coins: List[Dict[str, Any]],
        limit: int = 6
    ) -> List[Dict[str, Any]]:
        """
        Discovers and ranks similar crypto influencers:
        Combines live search + niche registry candidates to guarantee fast, high-quality results.
        """
        target_handle = (target_profile.get("screen_name") or "").lower()

        # Gather candidates: Niche Registry + Live Search
        all_handles: List[str] = []

        # 1. Niche Registry (instant & guaranteed)
        registry_handles = self.get_candidate_handles_by_niche(target_profile, promoted_coins)
        for h in registry_handles:
            if h.lower() != target_handle:
                all_handles.append(h)

        # 2. Live Search (attempt live queries)
        try:
            live_handles = self.search_candidates_ddg("site:x.com crypto 100x calls")
            for h in live_handles:
                if h.lower() != target_handle and h.lower() not in [x.lower() for x in all_handles]:
                    all_handles.append(h)
        except Exception:
            pass

        print(f"[*] Total candidate handles to hydrate: {len(all_handles)}")

        similar_influencers: List[Dict[str, Any]] = []

        # Hydrate candidate profiles in real-time
        for handle in all_handles:
            if handle.lower() == target_handle:
                continue

            # Check local cache first
            if handle.lower() in self._user_cache:
                user_data = self._user_cache[handle.lower()]
            else:
                try:
                    user_data = self.collector.fetch_user_data(handle)
                    self._user_cache[handle.lower()] = user_data
                except Exception as e:
                    print(f"[!] Could not hydrate @{handle}: {e}")
                    continue

            p = user_data.get("profile") or {}
            assets = user_data.get("promoted_assets") or []

            followers = p.get("followers_count") or 0
            if followers < 400:
                continue

            sim_score = self.calculate_similarity_score(target_profile, p, assets)
            coins_mentioned = [a.get("query") for a in assets[:5]]

            similar_influencers.append({
                "name": p.get("name") or handle,
                "screen_name": p.get("screen_name") or handle,
                "url": f"https://x.com/{p.get('screen_name') or handle}",
                "avatar_url": p.get("avatar_url") or "",
                "bio": p.get("bio") or "",
                "followers_count": followers,
                "tweets_count": p.get("tweets_count") or 0,
                "is_blue_verified": p.get("is_blue_verified", False),
                "similarity_score": sim_score,
                "recent_coins": coins_mentioned,
            })

            if len(similar_influencers) >= limit:
                break

        # Sort by similarity score descending, then followers
        similar_influencers.sort(key=lambda x: (x["similarity_score"], x["followers_count"]), reverse=True)
        print(f"[+] Successfully hydrated {len(similar_influencers)} similar influencers!")
        return similar_influencers

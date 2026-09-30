"""
Account Searcher Module
Finds, filters, and ranks X (Twitter) accounts based on thematic keywords,
niches, and categories, hydrates profiles in real-time, and generates custom outreach messages.
"""

import re
import json
from typing import Dict, List, Any, Optional
from modules.twitter_collector import TwitterCollector
from modules.dexscreener_client import DexScreenerClient
from modules.outreach_generator import OutreachGenerator


class AccountSearcher:
    # Extensive, categorized registry of active crypto accounts
    REGISTRY = {
        "crypto_general": {
            "tags": ["крипта", "crypto", "bitcoin", "btc", "eth", "ethereum", "рынок", "маркет", "трейдер", "trader", "аналитика", "technical analysis", "ta"],
            "handles": [
                "Pentosh1", "blknoiz06", "DaanCrypto", "IncomeSharks", "cryptomanran",
                "CredibleCrypto", "DonAlt", "PeterLBrandt", "rutradebtc", "MerlijnTrader",
                "RektProof", "CryptoCobain", "nehalzzzz1", "CryptoCapo_"
            ]
        },
        "alpha_callers": {
            "tags": ["альфа", "alpha", "caller", "коллер", "коллеры", "100x", "gems", "гемы", "lowcap", "calls", "сигналы", "сигнал"],
            "handles": [
                "EricCryptoman", "Crypt_bencall1x", "nehalzzzz1", "ShotCaller100x",
                "crypto100xcalls", "baron100xcalls", "wulfcryptox", "Crypto100xGems_",
                "AlphaCryptoGems", "gem_call100x", "Billi976764", "alphabotcalls"
            ]
        },
        "solana_memes": {
            "tags": ["солана", "solana", "sol", "мем", "meme", "memes", "memecoin", "мемкоины", "pumpfun", "raydium", "degen", "деген"],
            "handles": [
                "blknoiz06", "MustStopMurad", "toptickcrypto", "POW3R_crypto",
                "SolanaFloor", "theunipcs", "solbull_", "RelxBull", "PaidDogeX",
                "Tradermayne"
            ]
        },
        "angels_dealflow": {
            "tags": ["ангел", "angel", "инвестор", "investor", "инвестиции", "vc", "фонд", "deal flow", "дилфлоу", "сделки", "аллокации", "allocations", "seed", "private", "pre-seed"],
            "handles": [
                "balajis", "Arthur_0x", "MechanismCap", "SantiagoAuFund", "punk6529",
                "CMSHoldings", "TheSpartanGroup", "mrjasonchoi", "QwQiao", "hasufl",
                "EricCryptoman"
            ]
        },
        "defi_onchain": {
            "tags": ["дефай", "defi", "ончейн", "onchain", "research", "исследования", "смартмани", "smart money", "whale", "whales", "киты"],
            "handles": [
                "DefiIgnas", "0xFinish", "ThorHartvigsen", "DeFi_Made_Here",
                "TheDeFiInvestor", "rektdiomedes", "CryptoGemsCom", "AltcoinGordon",
                "0xDefiGuru"
            ]
        },
        "airdrop_retro": {
            "tags": ["дроп", "дропы", "airdrop", "airdrops", "ретро", "retro", "тестнет", "testnet", "фарминг", "farming"],
            "handles": [
                "olimpio_crypto", "CC2Ventures", "crypto_linx", "atoms_res",
                "DeFiMinty", "earndrop_io"
            ]
        },
        "cis_ru_community": {
            "tags": ["снг", "cis", "ру", "ru", "russia", "россия", "русский", "крипта снг", "трейдер снг"],
            "handles": [
                "rutradebtc", "0x_gremlin", "mardanov", "invest_incrypto",
                "cryptonews_ru", "tgroup_pro"
            ]
        }
    }

    def __init__(self, collector: Optional[TwitterCollector] = None):
        self.collector = collector or TwitterCollector()
        self.dex = DexScreenerClient()
        self._cache: Dict[str, Dict[str, Any]] = {}

    def normalize_query(self, keyword: str) -> List[str]:
        """Normalizes and expands search keywords (lowercasing, cleaning, synonyms)."""
        clean = keyword.strip().lower()
        terms = [clean]
        
        # Add word splits if multi-word
        for part in re.split(r"[\s,;]+", clean):
            if len(part) >= 2 and part not in terms:
                terms.append(part)

        # Keyword mapping synonyms
        synonyms = {
            "крипта": ["crypto", "bitcoin", "btc", "трейдер", "рынок"],
            "crypto": ["крипта", "bitcoin", "trader", "market"],
            "трейдер": ["trader", "trading", "крипта", "btc"],
            "trader": ["трейдер", "trading", "crypto"],
            "коллер": ["caller", "alpha", "100x", "gems", "альфа"],
            "caller": ["коллер", "alpha", "100x", "gems"],
            "альфа": ["alpha", "caller", "gems", "инсайты"],
            "alpha": ["альфа", "caller", "gems", "calls"],
            "солана": ["solana", "sol", "meme", "pumpfun"],
            "solana": ["солана", "sol", "meme", "memecoin"],
            "ангел": ["angel", "investor", "deal flow", "vc", "инвестор"],
            "angel": ["ангел", "investor", "deal flow", "vc"],
            "инвестор": ["investor", "angel", "deal flow", "фонд"],
            "investor": ["инвестор", "angel", "deal flow", "vc"],
            "дилфлоу": ["deal flow", "angel", "allocations", "сделки"],
            "deal flow": ["дилфлоу", "angel", "allocations", "deals"],
            "дефай": ["defi", "onchain", "ончейн"],
            "defi": ["дефай", "onchain", "research"],
            "дропы": ["airdrop", "retro", "тестнет"],
            "airdrop": ["дропы", "retro", "farming"]
        }

        for k, syn_list in synonyms.items():
            if k in clean:
                for s in syn_list:
                    if s not in terms:
                        terms.append(s)

        return terms

    def search_accounts(
        self,
        keyword: str,
        limit: int = 10,
        min_followers: int = 500
    ) -> List[Dict[str, Any]]:
        """
        Main entry point: finds accounts matching the keyword, hydrates their profiles,
        calculates match score, and generates a personalized outreach message.
        """
        terms = self.normalize_query(keyword)
        matched_handles: List[str] = []

        # 1. Match against Curated Registry
        for category, data in self.REGISTRY.items():
            category_tags = data["tags"]
            is_match = any(
                any(t in tag or tag in t for tag in category_tags)
                for t in terms
            )
            if is_match:
                for h in data["handles"]:
                    if h.lower() not in [x.lower() for x in matched_handles]:
                        matched_handles.append(h)

        # 2. If query mentions a specific coin or ecosystem, query DexScreener for verified socials
        if len(matched_handles) < limit:
            try:
                dex_res = self.dex.search_pairs(keyword)
                for p in dex_res[:5]:
                    tw = p.get("twitter_url")
                    if tw:
                        handle = self.collector.clean_handle(tw)
                        if handle and handle.lower() not in [x.lower() for x in matched_handles]:
                            matched_handles.append(handle)
            except Exception:
                pass

        # Fallback to general crypto if no specific match
        if not matched_handles:
            matched_handles.extend(self.REGISTRY["crypto_general"]["handles"])

        # 3. Hydrate profiles in real-time
        results: List[Dict[str, Any]] = []

        for handle in matched_handles:
            # Check memory cache
            if handle.lower() in self._cache:
                user_data = self._cache[handle.lower()]
            else:
                try:
                    user_data = self.collector.fetch_user_data(handle)
                    self._cache[handle.lower()] = user_data
                except Exception as e:
                    continue

            p = user_data.get("profile") or {}
            followers = p.get("followers_count") or 0

            if followers < min_followers:
                continue

            bio = p.get("bio") or ""
            bio_lower = bio.lower()

            # Calculate match score based on keyword presence in bio / name
            score = 70
            for t in terms:
                if t in bio_lower:
                    score += 10
                if t in (p.get("name") or "").lower():
                    score += 10

            score = min(99, max(50, score))

            # Determine dominant category
            matched_category = "Crypto & Trading"
            if any(w in bio_lower for w in ["angel", "investor", "venture", "vc", "founder"]):
                matched_category = "Angel Investor & VC"
            elif any(w in bio_lower for w in ["caller", "100x", "gem", "alpha", "entry"]):
                matched_category = "Alpha Caller & Gems"
            elif any(w in bio_lower for w in ["solana", "meme", "pump", "raydium"]):
                matched_category = "Solana & Memes"
            elif any(w in bio_lower for w in ["defi", "onchain", "research", "eth"]):
                matched_category = "DeFi & On-Chain"

            # Generate personalized outreach from rutraderbtc
            pitches = self.generate_tailored_pitch(p, matched_category)

            results.append({
                "screen_name": p.get("screen_name") or handle,
                "name": p.get("name") or handle,
                "url": f"https://x.com/{p.get('screen_name') or handle}",
                "avatar_url": p.get("avatar_url") or "",
                "bio": bio,
                "followers_count": followers,
                "tweets_count": p.get("tweets_count") or 0,
                "is_blue_verified": p.get("is_blue_verified", False),
                "category": matched_category,
                "match_score": score,
                "outreach_pitch": pitches["primary"],
                "outreach_pitch_short": pitches["short"],
            })

            if len(results) >= limit:
                break

        # Sort by match score descending, then by followers
        results.sort(key=lambda x: (x["match_score"], x["followers_count"]), reverse=True)
        return results

    def generate_tailored_pitch(self, profile: Dict[str, Any], category: str) -> Dict[str, str]:
        """Generates contextual outreach pitches tailored to the account's niche."""
        name = profile.get("name") or profile.get("screen_name") or "there"
        first_name = name.split()[0] if name else "there"

        if "Angel" in category:
            primary = (
                f"Hey {first_name} — reaching out from rutraderbtc. We actively participate in early-stage rounds "
                f"and strategic allocations. We're setting up a private circle of active angels to cross-share vetted "
                f"deal flow and co-invest. Open to swapping a current deal teaser to see if our flow matches? "
                f"Can share details here or on TG."
            )
            short = (
                f"Yo {first_name}, quick ping from rutraderbtc. We're sitting on early-stage allocations and looking "
                f"to cross-share deal flow with active angels. Down to swap a deal teaser? Drop your TG handle."
            )
        elif "Caller" in category:
            primary = (
                f"Yo {first_name} — respect the calls and early entries. Reaching out from rutraderbtc. "
                f"We track on-chain smart money, stealth dev launches, and early runners before they hit trending. "
                f"Connecting with a few sharp callers to privately cross-share high-conviction plays and dev intros. "
                f"Open to swapping alpha? Ping your TG if you're down."
            )
            short = (
                f"Hey {first_name}, rutraderbtc here. We source early on-chain plays and direct dev-side deal flow. "
                f"Looking to swap alpha and cross-share 10x+ setups with active callers. Down to connect on TG?"
            )
        elif "Solana" in category:
            primary = (
                f"Yo {first_name} — loving the Solana momentum. Reaching out from rutraderbtc (Solana & meme ecosystem focus). "
                f"We source early launches, sniper volume flows, and dev contacts before they pop on DexScreener. "
                f"Looking to cross-share early setups and alpha with active players. Let me know if you're open to connecting on TG."
            )
            short = (
                f"Hey {first_name}, quick one from rutraderbtc. Tracking early SOL ecosystem plays & dev launches. "
                f"Down to privately swap alpha/setups? Ping me your Telegram."
            )
        else:
            primary = (
                f"Hey {first_name} — appreciate your market insights here. Reaching out from rutraderbtc. "
                f"We focus on derivatives flow, liquidity heatmaps, and high-conviction narrative plays. "
                f"Looking to connect with respected traders to cross-share off-market alpha and early deal flow. "
                f"Would you be open to exchanging notes? Happy to connect here or on TG."
            )
            short = (
                f"Hey {first_name}, quick ping from rutraderbtc. We track liquidity flow and off-market alpha. "
                f"Open to privately swapping market notes and deal flow? Let me know or drop your TG."
            )

        return {"primary": primary, "short": short}

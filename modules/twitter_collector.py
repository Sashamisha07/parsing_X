"""
Twitter Collector Module
Parses Twitter (X) influencer profiles and extracts mentioned crypto assets,
cashtags, and contract addresses.
"""

import sys
import re
import json
import base64
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from curl_cffi import requests

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


class TwitterCollector:
    def __init__(self, auth_token: Optional[str] = None, ct0: Optional[str] = None):
        self.auth_token = auth_token
        self.ct0 = ct0
        self.session = requests.Session(impersonate="chrome124")

    def clean_handle(self, username_or_url: str) -> str:
        """Extracts clean screen name from URL or @handle."""
        s = username_or_url.strip()
        s = re.sub(r"^https?://(www\.)?(twitter|x)\.com/", "", s)
        s = s.lstrip("@").split("/")[0].split("?")[0]
        return s

    def fetch_user_data(self, username_or_url: str) -> Dict[str, Any]:
        """
        Fetches public profile data and tweets for the given user.
        """
        screen_name = self.clean_handle(username_or_url)
        url = f"https://x.com/{screen_name}"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }

        response = self.session.get(url, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch profile @{screen_name}: HTTP {response.status_code}")

        return self.parse_ssr_html(response.text, screen_name)

    def parse_ssr_html(self, html: str, screen_name: str) -> Dict[str, Any]:
        """
        Extracts user metadata, tweets, and crypto assets from Relay SSR graph.
        """
        profile: Dict[str, Any] = {
            "screen_name": screen_name,
            "name": screen_name,
            "rest_id": None,
            "followers_count": 0,
            "following_count": 0,
            "tweets_count": 0,
            "bio": "",
            "avatar_url": "",
            "is_blue_verified": False,
        }

        # Rest ID extraction
        id_match = re.search(r'\"user_result_by_screen_name.*?\"VXNlclJlc3VsdHM:([A-Za-z0-9=]+)\"', html)
        if id_match:
            try:
                decoded = base64.b64decode(id_match.group(1)).decode()
                profile["rest_id"] = decoded.replace("UserResults:", "").replace("User:", "")
            except Exception:
                pass
        if not profile["rest_id"]:
            m = re.search(r'rest_id:\"(\d+)\"', html)
            if m:
                profile["rest_id"] = m.group(1)

        # Name
        core_match = re.search(r'screen_name:\"' + re.escape(screen_name) + r'\",name:\"(?P<name>.*?)\"', html)
        if core_match:
            profile["name"] = core_match.group("name")

        # Follower counts
        rel_match = re.search(r'followers:(?P<followers>\d+),following:(?P<following>\d+)', html)
        if rel_match:
            profile["followers_count"] = int(rel_match.group("followers"))
            profile["following_count"] = int(rel_match.group("following"))

        tw_count_match = re.search(r'tweet_counts.*?tweets:(?P<tweets>\d+)', html)
        if tw_count_match:
            profile["tweets_count"] = int(tw_count_match.group("tweets"))

        profile["is_blue_verified"] = "is_blue_verified:!0" in html or "is_blue_verified:true" in html

        avatar_match = re.search(r'image_url:\"(?P<avatar>https://pbs\.twimg\.com/profile_images/[^\"]+)\"', html)
        if avatar_match:
            profile["avatar_url"] = avatar_match.group("avatar")

        desc_match = re.search(r'<meta property="og:description" content="(?P<desc>[^"]*)"', html)
        if desc_match:
            profile["bio"] = desc_match.group("desc")

        pinned_match = re.search(r'component:\"pinned_tweets\",element:\"tweet\".*?tweet-(\d+)', html)
        pinned_id = pinned_match.group(1) if pinned_match else None

        # Tweets
        tweet_ids = set(re.findall(r'TweetResults:(\d+)', html))
        tweets: List[Dict[str, Any]] = []

        for tid in tweet_ids:
            b64_tid = base64.b64encode(f"Tweet:{tid}".encode()).decode()

            # Details
            details_pattern = re.compile(
                rf'client:{re.escape(b64_tid)}:details\"?:\$R\[\d+\]=\{{(?P<details_body>.*?created_at_ms:(?P<time_ms>\d+).*?)\}}',
                re.DOTALL,
            )
            details_match = details_pattern.search(html)
            if not details_match:
                continue

            body = details_match.group("details_body")
            text_match = re.search(r'full_text:\"(?P<text>.*?)\",hashtag_entities', body, re.DOTALL)
            text = ""
            if text_match:
                text = text_match.group("text").replace("\\n", "\n").replace('\\"', '"')

            created_at_ms = int(details_match.group("time_ms"))
            created_at = datetime.fromtimestamp(created_at_ms / 1000.0, timezone.utc)

            # Counts
            counts_pattern = re.compile(
                rf'client:{re.escape(b64_tid)}:counts\"?:\$R\[\d+\]=\{{.*?reply_count:(?P<replies>\d+),retweet_count:(?P<retweets>\d+),favorite_count:(?P<likes>\d+),quote_count:(?P<quotes>\d+),bookmark_count:(?P<bookmarks>\d+)',
                re.DOTALL,
            )
            counts_match = counts_pattern.search(html)
            counts = counts_match.groupdict() if counts_match else {}

            views_pattern = re.compile(
                rf'client:{re.escape(b64_tid)}:views\"?:\$R\[\d+\]=\{{.*?count:\"(?P<views>\d+)\"',
                re.DOTALL,
            )
            views_match = views_pattern.search(html)
            views = int(views_match.group("views")) if views_match else 0

            # Cashtags ($BTC, $DELTA)
            cashtags = list(dict.fromkeys(re.findall(r'\$([A-Za-z0-9_]{2,15})\b', text)))
            cashtags = [c.upper() for c in cashtags if c.upper() not in ["USD", "USDT", "EUR", "RUB", "GM", "GN"]]

            # Contract addresses (EVM and Solana)
            evm_contracts = list(dict.fromkeys(re.findall(r'(0x[a-fA-F0-9]{40})', text)))
            # Solana address pattern (approx 32-44 base58 chars ending with pump or surrounded by spaces/colons)
            sol_contracts = list(dict.fromkeys(re.findall(r'\b([1-9A-HJ-NP-Za-km-z]{32,44}(?:pump)?)\b', text)))
            # Filter out false positive words that happen to look like base58
            sol_contracts = [s for s in sol_contracts if any(c.isdigit() for c in s) and len(s) >= 32 and not s.startswith("http")]

            tweets.append(
                {
                    "id": tid,
                    "url": f"https://x.com/{screen_name}/status/{tid}",
                    "created_at": created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    "created_timestamp": int(created_at_ms / 1000),
                    "is_pinned": (tid == pinned_id),
                    "text": text,
                    "views": views,
                    "likes": int(counts.get("likes", 0)),
                    "retweets": int(counts.get("retweets", 0)),
                    "replies": int(counts.get("replies", 0)),
                    "bookmarks": int(counts.get("bookmarks", 0)),
                    "cashtags": cashtags,
                    "evm_contracts": evm_contracts,
                    "sol_contracts": sol_contracts,
                }
            )

        tweets.sort(key=lambda x: x["created_timestamp"], reverse=True)

        # Aggregate detected crypto assets
        assets_map: Dict[str, Dict[str, Any]] = {}

        for t in tweets:
            # 1. EVM contracts
            for c in t["evm_contracts"]:
                key = c.lower()
                if key not in assets_map:
                    assets_map[key] = {
                        "query": c,
                        "type": "contract_evm",
                        "symbol": None,
                        "mentions": 0,
                        "total_views": 0,
                        "total_likes": 0,
                        "sample_tweet_url": t["url"],
                        "sample_tweet_text": t["text"],
                        "latest_tweet_date": t["created_at"],
                    }
                assets_map[key]["mentions"] += 1
                assets_map[key]["total_views"] += t["views"]
                assets_map[key]["total_likes"] += t["likes"]

            # 2. Solana contracts
            for c in t["sol_contracts"]:
                if c not in assets_map:
                    assets_map[c] = {
                        "query": c,
                        "type": "contract_solana",
                        "symbol": None,
                        "mentions": 0,
                        "total_views": 0,
                        "total_likes": 0,
                        "sample_tweet_url": t["url"],
                        "sample_tweet_text": t["text"],
                        "latest_tweet_date": t["created_at"],
                    }
                assets_map[c]["mentions"] += 1
                assets_map[c]["total_views"] += t["views"]
                assets_map[c]["total_likes"] += t["likes"]

            # 3. Cashtags
            for tag in t["cashtags"]:
                if tag not in assets_map:
                    assets_map[tag] = {
                        "query": tag,
                        "type": "cashtag",
                        "symbol": tag,
                        "mentions": 0,
                        "total_views": 0,
                        "total_likes": 0,
                        "sample_tweet_url": t["url"],
                        "sample_tweet_text": t["text"],
                        "latest_tweet_date": t["created_at"],
                    }
                assets_map[tag]["mentions"] += 1
                assets_map[tag]["total_views"] += t["views"]
                assets_map[tag]["total_likes"] += t["likes"]

        promoted_assets = list(assets_map.values())
        promoted_assets.sort(key=lambda x: (x["type"] != "cashtag", x["mentions"], x["total_views"]), reverse=True)

        return {
            "profile": profile,
            "tweets": tweets,
            "promoted_assets": promoted_assets,
        }

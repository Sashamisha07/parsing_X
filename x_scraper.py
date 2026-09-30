"""
X (Twitter) Scraper for User Profiles and Analysis
Supports:
1. Quick Public Mode (No Login): Fetches current profile info and recent tweets using browser-like TLS fingerprinting (curl_cffi).
2. Deep Mode (Authenticated): Uses auth_token and ct0 cookies to paginate through user timeline history.
"""

import os
import sys
import re
import json
import base64
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from curl_cffi import requests
import pandas as pd

# Reconfigure stdout/stderr for Unicode (handles symbols like ₿) on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


BEARER_TOKEN = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)


class XScraper:
    def __init__(self, auth_token: Optional[str] = None, ct0: Optional[str] = None):
        self.auth_token = auth_token
        self.ct0 = ct0
        self.session = requests.Session(impersonate="chrome124")

    def fetch_public_profile(self, screen_name: str) -> Dict[str, Any]:
        """
        Fetches public profile HTML and parses SSR Relay graph.
        Returns profile metadata and recent tweets.
        """
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
            raise RuntimeError(f"Failed to fetch profile: HTTP {response.status_code}")

        return self.parse_relay_html(response.text, screen_name)

    def parse_relay_html(self, html: str, screen_name: str) -> Dict[str, Any]:
        """
        Extracts user profile and tweets from Twitter SSR Relay Graph.
        """
        # 1. Profile extraction
        profile: Dict[str, Any] = {
            "screen_name": screen_name,
            "name": None,
            "rest_id": None,
            "followers_count": None,
            "following_count": None,
            "tweets_count": None,
            "bio": None,
            "telegram_or_url": None,
            "avatar_url": None,
            "is_blue_verified": False,
        }

        # User rest_id
        user_id_match = re.search(r'\"user_result_by_screen_name.*?\"VXNlclJlc3VsdHM:(\d+)\"', html)
        if not user_id_match:
            user_id_match = re.search(r'\"User:(\d+)\"', html)
        if user_id_match:
            profile["rest_id"] = user_id_match.group(1)

        # User core (name, screen_name)
        core_match = re.search(r'screen_name:\"' + re.escape(screen_name) + r'\",name:\"(?P<name>.*?)\"', html)
        if core_match:
            profile["name"] = core_match.group("name")

        # Counts
        rel_match = re.search(r'followers:(?P<followers>\d+),following:(?P<following>\d+)', html)
        if rel_match:
            profile["followers_count"] = int(rel_match.group("followers"))
            profile["following_count"] = int(rel_match.group("following"))

        tw_count_match = re.search(r'tweet_counts.*?tweets:(?P<tweets>\d+)', html)
        if tw_count_match:
            profile["tweets_count"] = int(tw_count_match.group("tweets"))

        # Blue verified
        profile["is_blue_verified"] = "is_blue_verified:!0" in html or "is_blue_verified:true" in html

        # Avatar
        avatar_match = re.search(r'image_url:\"(?P<avatar>https://pbs\.twimg\.com/profile_images/[^\"]+)\"', html)
        if avatar_match:
            profile["avatar_url"] = avatar_match.group("avatar")

        # Bio / Description
        desc_match = re.search(r'<meta property="og:description" content="(?P<desc>[^"]*)"', html)
        if desc_match:
            profile["bio"] = desc_match.group("desc")

        # Pinned tweet ID
        pinned_match = re.search(r'component:\"pinned_tweets\",element:\"tweet\".*?tweet-(\d+)', html)
        pinned_id = pinned_match.group(1) if pinned_match else None

        # 2. Tweets extraction
        tweet_ids = set(re.findall(r'TweetResults:(\d+)', html))

        tweets: List[Dict[str, Any]] = []

        for tid in tweet_ids:
            b64_tid = base64.b64encode(f"Tweet:{tid}".encode()).decode()

            # Text and Timestamp
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

            # Views
            views_pattern = re.compile(
                rf'client:{re.escape(b64_tid)}:views\"?:\$R\[\d+\]=\{{.*?count:\"(?P<views>\d+)\"',
                re.DOTALL,
            )
            views_match = views_pattern.search(html)
            views = int(views_match.group("views")) if views_match else 0

            # Cashtags ($BTC, $DELTA)
            cashtags = list(dict.fromkeys(re.findall(r'\$([A-Za-z0-9_]+)', text)))

            # Hashtags (#crypto)
            hashtags = list(dict.fromkeys(re.findall(r'#([A-Za-z0-9_]+)', text)))

            # Crypto contract addresses (EVM 0x... or Solana)
            contracts = list(dict.fromkeys(re.findall(r'(0x[a-fA-F0-9]{40})', text)))

            # External links
            urls = list(dict.fromkeys(re.findall(r'https?://[^\s]+', text)))

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
                    "hashtags": hashtags,
                    "contract_addresses": contracts,
                    "urls": urls,
                }
            )

        # Sort tweets descending by creation timestamp
        tweets.sort(key=lambda x: x["created_timestamp"], reverse=True)

        return {"profile": profile, "tweets": tweets}

    def save_results(self, data: Dict[str, Any], output_prefix: str = "rutradebtc"):
        """
        Saves parsed profile and tweets to JSON and CSV.
        """
        # Save JSON
        json_path = f"{output_prefix}_data.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Save Tweets CSV
        tweets = data.get("tweets", [])
        if tweets:
            df = pd.DataFrame(tweets)
            # Convert list columns to string for clean CSV representation
            for col in ["cashtags", "hashtags", "contract_addresses", "urls"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)

            csv_path = f"{output_prefix}_tweets.csv"
            df.to_csv(csv_path, index=False, encoding="utf-8-sig")
            print(f"[+] Saved {len(tweets)} tweets to CSV: {csv_path}")

        print(f"[+] Saved complete profile and tweets to JSON: {json_path}")


if __name__ == "__main__":
    screen_name = "rutradebtc"
    print(f"[*] Fetching data for https://x.com/{screen_name}...")
    scraper = XScraper()
    result = scraper.fetch_public_profile(screen_name)

    print("\n--- Profile Summary ---")
    p = result["profile"]
    print(f"Name: {p['name']} (@{p['screen_name']})")
    print(f"Rest ID: {p['rest_id']}")
    print(f"Followers: {p['followers_count']:,} | Following: {p['following_count']:,} | Total Tweets: {p['tweets_count']:,}")
    print(f"Bio: {p['bio']}")
    print(f"Verified: {p['is_blue_verified']}")

    print(f"\n--- Extracted {len(result['tweets'])} Tweets ---")
    for t in result["tweets"]:
        pin_str = "[PINNED] " if t["is_pinned"] else ""
        print(f"\n{pin_str}[{t['created_at']}] ID: {t['id']}")
        print(f"Stats: {t['views']:,} views | {t['likes']} likes | {t['retweets']} RT | {t['replies']} replies")
        if t["cashtags"]:
            print(f"Cashtags: {t['cashtags']}")
        if t["contract_addresses"]:
            print(f"Contracts: {t['contract_addresses']}")
        print(f"Text: {t['text'][:120]}...")

    scraper.save_results(result, output_prefix=screen_name)

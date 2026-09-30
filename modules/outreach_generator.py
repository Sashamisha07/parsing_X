"""
Outreach Message Generator Module
Generates high-converting, personalized outreach messages and pitches
tailored to crypto Twitter influencers (callers) and project developers.
"""

from typing import Dict, Any, Optional


class OutreachGenerator:

    @staticmethod
    def clean_tweet_snippet(text: Optional[str], max_len: int = 100) -> str:
        if not text:
            return ""
        clean = " ".join(text.split()).replace('"', "'")
        if len(clean) > max_len:
            clean = clean[:max_len] + "..."
        return clean

    @classmethod
    def generate_pitches_for_influencer(
        cls,
        influencer_profile: Dict[str, Any],
        coin_data: Optional[Dict[str, Any]] = None,
        custom_tweet_text: Optional[str] = None,
        my_project_name: str = "[Your Project Name]",
        my_chain: str = "Solana",
    ) -> Dict[str, str]:
        """
        Generates outreach messages addressing the influencer/caller:
        Asking for paid call / Telegram shoutout / alpha review based on their exact recent posts.
        """
        name = influencer_profile.get("name") or influencer_profile.get("screen_name")
        handle = influencer_profile.get("screen_name")
        coin_symbol = (coin_data.get("symbol") or "crypto") if coin_data else "early gems"
        chain = (coin_data.get("chain_id") or my_chain).capitalize() if coin_data else my_chain

        raw_tweet = custom_tweet_text or (coin_data.get("sample_tweet_text") if coin_data else "")
        tweet_quote = cls.clean_tweet_snippet(raw_tweet, 80)
        en_quote_part = f' (loved your tweet: "{tweet_quote}")' if tweet_quote else ""
        ru_quote_part = f' (очень зашел твой твит: "{tweet_quote}")' if tweet_quote else ""

        # 1. English - Direct Sponsored Call / Telegram Pitch
        en_call_pitch = (
            f"Hey {name} (@{handle})! 🔥\n\n"
            f"Been following your calls on ${coin_symbol}{en_quote_part}. Your community momentum is insane.\n\n"
            f"We are launching {my_project_name} on {chain} with locked liquidity and an active marketing budget. "
            f"We are booking sponsored Twitter threads and Telegram calls with top alpha leaders this week.\n\n"
            f"Could you send over your current promo rates / deck or your Telegram handle to discuss details?\n\n"
            f"Best regards,\nTeam {my_project_name}"
        )

        # 2. English - Alpha Share & Early Partner Inquiry
        en_alpha_pitch = (
            f"Hey @{handle}, quick question!\n\n"
            f"Saw your recent breakdown on ${coin_symbol}{en_quote_part}. We are deploying {my_project_name} on {chain} "
            f"with similar microcap tokenomics and organic backing.\n\n"
            f"Would love to send you our deck & early alpha access before our public marketing wave kicks in. "
            f"Mind if I drop the DexScreener link and contract address here?\n\n"
            f"Cheers!"
        )

        # 3. Russian - Питч для русскоязычных коллеров
        ru_pitch = (
            f"Привет, {name} (@{handle})! 🤝\n\n"
            f"Слежу за твоими коллами по ${coin_symbol}{ru_quote_part} — отличные сетапы и сильная реакция комьюнити.\n\n"
            f"Мы сейчас запускаем {my_project_name} на сети {chain} с залоченной ликвидностью и выделенным маркетинговым бюджетом. "
            f"Планируем закупку платных постов / коллов в твой Telegram-канал и Twitter.\n\n"
            f"Подскажи, пожалуйста, актуальный прайс на размещение и твой контакт в Telegram для быстрой связи?\n\n"
            f"Спасибо!"
        )

        return {
            "en_sponsored_call": en_call_pitch,
            "en_alpha_share": en_alpha_pitch,
            "ru_collab_pitch": ru_pitch,
        }

    @classmethod
    def generate_pitches_for_dev(
        cls,
        candidate_project: Dict[str, Any],
        influencer_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        """
        Generates outreach messages addressing developers of similar projects:
        Offering KOL marketing, influencer connections, or partnership based on the influencer's traction.
        """
        symbol = candidate_project.get("symbol") or "TOKEN"
        project_name = candidate_project.get("name") or symbol
        chain = (candidate_project.get("chain_id") or "").capitalize()
        fdv = f"${candidate_project.get('fdv', 0):,.0f}" if candidate_project.get("fdv") else "current cap"
        volume = f"${candidate_project.get('volume_24h', 0):,.0f}" if candidate_project.get("volume_24h") else ""

        inf_name = influencer_profile.get("name") if influencer_profile else "top alpha leaders"
        inf_handle = f"@{influencer_profile.get('screen_name')}" if influencer_profile else "@alpha_callers"
        inf_followers = f"({influencer_profile.get('followers_count', 0):,} followers)" if influencer_profile else ""

        # 1. English - KOL Marketing & Shilling Offer
        en_marketing_pitch = (
            f"Hey {project_name} (@{candidate_project.get('twitter_handle') or symbol}) team! 🚀\n\n"
            f"Awesome traction on DexScreener! Saw ${symbol} running on {chain} ({fdv} FDV{f' / {volume} 24h vol' if volume else ''}).\n\n"
            f"We work directly with prominent crypto callers like {inf_handle} {inf_followers} who recently sent similar plays for multi-x runs. "
            f"Are you guys currently looking to scale your marketing and onboard high-tier KOLs / call channels for ${symbol}?\n\n"
            f"Would love to connect on Telegram to share our roster and case studies. What's the best TG handle for your dev/marketing lead?\n\n"
            f"Best,"
        )

        # 2. Russian - Предложение продвижения для девов
        ru_marketing_pitch = (
            f"Привет, команда ${symbol}! 👋\n\n"
            f"Отличная динамика на DexScreener (капа {fdv}, сеть {chain}).\n\n"
            f"Мы сотрудничаем с проверенными крипто-коллерами и инфлюенсерами уровня {inf_handle} {inf_followers}, "
            f"которые специализируются именно на таких проектах и дают реальный торговый объем.\n\n"
            f"Планируете ли вы сейчас подключать закупку трафика и новые Telegram/Twitter коллы для ${symbol}? "
            f"С кем из вашей команды можно обсудить детали в Telegram?\n\n"
            f"Удачных торгов!"
        )

        return {
            "en_dev_marketing": en_marketing_pitch,
            "ru_dev_marketing": ru_marketing_pitch,
        }

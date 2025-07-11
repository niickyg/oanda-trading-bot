"""
data/news.py

Twitter-based news fetching and sentiment interpretation for Forex pairs.
Provides helpers to fetch recent tweets and derive BUY/SELL signals based
on keyword sentiment mapping to instrument codes.
"""

import os
import requests
from typing import List, Dict

__all__ = [
    "get_recent_tweets",
    "fetch_forex_news_from_twitter",
    "interpret_news_signals",
]

# ---------------------------------------------------------------------------
# Twitter news helper (v2 Recent Search)
# ---------------------------------------------------------------------------

BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

def get_recent_tweets(query: str, max_results: int = 10) -> List[Dict]:
    """
    Fetch recent tweets matching the query using Twitter API v2.
    Requires environment variable TWITTER_BEARER_TOKEN to be set.
    Returns a list of tweet dicts with 'text' and 'created_at'.
    """
    if not BEARER_TOKEN:
        raise EnvironmentError("TWITTER_BEARER_TOKEN not set")

    url = "https://api.twitter.com/2/tweets/search/recent"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    params = {
        "query": query,
        "max_results": max_results,
        "tweet.fields": "created_at,text,author_id"
    }
    resp = requests.get(url, headers=headers, params=params, timeout=10)
    resp.raise_for_status()
    json_resp = resp.json()
    return json_resp.get("data", [])

def fetch_forex_news_from_twitter(max_results: int = 5) -> List[Dict]:
    """
    Shortcut to fetch the top recent tweets mentioning major Forex keywords.
    """
    keywords = "forex OR EURUSD OR USDJPY OR GBPUSD OR trading"
    return get_recent_tweets(query=keywords, max_results=max_results)


# ---------------------------------------------------------------------------
# News-based trade signals
# ---------------------------------------------------------------------------

# Map keyword substrings to OANDA instrument codes
_PAIR_KEYWORDS = {
    "eurusd": "EUR_USD",
    "gbpusd": "GBP_USD",
    "usdjpy": "USD_JPY",
    "usdchf": "USD_CHF",
    "audusd": "AUD_USD",
    "nzdusd": "NZD_USD",
    "gbpjpy": "GBP_JPY",
    "eurjpy": "EUR_JPY",
}

# Simple sentiment keywords
_BUY_KEYWORDS = {"buy", "long", "rally", "bullish", "trend up"}
_SELL_KEYWORDS = {"sell", "short", "drop", "bearish", "trend down"}

def interpret_news_signals(tweets: List[Dict]) -> Dict[str, str]:
    """
    Analyze recent tweets and generate BUY/SELL signals per instrument.
    Returns a dict mapping instrument codes to "BUY" or "SELL".
    """
    signals: Dict[str, str] = {}
    for tweet in tweets:
        text = tweet.get("text", "").lower()
        for key, instr in _PAIR_KEYWORDS.items():
            if key in text:
                if any(bk in text for bk in _BUY_KEYWORDS):
                    signals[instr] = "BUY"
                elif any(sk in text for sk in _SELL_KEYWORDS):
                    signals[instr] = "SELL"
    return signals
"""
SCRAPER - Gaming Content Bot
=============================
Extrae noticias de videojuegos de:
  - RSS feeds (news sites)
  - Steam API

Uso:
  python scraper.py es         → español
  python scraper.py en         → inglés
"""

import os
import json
import feedparser
import requests
from pathlib import Path
from datetime import datetime
from sources_config import TOP_GAMES, RSS_FEEDS

BASE_DIR = Path(__file__).parent.parent
NEWS_DIR = BASE_DIR / "data" / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)

STEAM_NEWS_URL = "https://api.steampowered.com/ISteamNews/GetNewsForApp/v0002"


def fetch_rss_news(language: str = "es") -> list:
    """Extrae noticias de RSS feeds."""
    news = []
    feeds = RSS_FEEDS.get(language, [])

    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:3]:  # Top 3 entries por feed
                news.append({
                    "title": entry.get("title", ""),
                    "description": entry.get("summary", "")[:200],
                    "link": entry.get("link", ""),
                    "source": "rss",
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"[!] Error en feed {feed_url}: {e}")

    return news


def fetch_steam_news(language: str = "es") -> list:
    """Extrae noticias de Steam API."""
    news = []
    games = TOP_GAMES.get(language, [])
    steam_key = os.getenv("STEAM_API_KEY")

    if not steam_key:
        return news

    for game in games:
        app_id = game["app_id"]
        game_name = game["name"]

        try:
            res = requests.get(
                STEAM_NEWS_URL,
                params={"appid": app_id, "count": 3, "maxlength": 300},
                timeout=5
            )
            data = res.json()

            for item in data.get("appnews", {}).get("newsitems", []):
                news.append({
                    "title": item.get("title", ""),
                    "description": item.get("contents", "")[:200],
                    "link": item.get("url", ""),
                    "source": "steam",
                    "game": game_name,
                    "published": datetime.fromtimestamp(item.get("date", 0)).isoformat(),
                })
        except Exception as e:
            print(f"[!] Error en Steam {game_name}: {e}")

    return news


def run_scraper(language: str = "es") -> list:
    """Ejecuta el scraper para el idioma especificado."""
    all_news = []

    print(f"[*] Scrapeando noticias ({language})...")

    # RSS feeds
    rss_news = fetch_rss_news(language)
    all_news.extend(rss_news)
    print(f"    └─ RSS: {len(rss_news)} noticias")

    # Steam API
    steam_news = fetch_steam_news(language)
    all_news.extend(steam_news)
    print(f"    └─ Steam: {len(steam_news)} noticias")

    if not all_news:
        return []

    # Guardar a archivo JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = NEWS_DIR / f"news_{language}_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "language": language,
            "scraped_at": datetime.now().isoformat(),
            "total": len(all_news),
            "news": all_news
        }, f, ensure_ascii=False, indent=2)

    print(f"[✓] {len(all_news)} noticias guardadas en {filename.name}")
    return all_news


if __name__ == "__main__":
    import sys
    lang = sys.argv[1] if len(sys.argv) > 1 else "es"
    news = run_scraper(language=lang)

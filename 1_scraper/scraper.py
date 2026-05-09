"""
SCRAPER - Gaming Content Bot
=============================
Extrae noticias de videojuegos de:
  - RSS feeds (news sites)
  - Reddit
  - Steam API

Uso:
  python scraper.py es         → español
  python scraper.py en         → inglés
"""

from sources_config import TOP_GAMES, RSS_FEEDS


def run_scraper(language: str = "es") -> list:
    """Ejecuta el scraper para el idioma especificado."""
    # TODO: Implementar scraping
    pass


if __name__ == "__main__":
    import sys
    lang = sys.argv[1] if len(sys.argv) > 1 else "es"
    news = run_scraper(language=lang)

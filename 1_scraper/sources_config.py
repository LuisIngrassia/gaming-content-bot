"""
Configuración de fuentes para el scraper.
Edita TOP_GAMES y RSS_FEEDS según tus necesidades.
"""

# Steam AppIDs de los juegos principales
# Busca más en: https://steamdb.info
TOP_GAMES = {
    "es": [
        {"name": "Counter-Strike 2", "app_id": 730},
        {"name": "DOTA 2", "app_id": 570},
        {"name": "Baldur's Gate 3", "app_id": 1238140},
        {"name": "Elden Ring", "app_id": 1245620},
    ],
    "en": [
        {"name": "Counter-Strike 2", "app_id": 730},
        {"name": "DOTA 2", "app_id": 570},
        {"name": "Baldur's Gate 3", "app_id": 1238140},
        {"name": "Elden Ring", "app_id": 1245620},
    ],
}

# RSS feeds de noticias de videojuegos
RSS_FEEDS = {
    "es": [
        "https://www.gamesindustry.biz/es/feed",
        "https://www.vandal.net/feeds.xml",
    ],
    "en": [
        "https://www.gamesindustry.biz/en/feed",
        "https://www.polygon.com/rss/index.xml",
    ],
}

# Subreddits a monitorear
SUBREDDITS = {
    "es": ["gaming", "es_gaming"],
    "en": ["gaming", "pcgaming"],
}

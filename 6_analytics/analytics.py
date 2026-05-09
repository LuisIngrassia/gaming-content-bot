"""
ANALYTICS - Gaming Content Bot
================================
Recolecta métricas de YouTube, TikTok e Instagram
y las guarda en SQLite local para análisis.
"""

import json
import os
import sqlite3
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv(Path(__file__).parent.parent / ".env")
console = Console()

BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / "data" / "analytics.db"


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.executescript("""
        CREATE TABLE IF NOT EXISTS videos (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            script_file   TEXT UNIQUE,
            title         TEXT,
            game          TEXT,
            language      TEXT,
            content_type  TEXT,
            published_at  TEXT,
            yt_id         TEXT,
            tt_id         TEXT,
            ig_id         TEXT
        );
        CREATE TABLE IF NOT EXISTS metrics (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id    INTEGER REFERENCES videos(id),
            platform    TEXT,
            checked_at  TEXT,
            views       INTEGER DEFAULT 0,
            likes       INTEGER DEFAULT 0,
            comments    INTEGER DEFAULT 0,
            shares      INTEGER DEFAULT 0
        );
    """)
    con.commit()
    return con


def register_video(con, script_data: dict, script_file: str):
    results = script_data.get("publish_results", {})
    yt = (results.get("youtube") or {}).get("id")
    tt = (results.get("tiktok")  or {}).get("publish_id")
    ig = (results.get("instagram") or {}).get("media_id")
    try:
        con.execute("""
            INSERT OR IGNORE INTO videos
            (script_file, title, game, language, content_type, published_at, yt_id, tt_id, ig_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            script_file,
            script_data.get("title"),
            script_data.get("game_mentioned"),
            script_data.get("language"),
            script_data.get("content_type"),
            script_data.get("published_at"),
            yt, tt, ig,
        ))
        con.commit()
    except Exception as e:
        console.print(f"[red]DB error: {e}")


def fetch_youtube_metrics(video_id: str) -> dict:
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key or not video_id:
        return {}
    try:
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/videos",
            params={"part": "statistics", "id": video_id, "key": api_key},
            timeout=10,
        )
        items = res.json().get("items", [])
        if not items:
            return {}
        s = items[0].get("statistics", {})
        return {"views": int(s.get("viewCount",0)), "likes": int(s.get("likeCount",0)), "comments": int(s.get("commentCount",0))}
    except:
        return {}


def fetch_tiktok_metrics(publish_id: str) -> dict:
    token = os.getenv("TIKTOK_ACCESS_TOKEN")
    if not token or not publish_id:
        return {}
    try:
        res = requests.get(
            "https://open.tiktokapis.com/v2/video/query/",
            headers={"Authorization": f"Bearer {token}"},
            params={"fields": "view_count,like_count,comment_count,share_count",
                    "filters": json.dumps({"video_ids": [publish_id]})},
            timeout=10,
        )
        data = res.json().get("data", {}).get("videos", [])
        if not data:
            return {}
        v = data[0]
        return {"views": v.get("view_count",0), "likes": v.get("like_count",0),
                "comments": v.get("comment_count",0), "shares": v.get("share_count",0)}
    except:
        return {}


def fetch_instagram_metrics(media_id: str) -> dict:
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not token or not media_id:
        return {}
    try:
        res = requests.get(
            f"https://graph.facebook.com/v18.0/{media_id}/insights",
            params={"metric": "plays,likes,comments,shares", "access_token": token},
            timeout=10,
        )
        data = res.json().get("data", [])
        m = {d["name"]: d["values"][0]["value"] for d in data if d.get("values")}
        return {"views": m.get("plays",0), "likes": m.get("likes",0),
                "comments": m.get("comments",0), "shares": m.get("shares",0)}
    except:
        return {}


def collect_metrics():
    con = init_db()

    # Registrar videos nuevos
    scripts_dir = BASE_DIR / "data" / "processed"
    for f in scripts_dir.glob("script_*.json"):
        with open(f) as fp:
            data = json.load(fp)
        if data.get("published_at"):
            register_video(con, data, str(f))

    rows = con.execute("""
        SELECT id, title, yt_id, tt_id, ig_id FROM videos
        WHERE published_at < datetime('now', '-1 hour')
        ORDER BY published_at DESC LIMIT 50
    """).fetchall()

    if not rows:
        console.print("[yellow]Sin videos para chequear.")
        con.close()
        return

    console.rule(f"[bold cyan]Recolectando métricas — {len(rows)} videos")
    now = datetime.now().isoformat()

    for video_id, title, yt_id, tt_id, ig_id in rows:
        console.print(f"[dim]{title[:50]}")
        for platform, pid, fetch_fn in [
            ("youtube",   yt_id, fetch_youtube_metrics),
            ("tiktok",    tt_id, fetch_tiktok_metrics),
            ("instagram", ig_id, fetch_instagram_metrics),
        ]:
            if not pid:
                continue
            m = fetch_fn(pid)
            if m:
                con.execute(
                    "INSERT INTO metrics (video_id, platform, checked_at, views, likes, comments, shares) VALUES (?,?,?,?,?,?,?)",
                    (video_id, platform, now, m.get("views",0), m.get("likes",0), m.get("comments",0), m.get("shares",0))
                )

    con.commit()
    con.close()
    console.print("[green]Métricas guardadas.")


def get_top_performers(days: int = 7) -> list:
    con = init_db()
    rows = con.execute("""
        SELECT v.title, v.game, v.language, v.content_type,
               SUM(m.views) as total_views, SUM(m.likes) as total_likes
        FROM metrics m JOIN videos v ON m.video_id = v.id
        WHERE m.checked_at > datetime('now', ?)
        GROUP BY v.id ORDER BY total_views DESC LIMIT 10
    """, (f"-{days} days",)).fetchall()
    con.close()
    return rows


def show_dashboard():
    top = get_top_performers(7)
    if not top:
        console.print("[yellow]Sin métricas aún.")
        return
    table = Table(title="Top videos — últimos 7 días")
    table.add_column("Título", max_width=35)
    table.add_column("Juego", style="cyan")
    table.add_column("Lang", width=4)
    table.add_column("Tipo", style="magenta")
    table.add_column("Views", style="green", justify="right")
    table.add_column("Likes", style="yellow", justify="right")
    for row in top:
        title, game, lang, ctype, views, likes = row
        table.add_row((title or "")[:35], (game or "")[:15], lang or "",
                      (ctype or "").replace("_"," "), f"{views:,}", f"{likes:,}")
    console.print(table)


if __name__ == "__main__":
    import sys
    if "--dashboard" in sys.argv:
        show_dashboard()
    else:
        collect_metrics()
        show_dashboard()
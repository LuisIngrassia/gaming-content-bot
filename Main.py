"""
ORQUESTADOR - Gaming Content Bot
==================================
Une todos los módulos en un pipeline completo.

Pipeline:
  1. Scraper    → noticias nuevas
  2. Guiones    → Groq/Ollama
  3. Audio      → Kokoro TTS
  4. Video      → FFmpeg + Whisper
  5. Publicar   → YouTube + TikTok + Instagram
  6. Analytics  → métricas en SQLite

Uso:
  python main.py                          → pipeline completo ahora
  python main.py --lang es               → solo español
  python main.py --platforms youtube     → solo YouTube
  python main.py --schedule              → corre automatico segun horario
  python main.py --analytics             → ver dashboard

Cron del sistema (recomendado):
  0 9,21 * * * cd /ruta/bot && python main.py >> logs/cron.log 2>&1
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()
BASE_DIR = Path(__file__).parent

sys.path.insert(0, str(BASE_DIR / "1_scraper"))
sys.path.insert(0, str(BASE_DIR / "2_script"))
sys.path.insert(0, str(BASE_DIR / "3_audio"))
sys.path.insert(0, str(BASE_DIR / "4_video"))
sys.path.insert(0, str(BASE_DIR / "5_publish"))
sys.path.insert(0, str(BASE_DIR / "6_analytics"))


CONFIG = {
    "languages":      ["es", "en"],
    "platforms":      ["youtube", "tiktok", "instagram"],
    "schedule_times": ["09:00", "21:00"],
    "analytics_time": "08:00",
}


def run_pipeline(languages=None, platforms=None):
    from scraper          import run_scraper
    from script_generator import process_news_batch
    from audio_generator  import process_scripts_batch as gen_audio
    from video_generator  import process_batch as gen_video
    from publisher        import process_batch as publish_all

    if languages is None: languages = CONFIG["languages"]
    if platforms is None: platforms = CONFIG["platforms"]

    start = datetime.now()
    console.rule(f"[bold cyan]Gaming Content Bot — {start.strftime('%d/%m %H:%M')}")

    results = {"scraper": 0, "scripts": 0, "audio": 0, "video": 0, "published": 0, "errors": []}

    # 1. Scraping
    console.rule("[cyan]1/5 Scraping")
    news_dir = BASE_DIR / "data" / "news"
    for lang in languages:
        try:
            news = run_scraper(language=lang)
            results["scraper"] += len(news)
        except Exception as e:
            results["errors"].append(f"scraper_{lang}: {e}")

    if not results["scraper"]:
        console.print("[yellow]Sin noticias nuevas.")
        return results

    # 2. Guiones
    console.rule("[cyan]2/5 Guiones")
    try:
        files = sorted(news_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        for nf in files[:4]:
            batch = process_news_batch(nf, languages=languages)
            results["scripts"] += len(batch)
    except Exception as e:
        results["errors"].append(f"scripts: {e}")

    # 3. Audio
    console.rule("[cyan]3/5 Audio")
    try:
        results["audio"] = len(gen_audio())
    except Exception as e:
        results["errors"].append(f"audio: {e}")

    # 4. Video
    console.rule("[cyan]4/5 Video")
    try:
        results["video"] = len(gen_video())
    except Exception as e:
        results["errors"].append(f"video: {e}")

    # 5. Publicar
    console.rule("[cyan]5/5 Publicando")
    try:
        results["published"] = len(publish_all(platforms=platforms))
    except Exception as e:
        results["errors"].append(f"publish: {e}")

    # Resumen
    duration = (datetime.now() - start).seconds
    console.rule("[bold green]Pipeline completado")
    console.print(
        f"  Noticias: {results['scraper']} | "
        f"Guiones: {results['scripts']} | "
        f"Audio: {results['audio']} | "
        f"Video: {results['video']} | "
        f"Publicados: {results['published']} | "
        f"Tiempo: {duration//60}m {duration%60}s"
    )
    if results["errors"]:
        for e in results["errors"]:
            console.print(f"  [red]• {e}")

    # Log
    log_file = BASE_DIR / "logs" / "pipeline.jsonl"
    log_file.parent.mkdir(exist_ok=True)
    with open(log_file, "a") as f:
        f.write(json.dumps({"run_at": start.isoformat(), "duration_seconds": duration, **results}) + "\n")

    return results


def run_analytics():
    from analytics import collect_metrics, show_dashboard
    console.rule("[bold cyan]Analytics")
    collect_metrics()
    show_dashboard()


def start_scheduler():
    import schedule

    console.print("[bold green]Bot iniciado — modo scheduler")
    console.print(f"[dim]Horarios: {CONFIG['schedule_times']} | Ctrl+C para detener")

    for t in CONFIG["schedule_times"]:
        schedule.every().day.at(t).do(run_pipeline)

    schedule.every().day.at(CONFIG["analytics_time"]).do(run_analytics)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--schedule" in args:
        start_scheduler()
    elif "--analytics" in args:
        run_analytics()
    else:
        lang_i = args.index("--lang") + 1 if "--lang" in args else None
        languages = [args[lang_i]] if lang_i else CONFIG["languages"]

        plat_i = args.index("--platforms") + 1 if "--platforms" in args else None
        platforms = [a for a in args[plat_i:] if not a.startswith("--")] if plat_i else CONFIG["platforms"]

        run_pipeline(languages=languages, platforms=platforms)
"""
GENERADOR DE GUIONES - Gaming Content Bot
==========================================
Principal: Groq API (gratis, Llama 3.1 70B)
Fallback:  Ollama local (Llama 3.1 8B)

1 sola llamada por guión.
"""

import json
import os
import requests
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

load_dotenv(Path(__file__).parent.parent / ".env")
console = Console()

DATA_DIR = Path(__file__).parent.parent / "data" / "processed"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GROQ_API_URL   = "https://api.groq.com/openai/v1/chat/completions"
OLLAMA_API_URL = "http://localhost:11434/api/chat"
# Modelos disponibles en Groq (llama-3.1-70b-versatile fue descontinuado)
GROQ_MODEL     = "mixtral-8x7b-32768"  # Rápido y confiable
OLLAMA_MODEL   = "llama3.1:8b"


# ============================================
# PROMPTS
# ============================================

SYSTEM_PROMPT = """Sos un guionista experto en contenido viral de videojuegos para TikTok, Instagram Reels y YouTube Shorts.

REGLAS:
- Duración objetivo: 45-60 segundos leído en voz alta
- Frases cortas, máximo 15 palabras por frase
- Hook en los primeros 3 segundos
- Sin saludos, arrancá directo con el hook
- Sin emojis en el guión (van solo en la descripción)
- Lenguaje natural, como hablarle a un amigo gamer
- Terminar con CTA (like, seguir, comentar)

Devolvé ÚNICAMENTE este JSON sin markdown ni explicaciones:
{
  "hook": "primera frase, máximo 10 palabras",
  "script": "guión completo corrido, sin saltos de línea",
  "title": "título del video, máximo 8 palabras",
  "description": "descripción con emojis y hashtags",
  "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
  "content_type": "patch_note | new_game | update | rumor",
  "game_mentioned": "nombre del juego o 'general'",
  "estimated_duration_seconds": 50
}"""

USER_PROMPT_TEMPLATE = """Creá un guión en {language} para este contenido de videojuegos:

TÍTULO: {title}
RESUMEN: {summary}
FUENTE: {source}
TIPO: {content_type}

JSON puro, sin texto extra."""


# ============================================
# DETECTOR DE TIPO
# ============================================

def detect_content_type(news: dict) -> str:
    text = (news.get("title", "") + " " + news.get("description", "")).lower()
    if any(w in text for w in ["patch", "hotfix", "parche", "balance", "nerf", "buff"]):
        return "patch_note"
    if any(w in text for w in ["announced", "reveal", "anunciado", "new game", "nuevo juego", "release date"]):
        return "new_game"
    if any(w in text for w in ["rumor", "leak", "filtracion"]):
        return "rumor"
    return "update"


# ============================================
# GROQ (principal)
# ============================================

def call_groq(system: str, user: str) -> str | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        console.print("[yellow]GROQ_API_KEY no configurada, usando Ollama...")
        return None

    try:
        res = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "max_tokens": 800,
                "temperature": 0.7,
            },
            timeout=30,
        )
        res.raise_for_status()
        return res.json()["choices"][0]["message"]["content"].strip()

    except requests.exceptions.HTTPError as e:
        if res.status_code == 429:
            console.print("[yellow]Groq rate limit alcanzado, usando Ollama...")
        else:
            console.print(f"[red]Groq error {res.status_code}: {res.text[:200]}")
        return None
    except Exception as e:
        console.print(f"[red]Groq error: {e}")
        return None


# ============================================
# OLLAMA (fallback local)
# ============================================

def call_ollama(system: str, user: str) -> str | None:
    try:
        res = requests.post(
            OLLAMA_API_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 800},
            },
            timeout=120,
        )
        res.raise_for_status()
        return res.json()["message"]["content"].strip()

    except requests.exceptions.ConnectionError:
        console.print("[red]Ollama no esta corriendo. Inicialo con: ollama serve")
        return None
    except Exception as e:
        console.print(f"[red]Ollama error: {e}")
        return None


# ============================================
# GENERADOR PRINCIPAL
# ============================================

def generate_script(news: dict, language: str = "es") -> dict | None:
    content_type = detect_content_type(news)
    lang_name = "español rioplatense, tono casual gamer" if language == "es" else "english, casual gamer tone"

    user_prompt = USER_PROMPT_TEMPLATE.format(
        language=lang_name,
        title=news.get("title", ""),
        summary=news.get("description", news.get("summary", ""))[:400],
        source=news.get("source", ""),
        content_type=content_type,
    )

    console.print(f"\n[cyan]Generando guion ({language}): [bold]{news['title'][:55]}[/bold]")

    raw = call_groq(SYSTEM_PROMPT, user_prompt)
    provider = "groq"

    if raw is None:
        console.print("[dim]Intentando con Ollama local...")
        raw = call_ollama(SYSTEM_PROMPT, user_prompt)
        provider = "ollama"

    if raw is None:
        console.print("[red]Ambos providers fallaron.")
        return None

    # Limpiar markdown que el modelo pueda agregar igual
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    try:
        script_data = json.loads(raw)
    except json.JSONDecodeError as e:
        console.print(f"[red]JSON invalido de {provider}: {e}")
        console.print(f"[dim]Raw: {raw[:300]}")
        return None

    script_data["source_news"]  = {
        "title":     news.get("title"),
        "url":       news.get("url"),
        "source":    news.get("source"),
        "published": news.get("published"),
    }
    script_data["language"]     = language
    script_data["provider"]     = provider
    script_data["generated_at"] = datetime.now().isoformat()

    console.print(Panel(
        f"[bold yellow]HOOK:[/bold yellow] {script_data.get('hook')}\n\n"
        f"[white]{script_data.get('script', '')[:220]}...[/white]\n\n"
        f"[dim]Provider: {provider} | ~{script_data.get('estimated_duration_seconds')}s[/dim]",
        title="Guion listo",
        border_style="green",
    ))

    return script_data


# ============================================
# PROCESAR LOTE
# ============================================

def process_news_batch(news_file: Path, languages: list = ["es", "en"]) -> list:
    with open(news_file, encoding="utf-8") as f:
        data = json.load(f)

    # Extraer lista de noticias (el archivo puede ser dict o lista)
    news_list = data.get("news", data) if isinstance(data, dict) else data

    console.rule(f"[bold cyan]Generando guiones — {len(news_list)} noticias")
    scripts = []

    for news in news_list:
        for lang in languages:
            if news.get("language") == "es" and lang == "en":
                continue
            script = generate_script(news, language=lang)
            if script:
                scripts.append(script)
                save_script(script)

    console.print(f"\n[bold green]{len(scripts)} guiones generados")
    return scripts


def save_script(script: dict) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    game = script.get("game_mentioned", "general").replace(" ", "_")[:20]
    lang = script.get("language", "xx")
    filename = f"script_{timestamp}_{lang}_{game}.json"
    output_path = DATA_DIR / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    console.print(f"[dim]Guardado: {filename}")
    return output_path


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    import sys

    news_dir = Path(__file__).parent.parent / "data" / "news"

    if len(sys.argv) > 1:
        news_file = Path(sys.argv[1])
    else:
        files = sorted(news_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            console.print("[red]No hay noticias. Corre primero: python 1_scraper/scraper.py")
            raise SystemExit(1)
        news_file = files[0]
        console.print(f"[dim]Archivo: {news_file.name}")

    process_news_batch(news_file, languages=["es", "en"])
"""
GENERADOR DE AUDIO - Gaming Content Bot
=========================================
Convierte guiones a audio usando Kokoro TTS (local, gratis).

Kokoro es un TTS neural rápido y de buena calidad.
Modelos: ~350MB descargados la primera vez.

Uso:
  python audio_generator.py               → procesa guiones pendientes
  python audio_generator.py --download    → descarga modelos Kokoro
"""

import json
import os
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()

BASE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = BASE_DIR / "data" / "processed"
AUDIO_DIR = BASE_DIR / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

try:
    from kokoro import KokoroTTS
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False


def init_kokoro():
    """Inicializa Kokoro TTS."""
    if not KOKORO_AVAILABLE:
        console.print("[red]Kokoro no instalado. Instalá con: pip install kokoro-onnx")
        return None

    try:
        tts = KokoroTTS()
        console.print("[green]Kokoro TTS inicializado")
        return tts
    except Exception as e:
        console.print(f"[red]Error inicializando Kokoro: {e}")
        return None


def generate_audio(script_data: dict, tts=None) -> Path | None:
    """Convierte el guión a audio .wav."""
    if tts is None:
        tts = init_kokoro()
    if tts is None:
        return None

    language = script_data.get("language", "es")
    script_text = script_data.get("script", "")

    if not script_text:
        console.print("[red]No hay texto en el guión")
        return None

    try:
        audio_data = tts.synthesize(text=script_text, speed=1.0)

        game = script_data.get("game_mentioned", "general").replace(" ", "_")[:20]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}_{language}_{game}.wav"
        output_path = AUDIO_DIR / filename

        with open(output_path, "wb") as f:
            f.write(audio_data)

        console.print(f"[green]Audio generado: {filename}")
        return output_path

    except Exception as e:
        console.print(f"[red]Error generando audio: {e}")
        return None


def process_scripts_batch() -> list:
    """Genera audio para todos los guiones sin audio."""
    tts = init_kokoro()
    if tts is None:
        return []

    pending = []
    for script_file in SCRIPTS_DIR.glob("script_*.json"):
        with open(script_file, encoding="utf-8") as f:
            data = json.load(f)

        if not data.get("audio_path"):
            pending.append((script_file, data))

    if not pending:
        return []

    console.rule(f"[bold cyan]Generando audio — {len(pending)} guiones")
    results = []

    for script_file, script_data in pending:
        audio_path = generate_audio(script_data, tts)

        if audio_path:
            script_data["audio_path"] = str(audio_path)
            script_data["audio_duration"] = script_data.get("estimated_duration_seconds", 50)
            script_data["audio_generated_at"] = datetime.now().isoformat()

            with open(script_file, "w", encoding="utf-8") as f:
                json.dump(script_data, f, ensure_ascii=False, indent=2)

            results.append(audio_path)

    return results


if __name__ == "__main__":
    import sys

    if "--download" in sys.argv:
        console.print("[dim]Descargando modelos Kokoro...")
        tts = init_kokoro()
        if tts:
            console.print("[green]Modelos descargados (~350MB)")
    else:
        process_scripts_batch()

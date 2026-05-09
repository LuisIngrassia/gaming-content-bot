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
    from kokoro_onnx import Kokoro
    KOKORO_AVAILABLE = True
except ImportError:
    KOKORO_AVAILABLE = False


def _download_kokoro_models():
    """Descarga los modelos de Kokoro si no existen."""
    from urllib.request import urlopen
    from pathlib import Path
    import tarfile

    models_dir = Path.home() / ".cache" / "kokoro"
    models_dir.mkdir(parents=True, exist_ok=True)

    model_file = models_dir / "kokoro-v0_19.onnx"
    voices_file = models_dir / "voices.bin"

    if model_file.exists() and voices_file.exists():
        return str(model_file), str(voices_file)

    console.print("[dim]Descargando modelos Kokoro (~350MB)...")

    try:
        # Descargar modelo
        if not model_file.exists():
            console.print("[dim]  Modelo ONNX...")
            url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/kokoro-v0_19.onnx"
            with urlopen(url) as response:
                with open(model_file, "wb") as out:
                    out.write(response.read())

        # Descargar voices
        if not voices_file.exists():
            console.print("[dim]  Voces...")
            url = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files/voices.bin"
            with urlopen(url) as response:
                with open(voices_file, "wb") as out:
                    out.write(response.read())

        console.print("[green]Modelos descargados")
        return str(model_file), str(voices_file)

    except Exception as e:
        console.print(f"[red]Error descargando modelos: {e}")
        return None, None


def init_kokoro():
    """Inicializa Kokoro TTS."""
    if not KOKORO_AVAILABLE:
        console.print("[red]Kokoro no instalado. Instalá con: pip install kokoro-onnx")
        return None

    try:
        model_path, voices_path = _download_kokoro_models()
        if not model_path:
            return None

        tts = Kokoro(model_path=model_path, voices_path=voices_path)
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
        # Kokoro.create retorna (audio_array, sample_rate)
        import numpy as np
        import wave

        # Use first available voice (af = adult female)
        voices = tts.get_voices()
        voice = voices[0] if voices else "af"

        audio_array, sample_rate = tts.create(script_text, voice=voice, lang=language[:5])

        # Convertir a WAV
        game = script_data.get("game_mentioned", "general").replace(" ", "_")[:20]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"audio_{timestamp}_{language}_{game}.wav"
        output_path = AUDIO_DIR / filename

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes((audio_array * 32767).astype(np.int16).tobytes())

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

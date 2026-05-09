"""
GENERADOR DE AUDIO - Gaming Content Bot
========================================
Motor: Kokoro TTS (local, open source, 100% gratis)
Modelos: kokoro-v1.0.onnx + voices-v1.0.bin (~300MB, se bajan una vez)

Soporta español e inglés con voces distintas por idioma.
Corre en CPU o GPU (CUDA) automaticamente.
"""

import json
import os
import sys
import urllib.request
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

console = Console()

# ============================================
# PATHS Y CONFIG
# ============================================

BASE_DIR    = Path(__file__).parent.parent
MODELS_DIR  = BASE_DIR / "models" / "kokoro"
AUDIO_DIR   = BASE_DIR / "data" / "audio"
SCRIPTS_DIR = BASE_DIR / "data" / "processed"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FILE  = MODELS_DIR / "kokoro-v1.0.onnx"
VOICES_FILE = MODELS_DIR / "voices-v1.0.bin"

MODEL_URL  = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

# Voces por idioma
# Lista completa en: huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
VOICES = {
    "es": "ef_dora",    # español, femenina, clara — buena para gaming
    "en": "am_adam",    # inglés, masculina, energética — buena para gaming
}

# Alternativas si querés cambiar:
# es masculino: "em_alex"
# en femenino:  "af_sky"
# en neutro:    "am_michael"

SPEECH_SPEED = {
    "es": 1.1,   # español un poco más rápido (suena más natural en shorts)
    "en": 1.0,
}


# ============================================
# DESCARGA DE MODELOS (solo la primera vez)
# ============================================

def download_file(url: str, dest: Path, label: str):
    """Descarga con barra de progreso."""
    console.print(f"[cyan]Descargando {label}...")

    def reporthook(count, block_size, total_size):
        if total_size > 0:
            pct = int(count * block_size * 100 / total_size)
            mb_done = count * block_size / 1_000_000
            mb_total = total_size / 1_000_000
            print(f"\r  {pct}% ({mb_done:.1f}/{mb_total:.1f} MB)", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook)
    print()  # newline tras la barra
    console.print(f"[green]✅ {label} descargado")


def ensure_models():
    """Verifica que los modelos existan, si no los descarga."""
    missing = []
    if not MODEL_FILE.exists():
        missing.append((MODEL_URL, MODEL_FILE, "kokoro-v1.0.onnx (~300MB)"))
    if not VOICES_FILE.exists():
        missing.append((VOICES_URL, VOICES_FILE, "voices-v1.0.bin (~50MB)"))

    if not missing:
        return True

    console.print("[yellow]Modelos de Kokoro TTS no encontrados. Descargando (solo esta vez)...")
    for url, dest, label in missing:
        try:
            download_file(url, dest, label)
        except Exception as e:
            console.print(f"[red]Error descargando {label}: {e}")
            console.print("[dim]Descargalos manualmente desde:")
            console.print(f"[dim]  {url}")
            console.print(f"[dim]  → guardar en: {MODELS_DIR}/")
            return False

    return True


# ============================================
# GENERADOR DE AUDIO
# ============================================

def load_kokoro():
    """Carga el modelo Kokoro (singleton para no recargar en cada audio)."""
    try:
        from kokoro_onnx import Kokoro
        return Kokoro(str(MODEL_FILE), str(VOICES_FILE))
    except ImportError:
        console.print("[red]kokoro-onnx no instalado. Corré: pip install kokoro-onnx soundfile")
        return None
    except Exception as e:
        console.print(f"[red]Error cargando Kokoro: {e}")
        return None


def text_to_audio(
    text: str,
    language: str,
    output_path: Path,
    kokoro_instance=None
) -> Path | None:
    """
    Convierte texto a audio WAV.
    
    Args:
        text:            el guión a sintetizar
        language:        "es" o "en"
        output_path:     donde guardar el .wav
        kokoro_instance: instancia reutilizable (eficiencia)
    
    Returns:
        Path al archivo generado, o None si falla
    """
    import soundfile as sf

    voice = VOICES.get(language, "am_adam")
    speed = SPEECH_SPEED.get(language, 1.0)
    lang_code = "es" if language == "es" else "en-us"

    if kokoro_instance is None:
        kokoro_instance = load_kokoro()
        if kokoro_instance is None:
            return None

    console.print(f"[cyan]Sintetizando audio ({language}, voz: {voice})...")
    console.print(f"[dim]  Texto: {text[:80]}...")

    try:
        samples, sample_rate = kokoro_instance.create(
            text=text,
            voice=voice,
            speed=speed,
            lang=lang_code,
        )

        sf.write(str(output_path), samples, sample_rate)

        # Calcular duración
        duration = len(samples) / sample_rate
        size_kb = output_path.stat().st_size / 1024

        console.print(f"[green]✅ Audio generado: {output_path.name}")
        console.print(f"[dim]   Duración: {duration:.1f}s | Tamaño: {size_kb:.0f}KB")

        return output_path

    except Exception as e:
        console.print(f"[red]Error en síntesis: {e}")
        return None


# ============================================
# PROCESAR GUIÓN COMPLETO
# ============================================

def process_script(script_path: Path, kokoro_instance=None) -> dict | None:
    """
    Toma un guión JSON y genera el audio correspondiente.
    
    Returns:
        dict con paths de audio generados
    """
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    language    = script.get("language", "es")
    script_text = script.get("script", "")
    game        = script.get("game_mentioned", "general").replace(" ", "_")[:20]

    if not script_text:
        console.print(f"[red]Guión vacío: {script_path.name}")
        return None

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    audio_file  = AUDIO_DIR / f"audio_{timestamp}_{language}_{game}.wav"

    result = text_to_audio(
        text=script_text,
        language=language,
        output_path=audio_file,
        kokoro_instance=kokoro_instance,
    )

    if result is None:
        return None

    # Actualizar el JSON del guión con la ruta del audio
    script["audio_path"] = str(audio_file)
    script["audio_generated_at"] = datetime.now().isoformat()

    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    return {
        "script_path": str(script_path),
        "audio_path":  str(audio_file),
        "language":    language,
        "game":        game,
    }


# ============================================
# PROCESAR LOTE DE GUIONES
# ============================================

def process_scripts_batch(scripts_dir: Path = None) -> list:
    """
    Procesa todos los guiones que no tengan audio generado aún.
    Reutiliza la instancia de Kokoro para eficiencia.
    """
    if scripts_dir is None:
        scripts_dir = SCRIPTS_DIR

    # Buscar guiones sin audio
    pending = []
    for f in scripts_dir.glob("script_*.json"):
        with open(f) as fp:
            data = json.load(fp)
        if "audio_path" not in data:
            pending.append(f)

    if not pending:
        console.print("[yellow]No hay guiones pendientes de audio.")
        return []

    console.rule(f"[bold cyan]🎙 Generando audio — {len(pending)} guiones")

    if not ensure_models():
        console.print("[red]No se pudieron obtener los modelos. Abortando.")
        return []

    # Cargar Kokoro una sola vez para todos los guiones
    kokoro = load_kokoro()
    if kokoro is None:
        return []

    results = []
    for script_path in pending:
        result = process_script(script_path, kokoro_instance=kokoro)
        if result:
            results.append(result)

    console.print(f"\n[bold green]✅ {len(results)} audios generados en data/audio/")
    return results


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    # Uso 1: procesar todos los guiones pendientes
    #   python audio_generator.py
    #
    # Uso 2: procesar un guión específico
    #   python audio_generator.py ../data/processed/script_xxx.json
    #
    # Uso 3: solo descargar modelos
    #   python audio_generator.py --download

    if len(sys.argv) > 1 and sys.argv[1] == "--download":
        ensure_models()
        sys.exit(0)

    if len(sys.argv) > 1:
        script_file = Path(sys.argv[1])
        if not script_file.exists():
            console.print(f"[red]Archivo no encontrado: {script_file}")
            sys.exit(1)
        if not ensure_models():
            sys.exit(1)
        kokoro = load_kokoro()
        process_script(script_file, kokoro_instance=kokoro)
    else:
        process_scripts_batch()
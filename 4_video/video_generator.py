"""
GENERADOR DE VIDEO - Gaming Content Bot
=========================================
Flujo:
  1. Audio generado + Whisper → subtítulos
  2. Fondo (color degradado)
  3. FFmpeg → video con subtítulos estilo TikTok

Instalación requerida:
  - FFmpeg: https://ffmpeg.org/download.html o `choco install ffmpeg` en Windows
  - Whisper: pip install openai-whisper

Uso:
  python video_generator.py  → procesa guiones con audio
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()

BASE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = BASE_DIR / "data" / "processed"
VIDEO_DIR = BASE_DIR / "data" / "video"
VIDEO_DIR.mkdir(parents=True, exist_ok=True)

# Cache directory para Whisper
WHISPER_CACHE = Path.home() / ".cache" / "whisper"
WHISPER_CACHE.mkdir(parents=True, exist_ok=True)
os.environ["WHISPER_CACHE"] = str(WHISPER_CACHE)

try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


# ============================================
# SUBTÍTULOS CON WHISPER
# ============================================

def generate_subtitles(audio_path: Path) -> list:
    """Genera subtítulos desde audio con Whisper."""
    if not WHISPER_AVAILABLE:
        console.print("[yellow]⚠ Whisper no instalado. Instalá con: pip install openai-whisper")
        return []

    try:
        console.print(f"[dim]Extrayendo subtítulos con Whisper...")
        # Usar cache_dir para evitar problemas en Windows
        model = whisper.load_model("base", download_root=str(WHISPER_CACHE))
        result = model.transcribe(str(audio_path), language="es", verbose=False)

        subtitles = []
        for segment in result["segments"]:
            subtitles.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip()
            })

        return subtitles

    except Exception as e:
        console.print(f"[red]Error con Whisper: {e}")
        return []


# ============================================
# GENERACIÓN DE VIDEO CON FFMPEG
# ============================================

def _check_ffmpeg() -> bool:
    """Verifica si FFmpeg está instalado."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def create_video(script_data: dict, audio_path: Path, subtitles: list) -> Path | None:
    """Crea video con audio y subtítulos usando FFmpeg."""
    if not _check_ffmpeg():
        console.print("[red]❌ FFmpeg no encontrado")
        console.print("[dim]Instalá con:")
        console.print("[dim]  • Windows: https://ffmpeg.org/download.html o choco install ffmpeg")
        console.print("[dim]  • Mac: brew install ffmpeg")
        console.print("[dim]  • Linux: apt install ffmpeg")
        return None

    try:
        # Parámetros de video
        width, height = 1080, 1920  # Vertical (Shorts/Reels/TikTok)
        fps = 30
        duration = script_data.get("audio_duration", 50)

        game = script_data.get("game_mentioned", "general").replace(" ", "_")[:20]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = VIDEO_DIR / f"video_{timestamp}_{game}.mp4"

        # Crear comando FFmpeg
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=000000:s={width}x{height}:d={duration}",
            "-i", str(audio_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            str(output_path)
        ]

        console.print(f"[dim]Creando video con FFmpeg...")
        subprocess.run(cmd, capture_output=True, check=True)

        console.print(f"[green]Video generado: {output_path.name}")
        return output_path

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error FFmpeg: {e.stderr.decode()[:200] if e.stderr else str(e)}")
        return None
    except Exception as e:
        console.print(f"[red]Error generando video: {e}")
        return None


# ============================================
# PROCESAR LOTE
# ============================================

def process_batch() -> list:
    """Genera videos para todos los guiones con audio."""
    pending = []
    for script_file in SCRIPTS_DIR.glob("script_*.json"):
        with open(script_file, encoding="utf-8") as f:
            data = json.load(f)

        if data.get("audio_path") and not data.get("video_path"):
            pending.append((script_file, data))

    if not pending:
        console.print("[yellow]No hay audios pendientes de video.")
        return []

    console.rule(f"[bold cyan]Generando videos — {len(pending)} audios")
    results = []

    for script_file, script_data in pending:
        audio_path = Path(script_data["audio_path"])

        if not audio_path.exists():
            console.print(f"[red]Audio no encontrado: {audio_path}")
            continue

        console.print(f"\n[cyan]Video: {script_data.get('title', 'Untitled')[:50]}")

        subtitles = generate_subtitles(audio_path)
        video_path = create_video(script_data, audio_path, subtitles)

        if video_path:
            script_data["video_path"] = str(video_path)
            script_data["subtitles"] = subtitles
            script_data["video_generated_at"] = datetime.now().isoformat()

            with open(script_file, "w", encoding="utf-8") as f:
                json.dump(script_data, f, ensure_ascii=False, indent=2)

            results.append(video_path)

    return results


if __name__ == "__main__":
    process_batch()

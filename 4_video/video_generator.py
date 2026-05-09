"""
GENERADOR DE VIDEO - Gaming Content Bot
========================================
Flujo:
  1. Toma el audio generado por Kokoro
  2. Genera subtítulos con Whisper (local)
  3. Busca imagen de fondo (Unsplash free / carpeta local)
  4. Compone el video final con FFmpeg:
       - Fondo (imagen o color degradado)
       - Subtítulos animados centrados (estilo TikTok)
       - Intro con título del juego
       - Formato vertical 9:16 (1080x1920)

Output: .mp4 listo para publicar
"""

import json
import os
import subprocess
import tempfile
import requests
from pathlib import Path
from datetime import datetime
from rich.console import Console

console = Console()

# ============================================
# PATHS
# ============================================

BASE_DIR   = Path(__file__).parent.parent
VIDEO_DIR  = BASE_DIR / "data" / "video"
AUDIO_DIR  = BASE_DIR / "data" / "audio"
FONTS_DIR  = BASE_DIR / "assets" / "fonts"
BG_DIR     = BASE_DIR / "assets" / "backgrounds"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
FONTS_DIR.mkdir(parents=True, exist_ok=True)
BG_DIR.mkdir(parents=True, exist_ok=True)

# Resolución vertical (TikTok / Reels / Shorts)
WIDTH  = 1080
HEIGHT = 1920

# Colores por tipo de contenido (fondo degradado si no hay imagen)
THEME_COLORS = {
    "patch_note": ("1a1a2e", "16213e", "e94560"),  # azul oscuro + rojo
    "new_game":   ("0f3460", "533483", "e94560"),  # púrpura
    "update":     ("1a1a2e", "16213e", "00b4d8"),  # azul + cyan
    "rumor":      ("2d1b69", "11002f", "ff6b6b"),  # violeta oscuro
    "ranking":    ("1b1b2f", "2b2d42", "ffd60a"),  # oscuro + amarillo
}


# ============================================
# PASO 1: TRANSCRIPCIÓN CON WHISPER
# ============================================

def transcribe_audio(audio_path: Path, language: str = "es") -> list[dict] | None:
    """
    Genera subtítulos word-level usando Whisper.
    Retorna lista de segmentos con timestamps.
    """
    console.print(f"[cyan]Transcribiendo audio con Whisper...")

    try:
        import whisper
        # "base" corre bien en CPU, "small" mejor calidad con GPU
        # En tu 1660 Super: usar "small" sin problema
        model_size = "small"
        model = whisper.load_model(model_size)

        lang_code = "es" if language == "es" else "en"
        result = model.transcribe(
            str(audio_path),
            language=lang_code,
            word_timestamps=True,
            verbose=False,
        )

        # Extraer palabras con timestamps
        words = []
        for segment in result.get("segments", []):
            for word_data in segment.get("words", []):
                words.append({
                    "word":  word_data["word"].strip(),
                    "start": round(word_data["start"], 3),
                    "end":   round(word_data["end"], 3),
                })

        console.print(f"[green]✅ Transcripción: {len(words)} palabras detectadas")
        return words

    except Exception as e:
        console.print(f"[red]Error en Whisper: {e}")
        return None


def words_to_srt(words: list[dict], output_path: Path, words_per_line: int = 4) -> Path:
    """
    Convierte palabras con timestamps a archivo SRT.
    Agrupa de a N palabras por línea (estilo TikTok).
    """
    lines = []
    idx = 1

    for i in range(0, len(words), words_per_line):
        chunk = words[i:i + words_per_line]
        if not chunk:
            continue

        start = chunk[0]["start"]
        end   = chunk[-1]["end"]
        text  = " ".join(w["word"] for w in chunk)

        def fmt_time(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t % 1) * 1000)
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        lines.append(f"{idx}")
        lines.append(f"{fmt_time(start)} --> {fmt_time(end)}")
        lines.append(text.upper())  # mayúsculas estilo TikTok
        lines.append("")
        idx += 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    console.print(f"[green]✅ SRT generado: {output_path.name}")
    return output_path


# ============================================
# PASO 2: IMAGEN DE FONDO
# ============================================

def get_background_image(game: str, content_type: str) -> Path | None:
    """
    Busca imagen de fondo para el video.
    Primero busca en carpeta local assets/backgrounds/,
    si no hay usa Unsplash (gratuito, sin key para queries simples).
    """
    # 1. Buscar local primero
    for ext in ["jpg", "jpeg", "png", "webp"]:
        local = BG_DIR / f"{game.lower().replace(' ', '_')}.{ext}"
        if local.exists():
            console.print(f"[dim]Fondo local: {local.name}")
            return local

    # 2. Unsplash source (gratis, sin API key, redirect directo)
    # Limitation: imagen random del query, no siempre perfecta
    query = f"video+game+{game.replace(' ', '+')}" if game != "general" else "video+game+dark"
    url = f"https://source.unsplash.com/{WIDTH}x{HEIGHT}/?{query}"

    try:
        res = requests.get(url, timeout=15, allow_redirects=True)
        if res.status_code == 200 and "image" in res.headers.get("content-type", ""):
            img_path = BG_DIR / f"_temp_{game[:20].replace(' ', '_')}.jpg"
            with open(img_path, "wb") as f:
                f.write(res.content)
            console.print(f"[dim]Fondo Unsplash descargado para: {game}")
            return img_path
    except Exception as e:
        console.print(f"[dim]Unsplash no disponible ({e}), usando degradado")

    return None  # FFmpeg usará degradado de colores


# ============================================
# PASO 3: COMPOSICIÓN CON FFMPEG
# ============================================

def get_audio_duration(audio_path: Path) -> float:
    """Obtiene duración del audio en segundos."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio_path)],
        capture_output=True, text=True
    )
    try:
        return float(result.stdout.strip())
    except:
        return 60.0


def build_video(
    audio_path:   Path,
    srt_path:     Path,
    output_path:  Path,
    script_data:  dict,
    bg_image:     Path | None = None,
) -> Path | None:
    """
    Compone el video final con FFmpeg.
    
    Estructura:
    - Fondo: imagen oscurecida o degradado animado
    - Texto superior: nombre del juego (0.5s - 3s)
    - Subtítulos: centrados, estilo TikTok
    - Duración: igual al audio
    """
    duration     = get_audio_duration(audio_path)
    game         = script_data.get("game_mentioned", "GAMING")
    content_type = script_data.get("content_type", "update")
    title        = script_data.get("title", "")[:50]
    language     = script_data.get("language", "es")

    colors = THEME_COLORS.get(content_type, THEME_COLORS["update"])
    color1, color2, accent = colors

    console.print(f"[cyan]Componiendo video ({duration:.1f}s)...")

    try:
        # ---- Construir filtergraph de FFmpeg ----

        if bg_image:
            # Con imagen de fondo
            video_input = [
                "-loop", "1", "-i", str(bg_image),  # imagen de fondo
                "-i", str(audio_path),               # audio
            ]
            # Oscurecer imagen y escalar a 9:16
            base_filter = (
                f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={WIDTH}:{HEIGHT},"
                f"colorchannelmixer=rr=0.4:gg=0.4:bb=0.4[bg];"  # oscurecer 60%
            )
            map_args = ["-map", "[final]", "-map", "1:a"]
        else:
            # Sin imagen: degradado animado con colores del tema
            video_input = [
                "-f", "lavfi",
                "-i", f"color=c=0x{color1}:size={WIDTH}x{HEIGHT}:rate=30",
                "-i", str(audio_path),
            ]
            base_filter = (
                f"[0:v]"
                f"drawbox=x=0:y=0:w={WIDTH}:h={HEIGHT//2}:color=0x{color2}@0.5:t=fill,"
                f"[bg];"
            )
            map_args = ["-map", "[final]", "-map", "1:a"]

        # Fuente disponible en el sistema
        font = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if not Path(font).exists():
            font = "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"

        # Subtítulos estilo TikTok (centrados, grandes, con sombra)
        subtitle_style = (
            f"FontName=DejaVu Sans Bold,"
            f"FontSize=22,"
            f"PrimaryColour=&H00FFFFFF,"      # blanco
            f"OutlineColour=&H00000000,"      # contorno negro
            f"BackColour=&H80000000,"         # fondo semitransparente
            f"Bold=1,"
            f"Alignment=2,"                   # centrado inferior
            f"MarginV=300,"                   # subir subtítulos (dejar espacio abajo)
            f"Outline=3,"
            f"Shadow=2"
        )

        # Texto del juego en la parte superior
        game_text = game.upper()
        accent_hex = accent

        subtitle_filter = (
            f"[bg]"
            # Barra superior con nombre del juego
            f"drawbox=x=0:y=80:w={WIDTH}:h=120:color=0x{accent_hex}@0.85:t=fill,"
            f"drawtext=text='{game_text}':fontfile={font}:fontsize=52:fontcolor=white:"
            f"x=(w-text_w)/2:y=105:enable='between(t,0,{duration})',"
            # Tipo de contenido (patch note / new game / etc)
            f"drawtext=text='{content_type.upper().replace('_',' ')}':fontfile={font}:"
            f"fontsize=28:fontcolor=0x{accent_hex}:x=(w-text_w)/2:y=218:"
            f"enable='between(t,0,{duration})',"
            # Subtítulos desde el SRT (usando subtitles filter)
            f"subtitles={srt_path}:force_style='{subtitle_style}'"
            f"[final]"
        )

        full_filter = base_filter + subtitle_filter

        cmd = [
            "ffmpeg", "-y",
            *video_input,
            "-filter_complex", full_filter,
            *map_args,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",      # balance velocidad/calidad
            "-crf", "23",           # calidad (18=alta, 28=baja)
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",  # compatible con todas las plataformas
            "-movflags", "+faststart",  # streaming optimizado
            str(output_path),
        ]

        console.print(f"[dim]FFmpeg procesando...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            console.print(f"[red]FFmpeg error:\n{result.stderr[-500:]}")
            return None

        size_mb = output_path.stat().st_size / 1_000_000
        console.print(f"[green]✅ Video generado: {output_path.name}")
        console.print(f"[dim]   Duración: {duration:.1f}s | Tamaño: {size_mb:.1f}MB")
        return output_path

    except Exception as e:
        console.print(f"[red]Error en composición: {e}")
        return None


# ============================================
# PIPELINE COMPLETO POR GUIÓN
# ============================================

def process_script_to_video(script_path: Path) -> dict | None:
    """
    Pipeline completo: guión JSON → video MP4.
    Requiere que el guión ya tenga audio_path generado.
    """
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    # Verificar que tiene audio
    audio_path_str = script.get("audio_path")
    if not audio_path_str:
        console.print(f"[yellow]Sin audio: {script_path.name} — corré primero audio_generator.py")
        return None

    audio_path = Path(audio_path_str)
    if not audio_path.exists():
        console.print(f"[red]Audio no encontrado: {audio_path}")
        return None

    language = script.get("language", "es")
    game     = script.get("game_mentioned", "general")
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")

    console.rule(f"[bold cyan]🎬 Video: {script.get('title', '')[:40]}")

    # 1. Transcribir → SRT
    with tempfile.TemporaryDirectory() as tmpdir:
        srt_path = Path(tmpdir) / "subtitles.srt"
        words = transcribe_audio(audio_path, language)
        if words is None:
            return None
        words_to_srt(words, srt_path)

        # 2. Fondo
        bg = get_background_image(game, script.get("content_type", "update"))

        # 3. Renderizar video
        video_file = VIDEO_DIR / f"video_{ts}_{language}_{game[:15].replace(' ','_')}.mp4"
        result = build_video(audio_path, srt_path, video_file, script, bg_image=bg)

    if result is None:
        return None

    # Actualizar JSON con ruta del video
    script["video_path"] = str(video_file)
    script["video_generated_at"] = datetime.now().isoformat()
    with open(script_path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)

    return {
        "script_path": str(script_path),
        "video_path":  str(video_file),
        "language":    language,
        "game":        game,
    }


# ============================================
# PROCESAR LOTE
# ============================================

def process_batch(scripts_dir: Path = None) -> list:
    """Procesa todos los guiones con audio pero sin video."""
    if scripts_dir is None:
        scripts_dir = BASE_DIR / "data" / "processed"

    pending = []
    for f in scripts_dir.glob("script_*.json"):
        with open(f) as fp:
            data = json.load(fp)
        if data.get("audio_path") and not data.get("video_path"):
            pending.append(f)

    if not pending:
        console.print("[yellow]No hay guiones pendientes de video.")
        return []

    console.rule(f"[bold cyan]🎬 Generando videos — {len(pending)} pendientes")
    results = []
    for script_path in pending:
        r = process_script_to_video(script_path)
        if r:
            results.append(r)

    console.print(f"\n[bold green]✅ {len(results)} videos en data/video/")
    return results


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        process_script_to_video(Path(sys.argv[1]))
    else:
        process_batch()
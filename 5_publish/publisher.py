"""
PUBLICADOR - Gaming Content Bot
=================================
Publica videos en:
  - YouTube Shorts  (API oficial, gratis)
  - TikTok          (Content Posting API, gratis)
  - Instagram Reels (Graph API de Meta, gratis)

Cada plataforma tiene su propio método.
Se puede publicar en todas a la vez o elegir cuáles.
"""

import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv(Path(__file__).parent.parent / ".env")
console = Console()

BASE_DIR   = Path(__file__).parent.parent
VIDEO_DIR  = BASE_DIR / "data" / "video"
LOGS_DIR   = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# ============================================
# YOUTUBE SHORTS
# ============================================

class YouTubePublisher:
    """
    Publica en YouTube Shorts vía YouTube Data API v3.
    
    Setup:
    1. Google Cloud Console → crear proyecto
    2. Habilitar YouTube Data API v3
    3. Crear credenciales OAuth 2.0 (tipo Desktop App)
    4. Descargar client_secrets.json → poner en raíz del proyecto
    
    El primer run abre el browser para autorizar.
    Después guarda el token y no pide más.
    """

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
    TOKEN_FILE = BASE_DIR / "youtube_token.json"
    SECRETS_FILE = BASE_DIR / "client_secrets.json"

    def authenticate(self):
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None

        if self.TOKEN_FILE.exists():
            creds = Credentials.from_authorized_user_file(str(self.TOKEN_FILE), self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.SECRETS_FILE.exists():
                    console.print("[red]Falta client_secrets.json para YouTube.")
                    console.print("[dim]Descargalo de Google Cloud Console → APIs → YouTube Data API v3 → Credenciales")
                    return None
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.SECRETS_FILE), self.SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self.TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        return build("youtube", "v3", credentials=creds)

    def upload(self, video_path: Path, script_data: dict) -> dict | None:
        from googleapiclient.http import MediaFileUpload

        console.print(f"[cyan]📺 Subiendo a YouTube Shorts...")

        youtube = self.authenticate()
        if not youtube:
            return None

        language  = script_data.get("language", "es")
        title     = script_data.get("title", "Gaming News")[:100]
        desc      = script_data.get("description", "")
        hashtags  = " ".join(script_data.get("hashtags", []))
        game      = script_data.get("game_mentioned", "gaming")

        # YouTube Shorts requiere #Shorts en título o descripción
        full_description = f"{desc}\n\n{hashtags}\n\n#Shorts #Gaming #{game.replace(' ', '')}"
        full_title       = f"{title} #Shorts"

        body = {
            "snippet": {
                "title":       full_title[:100],
                "description": full_description[:5000],
                "tags":        [game, "gaming", "shorts", language],
                "categoryId":  "20",  # Gaming
                "defaultLanguage": language,
            },
            "status": {
                "privacyStatus":           "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 5,  # chunks de 5MB
        )

        try:
            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            response = None
            with console.status("[dim]Subiendo..."):
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        pct = int(status.progress() * 100)
                        console.print(f"[dim]  YouTube: {pct}%", end="\r")

            video_id  = response.get("id")
            video_url = f"https://youtube.com/shorts/{video_id}"
            console.print(f"[green]✅ YouTube Shorts: {video_url}")
            return {"platform": "youtube", "url": video_url, "id": video_id}

        except Exception as e:
            console.print(f"[red]Error YouTube: {e}")
            return None


# ============================================
# TIKTOK
# ============================================

class TikTokPublisher:
    """
    Publica en TikTok vía Content Posting API.
    
    Setup:
    1. developers.tiktok.com → crear app
    2. Solicitar permiso "video.publish"
    3. Obtener access token con OAuth 2.0
    4. Copiar TIKTOK_ACCESS_TOKEN al .env
    
    Nota: el access token expira cada 24hs.
    El refresh token dura 365 días.
    Ver: docs.tiktok.com/api/content-posting
    """

    BASE_URL = "https://open.tiktokapis.com/v2"

    def __init__(self):
        self.access_token  = os.getenv("TIKTOK_ACCESS_TOKEN")
        self.refresh_token = os.getenv("TIKTOK_REFRESH_TOKEN")
        self.client_key    = os.getenv("TIKTOK_CLIENT_KEY")
        self.client_secret = os.getenv("TIKTOK_CLIENT_SECRET")

    def refresh_access_token(self) -> bool:
        """Renueva el access token usando el refresh token."""
        if not all([self.refresh_token, self.client_key, self.client_secret]):
            return False

        res = requests.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key":    self.client_key,
                "client_secret": self.client_secret,
                "grant_type":    "refresh_token",
                "refresh_token": self.refresh_token,
            },
        )

        if res.status_code == 200:
            data = res.json()
            self.access_token = data.get("access_token")
            # Actualizar .env en runtime (no persiste al archivo, solo en memoria)
            os.environ["TIKTOK_ACCESS_TOKEN"] = self.access_token
            console.print("[dim]TikTok token renovado")
            return True

        console.print(f"[red]Error renovando token TikTok: {res.text[:200]}")
        return False

    def upload(self, video_path: Path, script_data: dict) -> dict | None:
        if not self.access_token:
            console.print("[yellow]⚠ TikTok no configurado (TIKTOK_ACCESS_TOKEN faltante)")
            return None

        console.print(f"[cyan]🎵 Subiendo a TikTok...")

        title     = script_data.get("title", "")[:150]
        hashtags  = " ".join(script_data.get("hashtags", []))
        caption   = f"{title} {hashtags}"[:2200]
        file_size = video_path.stat().st_size

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type":  "application/json; charset=UTF-8",
        }

        # Paso 1: iniciar upload
        try:
            init_res = requests.post(
                f"{self.BASE_URL}/post/publish/video/init/",
                headers=headers,
                json={
                    "post_info": {
                        "title":              caption,
                        "privacy_level":      "PUBLIC_TO_EVERYONE",
                        "disable_duet":       False,
                        "disable_comment":    False,
                        "disable_stitch":     False,
                        "video_cover_timestamp_ms": 1000,
                    },
                    "source_info": {
                        "source":         "FILE_UPLOAD",
                        "video_size":     file_size,
                        "chunk_size":     file_size,
                        "total_chunk_count": 1,
                    },
                },
            )

            if init_res.status_code == 401:
                console.print("[dim]Token expirado, renovando...")
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    # reintentar
                    return self.upload(video_path, script_data)
                return None

            init_data   = init_res.json().get("data", {})
            publish_id  = init_data.get("publish_id")
            upload_url  = init_data.get("upload_url")

            if not upload_url:
                console.print(f"[red]TikTok init error: {init_res.text[:300]}")
                return None

            # Paso 2: subir el archivo
            with open(video_path, "rb") as vf:
                video_data = vf.read()

            upload_res = requests.put(
                upload_url,
                data=video_data,
                headers={
                    "Content-Type":         "video/mp4",
                    "Content-Range":        f"bytes 0-{file_size - 1}/{file_size}",
                    "Content-Length":       str(file_size),
                },
            )

            if upload_res.status_code not in [200, 206]:
                console.print(f"[red]TikTok upload error: {upload_res.status_code}")
                return None

            console.print(f"[green]✅ TikTok publicado (publish_id: {publish_id})")
            return {"platform": "tiktok", "publish_id": publish_id}

        except Exception as e:
            console.print(f"[red]Error TikTok: {e}")
            return None


# ============================================
# INSTAGRAM REELS
# ============================================

class InstagramPublisher:
    """
    Publica en Instagram Reels vía Meta Graph API.
    
    Setup:
    1. developers.facebook.com → crear app (tipo Business)
    2. Agregar producto "Instagram Graph API"
    3. Conectar cuenta de Instagram Business/Creator
    4. Generar Long-lived Token (dura 60 días)
    5. Copiar INSTAGRAM_ACCESS_TOKEN e INSTAGRAM_ACCOUNT_ID al .env
    
    Ver: developers.facebook.com/docs/instagram-api/guides/reels
    
    IMPORTANTE: el video debe estar en una URL pública para que Meta lo descargue.
    Opciones:
      - Subir a un bucket S3, Cloudflare R2, o cualquier hosting
      - Usar ngrok temporalmente si corrés local
      - Subir primero a YouTube y usar esa URL (no recomendado)
    
    En este módulo usamos un hosting simple con transfer.sh (gratis, temporal).
    """

    GRAPH_URL = "https://graph.facebook.com/v18.0"

    def __init__(self):
        self.access_token  = os.getenv("INSTAGRAM_ACCESS_TOKEN")
        self.account_id    = os.getenv("INSTAGRAM_ACCOUNT_ID")

    def upload_to_transfer_sh(self, video_path: Path) -> str | None:
        """
        Sube el video a transfer.sh para obtener URL pública temporal.
        Gratis, sin registro, archivos disponibles 14 días.
        """
        console.print("[dim]Subiendo video a transfer.sh para URL pública...")
        try:
            with open(video_path, "rb") as f:
                res = requests.put(
                    f"https://transfer.sh/{video_path.name}",
                    data=f,
                    headers={"Max-Days": "14"},
                    timeout=120,
                )
            if res.status_code == 200:
                url = res.text.strip()
                console.print(f"[dim]URL temporal: {url}")
                return url
            console.print(f"[red]transfer.sh error: {res.status_code}")
            return None
        except Exception as e:
            console.print(f"[red]Error subiendo a transfer.sh: {e}")
            return None

    def upload(self, video_path: Path, script_data: dict) -> dict | None:
        if not self.access_token or not self.account_id:
            console.print("[yellow]⚠ Instagram no configurado (faltan INSTAGRAM_ACCESS_TOKEN / INSTAGRAM_ACCOUNT_ID)")
            return None

        console.print(f"[cyan]📸 Subiendo a Instagram Reels...")

        caption   = script_data.get("description", "")[:2200]
        hashtags  = " ".join(script_data.get("hashtags", []))
        full_cap  = f"{caption}\n\n{hashtags}"[:2200]

        # Paso 1: obtener URL pública del video
        video_url = self.upload_to_transfer_sh(video_path)
        if not video_url:
            console.print("[red]No se pudo obtener URL pública para Instagram")
            return None

        try:
            # Paso 2: crear media container
            container_res = requests.post(
                f"{self.GRAPH_URL}/{self.account_id}/media",
                params={
                    "media_type":   "REELS",
                    "video_url":    video_url,
                    "caption":      full_cap,
                    "share_to_feed": True,
                    "access_token": self.access_token,
                },
            )

            container_data = container_res.json()
            if "error" in container_data:
                console.print(f"[red]Instagram container error: {container_data['error']['message']}")
                return None

            container_id = container_data.get("id")

            # Paso 3: esperar que Meta procese el video (puede tardar ~30s)
            console.print("[dim]Esperando procesamiento de Meta...")
            time.sleep(30)

            # Verificar estado
            for _ in range(10):
                status_res = requests.get(
                    f"{self.GRAPH_URL}/{container_id}",
                    params={
                        "fields":       "status_code,status",
                        "access_token": self.access_token,
                    },
                )
                status_data = status_res.json()
                status_code = status_data.get("status_code")

                if status_code == "FINISHED":
                    break
                elif status_code == "ERROR":
                    console.print(f"[red]Instagram procesamiento falló: {status_data}")
                    return None

                console.print(f"[dim]Estado: {status_code}, esperando...")
                time.sleep(10)

            # Paso 4: publicar
            publish_res = requests.post(
                f"{self.GRAPH_URL}/{self.account_id}/media_publish",
                params={
                    "creation_id":  container_id,
                    "access_token": self.access_token,
                },
            )

            publish_data = publish_res.json()
            if "error" in publish_data:
                console.print(f"[red]Instagram publish error: {publish_data['error']['message']}")
                return None

            media_id = publish_data.get("id")
            console.print(f"[green]✅ Instagram Reels publicado (id: {media_id})")
            return {"platform": "instagram", "media_id": media_id}

        except Exception as e:
            console.print(f"[red]Error Instagram: {e}")
            return None


# ============================================
# PUBLICADOR PRINCIPAL
# ============================================

def publish_video(
    video_path:  Path,
    script_data: dict,
    platforms:   list = ["youtube", "tiktok", "instagram"],
) -> dict:
    """
    Publica un video en todas las plataformas configuradas.
    
    Args:
        video_path:  path al .mp4
        script_data: dict con título, descripción, hashtags, etc.
        platforms:   lista de plataformas a usar
    
    Returns:
        dict con resultados por plataforma
    """
    results = {}

    if "youtube" in platforms:
        yt = YouTubePublisher()
        results["youtube"] = yt.upload(video_path, script_data)

    if "tiktok" in platforms:
        tt = TikTokPublisher()
        results["tiktok"] = tt.upload(video_path, script_data)

    if "instagram" in platforms:
        ig = InstagramPublisher()
        results["instagram"] = ig.upload(video_path, script_data)

    # Log de publicación
    log_entry = {
        "published_at": datetime.now().isoformat(),
        "video":        str(video_path),
        "title":        script_data.get("title"),
        "language":     script_data.get("language"),
        "game":         script_data.get("game_mentioned"),
        "results":      results,
    }

    log_file = LOGS_DIR / "publications.jsonl"
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    # Mostrar resumen
    table = Table(title="📊 Resultado de publicación")
    table.add_column("Plataforma", style="cyan")
    table.add_column("Estado")
    table.add_column("Detalle")

    for platform, result in results.items():
        if result:
            url = result.get("url") or result.get("publish_id") or result.get("media_id") or "ok"
            table.add_row(platform.upper(), "[green]✅ Publicado", str(url))
        else:
            table.add_row(platform.upper(), "[red]❌ Error", "ver logs")

    console.print(table)
    return results


# ============================================
# PROCESAR LOTE
# ============================================

def process_batch(
    scripts_dir: Path = None,
    platforms: list = ["youtube", "tiktok", "instagram"],
) -> list:
    """Publica todos los videos que no hayan sido publicados aún."""
    if scripts_dir is None:
        scripts_dir = BASE_DIR / "data" / "processed"

    pending = []
    for f in scripts_dir.glob("script_*.json"):
        with open(f, encoding="utf-8") as fp:
            data = json.load(fp)
        if data.get("video_path") and not data.get("published_at"):
            pending.append((f, data))

    if not pending:
        console.print("[yellow]No hay videos pendientes de publicación.")
        return []

    console.rule(f"[bold cyan]📤 Publicando — {len(pending)} videos")
    all_results = []

    for script_path, script_data in pending:
        video_path = Path(script_data["video_path"])
        if not video_path.exists():
            console.print(f"[red]Video no encontrado: {video_path}")
            continue

        results = publish_video(video_path, script_data, platforms)
        all_results.append(results)

        # Marcar como publicado en el JSON
        script_data["published_at"] = datetime.now().isoformat()
        script_data["publish_results"] = results
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script_data, f, ensure_ascii=False, indent=2)

        # Esperar entre publicaciones para no triggear rate limits
        time.sleep(5)

    return all_results


# ============================================
# CLI
# ============================================

if __name__ == "__main__":
    import sys

    # Uso: python publisher.py                          → publica todo pendiente en todas
    # Uso: python publisher.py youtube                  → solo YouTube
    # Uso: python publisher.py youtube tiktok           → YouTube y TikTok
    # Uso: python publisher.py path/to/script.json      → un guión específico en todas

    args = sys.argv[1:]
    known_platforms = {"youtube", "tiktok", "instagram"}

    if args and Path(args[0]).exists():
        # Es un archivo específico
        script_path = Path(args[0])
        with open(script_path, encoding="utf-8") as f:
            script_data = json.load(f)
        platforms = [a for a in args[1:] if a in known_platforms] or list(known_platforms)
        video_path = Path(script_data["video_path"])
        publish_video(video_path, script_data, platforms)
    else:
        # Lote con plataformas opcionales
        platforms = [a for a in args if a in known_platforms] or list(known_platforms)
        process_batch(platforms=platforms)
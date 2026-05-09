# 🎮 Gaming Content Bot

Pipeline 100% automatizado para generar y publicar contenido vertical de videojuegos
en YouTube Shorts, TikTok e Instagram Reels.

## Stack

| Módulo | Herramienta | Costo |
|--------|-------------|-------|
| Noticias | RSS + Reddit + Steam API | Gratis |
| Guiones | Groq API (Llama 3.1 70B) | Gratis |
| Guiones fallback | Ollama local (Llama 3.1 8B) | Gratis |
| Audio | Kokoro TTS local | Gratis |
| Subtítulos | Whisper local | Gratis |
| Video | FFmpeg local | Gratis |
| Publicación | APIs nativas | Gratis |
| DB | SQLite | Gratis |

---

## Setup inicial

### 1. Instalar

```bash
git clone https://github.com/tuusuario/gaming-content-bot
cd gaming-content-bot
pip install -r requirements.txt
```

### 2. Configurar .env

```bash
cp .env.example .env
# Editar .env con tus keys
```

| Variable | Dónde | Tiempo |
|----------|-------|--------|
| `GROQ_API_KEY` | console.groq.com | 2 min |
| `REDDIT_CLIENT_ID/SECRET` | reddit.com/prefs/apps | 3 min |
| `STEAM_API_KEY` | steamcommunity.com/dev/apikey | 2 min |
| `YOUTUBE_API_KEY` | console.cloud.google.com | 10 min |
| `TIKTOK_*` | developers.tiktok.com | 1-3 días (aprobación) |
| `INSTAGRAM_*` | developers.facebook.com | 15 min |

### 3. YouTube OAuth (una sola vez)

```bash
# Bajar client_secrets.json de Google Cloud Console → ponerlo en la raíz
python main.py --platforms youtube   # abre browser para autorizar
```

### 4. Ollama (fallback local)

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b
```

### 5. Modelos Kokoro TTS

```bash
python 3_audio/audio_generator.py --download   # ~350MB, solo esta vez
```

---

## Uso

```bash
python main.py                            # pipeline completo
python main.py --lang es                  # solo español
python main.py --lang en                  # solo inglés
python main.py --platforms youtube        # solo YouTube
python main.py --platforms youtube tiktok # YouTube y TikTok
python main.py --schedule                 # modo automático (usa horario en CONFIG)
python main.py --analytics                # ver métricas
```

### Módulos por separado

```bash
python 1_scraper/scraper.py es
python 2_script/script_generator.py
python 3_audio/audio_generator.py
python 4_video/video_generator.py
python 5_publish/publisher.py
python 6_analytics/analytics.py --dashboard
```

---

## Cron (recomendado)

```bash
crontab -e
```

```cron
# Pipeline 2 veces al día
0 9,21 * * * cd /ruta/gaming-content-bot && python main.py >> logs/cron.log 2>&1

# Analytics diario
0 8 * * * cd /ruta/gaming-content-bot && python main.py --analytics >> logs/cron.log 2>&1
```

---

## Estructura

```
gaming-content-bot/
├── main.py                  ← orquestador
├── requirements.txt
├── .env.example
├── .gitignore
├── client_secrets.json      ← YouTube OAuth (NO subir a GitHub)
│
├── 1_scraper/
│   ├── scraper.py
│   └── sources_config.py
├── 2_script/
│   └── script_generator.py
├── 3_audio/
│   └── audio_generator.py
├── 4_video/
│   └── video_generator.py
├── 5_publish/
│   ├── publisher.py
│   └── SETUP.md
├── 6_analytics/
│   └── analytics.py
│
├── assets/backgrounds/      ← fondos 1080x1920 por juego
├── data/                    ← generado en runtime (en .gitignore)
├── models/                  ← Kokoro TTS (en .gitignore)
└── logs/                    ← logs de runs (en .gitignore)
```

---

## Agregar juegos al scraper de Steam

Editar `TOP_GAMES` en `1_scraper/scraper.py` con el AppID del juego.
AppIDs en: https://steamdb.info

## Cambiar voces de TTS

Editar `VOICES` en `3_audio/audio_generator.py`.
Lista completa: https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md

## Personalizar temas visuales

Editar `THEME_COLORS` en `4_video/video_generator.py`.
Agregar fondos propios en `assets/backgrounds/` (nombre = juego en minúsculas).
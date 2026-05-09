# 📤 Setup de plataformas de publicación

## YouTube Shorts ← más fácil de configurar

1. Ir a [console.cloud.google.com](https://console.cloud.google.com)
2. Crear proyecto nuevo
3. APIs & Services → Enable APIs → buscar **YouTube Data API v3** → Enable
4. APIs & Services → Credentials → Create Credentials → **OAuth 2.0 Client ID**
   - Application type: **Desktop App**
   - Nombre: `gaming-content-bot`
5. Descargar el JSON → renombrarlo a `client_secrets.json` → poner en la raíz del proyecto
6. Primera vez que corrás el bot, abre el browser para autorizar. Después es automático.

---

## TikTok

1. Ir a [developers.tiktok.com](https://developers.tiktok.com)
2. Crear app → tipo **Web**
3. En Products → agregar **Content Posting API**
4. Solicitar acceso (puede tardar unos días en aprobarse)
5. Una vez aprobado, OAuth flow para obtener tokens:
   - `TIKTOK_ACCESS_TOKEN` (expira en 24hs)
   - `TIKTOK_REFRESH_TOKEN` (expira en 365 días)
   - `TIKTOK_CLIENT_KEY`
   - `TIKTOK_CLIENT_SECRET`

> El bot renueva el access token automáticamente usando el refresh token.

---

## Instagram Reels

1. Ir a [developers.facebook.com](https://developers.facebook.com)
2. Crear app → tipo **Business**
3. Agregar producto → **Instagram Graph API**
4. Conectar tu cuenta de Instagram (debe ser **Business** o **Creator**, no personal)
5. En Graph API Explorer → generar token con permisos:
   - `instagram_basic`
   - `instagram_content_publish`
   - `pages_read_engagement`
6. Convertir a Long-lived token (dura 60 días):
   ```
   GET https://graph.facebook.com/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id={APP_ID}
     &client_secret={APP_SECRET}
     &fb_exchange_token={SHORT_TOKEN}
   ```
7. Obtener tu Instagram Account ID:
   ```
   GET https://graph.facebook.com/me/accounts?access_token={TOKEN}
   ```
8. Copiar al `.env`:
   - `INSTAGRAM_ACCESS_TOKEN`
   - `INSTAGRAM_ACCOUNT_ID`

> ⚠️ El token de Instagram expira en 60 días. Renovarlo manualmente o configurar refresh automático.

---

## Variables en .env

```env
# YouTube (no va token acá, usa client_secrets.json)
# Solo asegurarse que client_secrets.json esté en la raíz

# TikTok
TIKTOK_ACCESS_TOKEN=
TIKTOK_REFRESH_TOKEN=
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=

# Instagram
INSTAGRAM_ACCESS_TOKEN=
INSTAGRAM_ACCOUNT_ID=
```

---

## Testear cada plataforma por separado

```bash
cd 5_publish

# Solo YouTube
python publisher.py youtube

# Solo TikTok
python publisher.py tiktok

# Solo Instagram
python publisher.py instagram

# Todas
python publisher.py
```
# Setup: Video Generator Dependencies

## FFmpeg (Required)

FFmpeg is needed to create video files from audio and image backgrounds.

### Installation Options

#### Option 1: Chocolatey (Windows) - Recommended
```powershell
choco install ffmpeg
```

#### Option 2: Windows Package Manager
```powershell
winget install FFmpeg
```

#### Option 3: Manual Download
1. Visit https://ffmpeg.org/download.html
2. Download the Windows build (recommended: full static build)
3. Extract to a folder, e.g., `C:\ffmpeg`
4. Add to PATH:
   - Press `Win + X`, search for "Environment Variables"
   - Edit system environment variables
   - Add the ffmpeg folder to PATH

#### Option 4: macOS
```bash
brew install ffmpeg
```

#### Option 5: Linux (Debian/Ubuntu)
```bash
sudo apt install ffmpeg
```

### Verify Installation
```bash
ffmpeg -version
```

## Whisper (Automatic)

Whisper model is downloaded automatically on first use (~350MB).

## Video Output

Once both are installed, videos will be generated in `data/video/` directory with:
- Resolution: 1080x1920 (vertical, optimized for TikTok/Shorts/Reels)
- Format: MP4 with H.264 video + AAC audio
- Subtitles: Auto-generated from audio using Whisper

## Testing

```bash
python video_generator.py
```

Videos will be created for all audio files that don't have videos yet.

<p align="center">
  <img src="screenshot.png" alt="VidPro Web UI Screenshot" width="800">
</p>

# VidPro — YouTube, Instagram & TikTok Downloader

A modern media downloader built on `yt-dlp`, featuring a responsive Web UI, interactive CLI, and smart platform-based folder organization.

---

## 🚀 Quick Start

One command to install dependencies and launch the Web UI:

```bash
python3 run.py
```

`run.py` automatically:
- Creates a virtual environment (`venv`) if missing
- Installs all required Python packages
- Checks for `ffmpeg` (prompts installation guide if missing)
- Launches the Web UI → browser opens automatically at `http://127.0.0.1:8767`

---

## ✨ Key Features

### 1. Multi-Platform Support
- **YouTube**: Videos, playlists, Shorts, and live stream recordings.
- **Instagram**: Reels, posts, and IGTV content.
- **TikTok**: Watermark-free video downloads with metadata extraction.

### 2. Smart Folder Organization
Downloads are auto-sorted into clean, platform-specific directories:
- `downloads/YouTube/`
- `downloads/Instagram/`
- `downloads/TikTok/`
- **Playlist-specific subfolders**: YouTube playlists are saved under their title (e.g., `downloads/YouTube/Favorite_List/`).

### 3. Advanced Web UI
- **Live Preview**: Paste a link → instantly see thumbnail, title, and channel info (YouTube & TikTok).
- **Progress Tracking**: Smooth animated progress bars + real-time download speed.
- **Playlist Management**: View all videos in a list, track status (✅ Completed, ⚠️ Skipped, ❌ Failed).
- **Smart Cleanup**: Filter and delete completed, failed, or skipped items from history.
- **Duplicate Detection**: Detects already-downloaded files and optionally skips them (with warning).
- **Theme Support**: Light/Dark mode for comfortable viewing.

---

## 🛠 Usage Modes

### 1. Web UI
```bash
python3 run.py
# or
python yt_downloader.py --web
```

### 2. Interactive CLI (Arrow-key navigation)
```bash
python yt_downloader.py
```
Navigate menus with arrow keys and select options interactively.

### 3. Standard CLI
```bash
python yt_downloader.py <URL> [options]
```

---

## ⚙️ All Options

| Option | Default | Description |
|--------|---------|-------------|
| `--web` | — | Launch Web UI (port: 8767) |
| `-o, --output DIR` | `./downloads` | Base download directory |
| `--audio` | — | Download audio only (MP3, 192kbps) |
| `--subtitle` | — | Download subtitles (TR & EN supported) |
| `--thumbnail` | — | Save thumbnail image |
| `--metadata` | — | Save video metadata as JSON |
| `--no-overwrite` | — | Skip if file exists (UI shows warning) |
| `--clip START END` | — | Download specific segment (e.g., `00:01:00 00:02:30`) |
| `--playlist` | — | Download entire playlist |
| `--batch-file FILE` | — | Read batch of URLs from file |

---

## 📝 Requirements
- **Python 3.8+**
- **ffmpeg**: Required for video/audio processing (must be installed system-wide).
- **Internet connection**: To fetch and download media.

---

## 📂 Sample Directory Structure
```text
vidpro/
├── downloads/
│   ├── YouTube/
│   │   └── Music_Playlist/
│   │       ├── video1.mp4
│   │       └── video2.mp4
│   ├── Instagram/
│   │   └── reel_video.mp4
│   └── TikTok/
│       └── tiktok_trend.mp4
```

---

> 💡 **Note**: This tool is for personal/fair-use downloading only. Respect creators' rights and platform terms of service.
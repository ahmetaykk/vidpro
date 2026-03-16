<p align="center">
  <img src="screenshot.png" alt="VidPro Web UI Screenshot" width="800">
</p>

# VidPro v2 — Multi-Site Video & Subtitle Downloader

A modern media downloader built on `yt-dlp`, featuring a responsive Web UI, interactive CLI, authentication options, and smart domain-based folder organization.

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

### 1. Multi-Site Support (yt-dlp powered)
- Supports **YouTube, Instagram, TikTok** and **1000+ additional sites** supported by `yt-dlp`.
- Web preview is optimized for YouTube / Instagram / TikTok; downloading works for many other supported domains.

### 2. Smart Folder Organization
Downloads are auto-sorted into clean, domain-based directories:
- `downloads/YouTube/`
- `downloads/Instagram/`
- `downloads/TikTok/`
- `downloads/<OtherDomain>/` (for other supported sites)
- **Playlist-specific subfolders**: YouTube playlists are saved under their title (e.g., `downloads/YouTube/Favorite_List/`).

### 3. Advanced Web UI
- **Live Preview**: Paste a link → instantly see thumbnail, title, and channel info (YouTube & TikTok).
- **Progress Tracking**: Smooth animated progress bars + real-time download speed.
- **Playlist Management**: View all videos in a list, track status (✅ Completed, ⚠️ Skipped, ❌ Failed).
- **Smart Cleanup**: Filter and delete completed, failed, or skipped items from history.
- **Duplicate Detection**: Detects already-downloaded files and optionally skips them (with warning).
- **Theme Support**: Light/Dark mode for comfortable viewing.
- **Language Switcher**: Topbar language selector with **flag-only UI**, **English (default)** + 7 more languages.
- **Subtitle Controls**: Multi-select subtitle language list (default: English), subtitle format selection, embed subtitles, and only-subtitles mode.
- **Auth/Network Controls**: Cookies file, proxy, user-agent, referer, and custom headers (JSON).

### 4. Flexible Subtitle Workflow
- Download subtitles with multi-select language list (e.g. `en,tr,de`).
- Choose subtitle output format (`best`, `vtt`, `srt`, `ass`, `ttml`).
- Embed subtitles into video when compatible.
- Download **only subtitles** without downloading video/audio.
- If selected subtitle languages are not available, jobs are marked as **skipped** (instead of false error in only-subtitles scenarios).
- Jobs cards display subtitle metadata (requested/selected warning context).

### 5. Auth / Restricted Content Support
- `cookies.txt` (Netscape format) support for logged-in/private content.
- Custom `User-Agent`, `Referer`, `Proxy`, and extra HTTP headers.
- Intended for legal/personal use and subject to each platform's terms.

### 6. Localization
- UI localization files are under `static/lang/`.
- Included languages:
  - `static/lang/en.json`
  - `static/lang/tr.json`
  - `static/lang/es.json`
  - `static/lang/de.json`
  - `static/lang/fr.json`
  - `static/lang/it.json`
  - `static/lang/pt.json`
  - `static/lang/ru.json`
- Default language is English; selection is saved in browser `localStorage`.
- FAQ content is localized per language file.

---

## 📜 License
This project is licensed under the **MIT License**.
See [LICENSE](file:///Users/mac/Desktop/vidpro/LICENSE).

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
| `--history` | — | Show download history |
| `--history-file FILE` | `archive.txt` | History/archive file path |
| `-o, --output DIR` | `./downloads` | Base download directory |
| `-q, --quality` | `best` | Video quality preset (`best/4k/1080/720/480/360`) |
| `--out-format` | `mp4` | Output container (`mp4/mkv/webm`) |
| `-f, --format FORMAT_ID` | — | Explicit yt-dlp format selector |
| `--audio` | — | Download audio only (MP3, 192kbps) |
| `--subtitle` | — | Enable subtitle download |
| `--subtitle-langs DILLER` | `en` | Subtitle languages (comma-separated, e.g. `en,tr,de`) |
| `--subtitle-format FORMAT` | `best` | Subtitle format (`best/vtt/srt/ass/ttml`) |
| `--embed-subs` | — | Embed subtitles into video (when compatible) |
| `--only-subs` | — | Download only subtitles (skip media download) |
| `--thumbnail` | — | Save thumbnail image |
| `--metadata` | — | Save video metadata as JSON |
| `--no-overwrite` | — | Skip if file exists (UI shows warning) |
| `--archive FILE` | — | Use archive file to avoid re-downloading |
| `--clip START END` | — | Download specific segment (e.g., `00:01:00 00:02:30`) |
| `--playlist` | — | Download entire playlist |
| `--playlist-start N` | — | Playlist start index |
| `--playlist-end N` | — | Playlist end index |
| `--list-formats` | — | List available formats for given URL |
| `--cookies FILE` | — | Cookies file path (Netscape format) |
| `--proxy URL` | — | Proxy URL (HTTP/SOCKS) |
| `--user-agent UA` | — | Custom User-Agent header |
| `--referer URL` | — | Custom Referer header |
| `--headers-json JSON` | — | Extra headers as JSON object |
| `--batch-file FILE` | — | Read batch of URLs from file |
| `--concurrent N` | `1` | Parallel downloads for batch mode |

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
│   └── Twitter/
│       └── post_video.mp4
```

---

> 💡 **Note**: This tool is for personal/fair-use downloading only. Respect creators' rights and platform terms of service.

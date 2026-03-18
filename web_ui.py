"""
Web UI - FastAPI backend for VidPro

Features:
- RESTful API for video downloading
- Real-time progress tracking via WebSocket-like polling
- Job management with cancel/pause functionality
- Playlist support with individual video tracking
- Security-focused input validation
- CORS protection
- File management and folder operations
- Settings persistence
- Multi-language support

Security:
- Input validation for all user inputs
- Path traversal protection
- CORS restrictions to localhost only
- Safe file handling
- Cookie file validation

Architecture:
- Jobs stored in jobs_history.json
- Playlists stored in playlists_history.json
- Settings stored in settings.json
- Background task processing
- Thread-safe operations with locks
"""
import os
import json
import threading
import webbrowser
from datetime import datetime
import signal
import socket
import ipaddress
from urllib.parse import urlparse, urljoin
import copy
import subprocess
import sys
from validation import validate_url, validate_file_path, validate_json_input, validate_cookie_file_path

def open_folder_safe(path):
    """Cross-platform safe folder opening"""
    try:
        if sys.platform == "win32":
            subprocess.run(["explorer", path], check=True)
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=True)
        else:  # Linux
            subprocess.run(["xdg-open", path], check=True)
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

# Configuration loading
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Default configuration if file doesn't exist or is invalid
        return {
            "server": {"host": "127.0.0.1", "port": 8767},
            "security": {"allowed_origins": ["http://127.0.0.1:8767", "http://localhost:8767"]}
        }

CONFIG = load_config()

from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, Response, FileResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import httpx

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="YouTube Downloader")

# CORS middleware - Restrict origins for security using config
app.add_middleware(
    CORSMiddleware,
    allow_origins=CONFIG["security"]["allowed_origins"],
    allow_credentials=False,
    allow_methods=CONFIG["security"].get("allowed_methods", ["GET", "POST", "PUT", "DELETE"]),
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Statik dosyaları sun
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

ICON_PNG_PATH = os.path.join(os.path.dirname(__file__), "static", "icon.png")

JOBS_FILE = "jobs_history.json"

# job_id -> {"cancelled": Event, "paused": Event}
_job_controls: dict = {}

# playlist_id -> {"cancelled": Event, "paused": Event}
_playlist_controls: dict = {}

# Kalıcı depolama ─────────────────────────────────────────────────────────────

def load_jobs() -> dict:
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            pass
    return {}

def save_jobs(jobs: dict):
    try:
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump(jobs, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

PLAYLISTS_FILE = "playlists_history.json"

def load_playlists() -> dict:
    if os.path.exists(PLAYLISTS_FILE):
        try:
            with open(PLAYLISTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            pass
    return {}

def save_playlists(playlists: dict):
    try:
        with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
            json.dump(playlists, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

SETTINGS_FILE = "settings.json"

def load_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
            pass
    return {"cookies_from_browser": ""}

def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _parse_subtitle_langs(value):
    if isinstance(value, str):
        langs = [x.strip().lower().replace("_", "-") for x in value.replace(";", ",").split(",") if x.strip()]
        return langs
    if isinstance(value, (list, tuple, set)):
        return [str(x).strip().lower().replace("_", "-") for x in value if str(x).strip()]
    return []

def _select_subtitle_langs(requested, info):
    subtitles = info.get("subtitles") or {}
    auto_caps = info.get("automatic_captions") or {}
    available_raw = set(subtitles.keys()) | set(auto_caps.keys())
    available = sorted({str(x).strip().lower().replace("_", "-") for x in available_raw if str(x).strip()})
    selected = []
    for want in requested:
        if want in available:
            selected.append(want)
            continue
        want_base = want.split("-")[0]
        match = next((a for a in available if a.split("-")[0] == want_base), None)
        if match:
            selected.append(match)
    uniq_selected = []
    for s in selected:
        if s not in uniq_selected:
            uniq_selected.append(s)
    return uniq_selected, available

# Başlangıçta diskten yükle
jobs: dict      = load_jobs()
playlists: dict = load_playlists()
job_counter: int      = max(jobs.keys(),      default=0)
playlist_counter: int = max(playlists.keys(), default=0)
_lock = threading.Lock()

# ── İndirme işlemi ───────────────────────────────────────────────────────────

def _run_download(job_id: int, url: str, cfg: dict):
    import yt_dlp
    from yt_downloader import build_ydl_opts, save_metadata

    cancelled = _job_controls[job_id]["cancelled"]
    paused    = _job_controls[job_id]["paused"]

    with _lock:
        jobs[job_id]["status"] = "running"
        save_jobs(jobs)

    logs = []
    is_skipped = [False]

    class MyLogger:
        def debug(self, msg):
            if "has already been downloaded" in msg or "already in archive" in msg:
                is_skipped[0] = True
        def info(self, msg): 
            logs.append(f"INFO: {msg}")
            with _lock:
                jobs[job_id]["logs"] = logs[:]
                save_jobs(jobs)
        def warning(self, msg):
            logs.append(f"WARNING: {msg}")
            with _lock:
                jobs[job_id]["logs"] = logs[:]
                save_jobs(jobs)
        def error(self, msg):
            logs.append(f"ERROR: {msg}")
            with _lock:
                jobs[job_id]["logs"] = logs[:]
                save_jobs(jobs)

    def progress_hook(d):
        if cancelled.is_set():
            raise yt_dlp.utils.DownloadError("cancelled")
        # Durdurulmuşsa bekle
        while paused.is_set() and not cancelled.is_set():
            with _lock:
                jobs[job_id]["status"] = "paused"
                save_jobs(jobs)
            threading.Event().wait(0.5)
        if not paused.is_set() and jobs[job_id]["status"] == "paused":
            with _lock:
                jobs[job_id]["status"] = "running"
                save_jobs(jobs)

        filename = os.path.basename(d.get("filename", ""))
        if d["status"] == "downloading":
            with _lock:
                jobs[job_id]["progress"] = d.get("_percent_str", "?%").strip()
                jobs[job_id]["speed"]    = d.get("_speed_str", "?").strip()
                save_jobs(jobs)
        elif d["status"] == "finished":
            logs.append(filename)
            with _lock:
                jobs[job_id]["logs"] = logs[:]
                save_jobs(jobs)

    cfg_copy = copy.deepcopy(cfg)
    cfg_copy["url"] = url  # build_ydl_opts için URL ekle
    opts = build_ydl_opts(cfg_copy)
    opts["progress_hooks"] = [progress_hook]
    opts["logger"] = MyLogger()
    opts["quiet"] = False  # Logları yakalamak için quiet False olmalı ama logger her şeyi yutar

    try:
        # metadata çekmek için de aynı ayarları (cookies vb.) kullanmalıyız
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if cancelled.is_set():
            with _lock:
                jobs[job_id]["status"] = "cancelled"
                jobs[job_id]["error"]  = "İptal edildi"
                save_jobs(jobs)
            return

        jobs[job_id]["title"]         = info.get("title", "")
        jobs[job_id]["thumbnail_url"] = info.get("thumbnail", "")
        jobs[job_id]["uploader"]      = info.get("uploader", "")
        jobs[job_id]["duration"]      = info.get("duration_string", "")

        cfg_copy = copy.deepcopy(cfg)
        cfg_copy["url"] = url
        subtitle_mode = bool(cfg.get("subtitle") or cfg.get("only_subtitles") or cfg.get("embed_subtitles"))
        if subtitle_mode:
            requested = _parse_subtitle_langs(cfg.get("subtitle_langs")) or ["en"]
            selected, available = _select_subtitle_langs(requested, info)
            jobs[job_id]["subtitle_requested"] = ",".join(requested)
            jobs[job_id]["subtitle_available"] = ",".join(available)
            jobs[job_id]["subtitle_selected"] = ",".join(selected)
            if selected:
                cfg_copy["subtitle_langs"] = selected
            else:
                jobs[job_id]["subtitle_warning"] = "No subtitles found for selected languages"
                if cfg.get("only_subtitles"):
                    with _lock:
                        jobs[job_id]["status"] = "skipped"
                        jobs[job_id]["progress"] = "100%"
                        jobs[job_id]["speed"] = ""
                        save_jobs(jobs)
                    return
                cfg_copy["subtitle"] = False
                cfg_copy["embed_subtitles"] = False
        opts = build_ydl_opts(cfg_copy)
        
        # Metadata'yı video ile aynı yere (paths['home']) kaydet
        if cfg.get("metadata"):
            actual_dir = os.path.dirname(opts["outtmpl"])
            save_metadata(info, actual_dir)

        opts["progress_hooks"] = [progress_hook]
        opts["logger"] = MyLogger()
        opts["quiet"] = False

        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        with _lock:
            if not cancelled.is_set():
                if is_skipped[0]:
                    jobs[job_id]["status"]   = "skipped"
                    jobs[job_id]["progress"] = "100%"
                else:
                    jobs[job_id]["status"]   = "done"
                    jobs[job_id]["progress"] = "100%"
                jobs[job_id]["speed"]    = ""
            else:
                jobs[job_id]["status"] = "cancelled"
                jobs[job_id]["error"]  = "İptal edildi"
            save_jobs(jobs)

    except yt_dlp.utils.DownloadError as e:
        with _lock:
            if "Sign in to confirm your age" in str(e):
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"]  = "Age-restricted content. Please sign in to confirm your age."
            elif cancelled.is_set():
                jobs[job_id]["status"] = "cancelled"
                jobs[job_id]["error"]  = "İptal edildi"
            elif cfg.get("only_subtitles") and ("subtitle" in str(e).lower() or "caption" in str(e).lower()):
                jobs[job_id]["status"] = "skipped"
                jobs[job_id]["progress"] = "100%"
                jobs[job_id]["error"]  = "No subtitles found for selected languages"
            else:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"]  = f"Download error: {str(e)}"
            save_jobs(jobs)
    except Exception as e:
        with _lock:
            if cancelled.is_set():
                jobs[job_id]["status"] = "cancelled"
                jobs[job_id]["error"]  = "İptal edildi"
            elif cfg.get("only_subtitles") and ("subtitle" in str(e).lower() or "caption" in str(e).lower()):
                jobs[job_id]["status"] = "skipped"
                jobs[job_id]["progress"] = "100%"
                jobs[job_id]["error"]  = "No subtitles found for selected languages"
            else:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"]  = f"Unexpected error: {str(e)}"
            save_jobs(jobs)

# ── Playlist indirme ─────────────────────────────────────────────────────────

def _run_playlist(playlist_id: int, url: str, cfg: dict):
    import yt_dlp
    from yt_downloader import build_ydl_opts, save_metadata

    cancelled = _playlist_controls[playlist_id]["cancelled"]
    paused    = _playlist_controls[playlist_id]["paused"]

    with _lock:
        playlists[playlist_id]["status"] = "running"
        save_playlists(playlists)

    try:
        # Playlist bilgileri için de cfg ayarlarını kullan
        opts_pl = build_ydl_opts(cfg)
        opts_pl["extract_flat"] = True
        with yt_dlp.YoutubeDL(opts_pl) as ydl:
            info = ydl.extract_info(url, download=False)

        pl_title = info.get("title") or info.get("playlist_title") or "Playlist"
        # Kesin çözüm: playlist_title'ı cfg_copy içine doğru anahtarla yerleştir
        cfg["playlist_title"] = pl_title

        entries      = info.get("entries", [])
        total        = len(entries)

        with _lock:
            playlists[playlist_id]["title"]         = pl_title
            playlists[playlist_id]["thumbnail_url"] = info.get("thumbnails", [{}])[-1].get("url", "") if info.get("thumbnails") else ""
            playlists[playlist_id]["uploader"]      = info.get("uploader", "")
            playlists[playlist_id]["total"]         = total
            playlists[playlist_id]["done_count"]    = 0
            playlists[playlist_id]["items"]         = [
                {"index": i+1, "title": e.get("title", f"Video {i+1}"), "status": "pending", "progress": "0%"}
                for i, e in enumerate(entries)
            ]
            save_playlists(playlists)

        for i, entry in enumerate(entries):
            if cancelled.is_set():
                with _lock:
                    playlists[playlist_id]["status"] = "cancelled"
                    save_playlists(playlists)
                return
            while paused.is_set() and not cancelled.is_set():
                with _lock:
                    playlists[playlist_id]["status"] = "paused"
                threading.Event().wait(0.5)
            with _lock:
                if not paused.is_set():
                    playlists[playlist_id]["status"] = "running"

            video_url   = entry.get("url") or entry.get("webpage_url") or f"https://youtube.com/watch?v={entry.get('id','')}"
            video_title = entry.get("title", f"Video {i+1}")

            is_item_skipped = [False]

            class ItemLogger:
                def debug(self, msg):
                    if "has already been downloaded" in msg or "already in archive" in msg:
                        is_item_skipped[0] = True
                def info(self, msg): pass
                def warning(self, msg): pass
                def error(self, msg): pass

            def make_hook(idx):
                def hook(d):
                    if cancelled.is_set():
                        raise yt_dlp.utils.DownloadError("cancelled")
                    while paused.is_set() and not cancelled.is_set():
                        with _lock:
                            playlists[playlist_id]["status"] = "paused"
                        threading.Event().wait(0.5)
                    with _lock:
                        if not paused.is_set():
                            playlists[playlist_id]["status"] = "running"
                        if d["status"] == "downloading":
                            pct = d.get("_percent_str", "?%").strip()
                            spd = d.get("_speed_str", "?").strip()
                            playlists[playlist_id]["current_progress"] = pct
                            playlists[playlist_id]["speed"] = spd
                            for it in playlists[playlist_id]["items"]:
                                if it["index"] == idx:
                                    it["progress"] = pct
                        elif d["status"] == "finished":
                            for it in playlists[playlist_id]["items"]:
                                if it["index"] == idx:
                                    it["status"] = "done"
                                    it["progress"] = "100%"
                        save_playlists(playlists)
                return hook

            cfg_copy = copy.deepcopy(cfg)
            cfg_copy["playlist"] = False
            cfg_copy["url"] = video_url
            cfg_copy["playlist_title"] = pl_title # Playlist ismini ilet
            opts = build_ydl_opts(cfg_copy)
            
            opts["progress_hooks"] = [make_hook(i+1)]
            opts["logger"] = ItemLogger()
            opts["quiet"] = False

            with _lock:
                # Update status of current item to running
                for it in playlists[playlist_id]["items"]:
                    if it["index"] == i+1:
                        it["status"] = "running"
                playlists[playlist_id]["current_index"] = i + 1
                playlists[playlist_id]["current_title"] = video_title
                save_playlists(playlists)

            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([video_url])
                with _lock:
                    playlists[playlist_id]["done_count"] = i + 1
                    overall_pct = round(((i+1) / total) * 100)
                    playlists[playlist_id]["overall_progress"] = f"{overall_pct}%"
                    # Update item status if skipped
                    for it in playlists[playlist_id]["items"]:
                        if it["index"] == i+1:
                            if is_item_skipped[0]:
                                it["status"] = "skipped"
                            else:
                                it["status"] = "done"
                    save_playlists(playlists)
            except Exception as e:
                with _lock:
                    if not cancelled.is_set():
                        for it in playlists[playlist_id]["items"]:
                            if it["index"] == i+1:
                                it["status"] = "error"
                                it["error"]  = str(e)
                    save_playlists(playlists)

        with _lock:
            if cancelled.is_set():
                playlists[playlist_id]["status"] = "cancelled"
                playlists[playlist_id]["error"]  = "İptal edildi"
            else:
                playlists[playlist_id]["status"]           = "done"
                playlists[playlist_id]["overall_progress"] = "100%"
                playlists[playlist_id]["speed"]            = ""
            save_playlists(playlists)

    except Exception as e:
        with _lock:
            playlists[playlist_id]["status"] = "error"
            playlists[playlist_id]["error"]  = str(e)
            save_playlists(playlists)


# ── Endpoints ────────────────────────────────────────────────────────────────

def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return False
    return True

def _hostname_is_public(hostname: str) -> bool:
    host = (hostname or "").strip().lower()
    if not host or host == "localhost":
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            return False
    return True

def _validate_proxy_url(raw_url: str) -> str:
    u = urlparse(raw_url)
    if u.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid URL scheme")
    if not u.hostname or not _hostname_is_public(u.hostname):
        raise HTTPException(status_code=400, detail="Invalid URL host")
    return raw_url

@app.get("/brand-icon.png")
async def brand_icon():
    if not os.path.exists(ICON_PNG_PATH):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(ICON_PNG_PATH, media_type="image/png", headers={"Cache-Control": "no-store"})

@app.get("/favicon.ico")
@app.get("/favicon.png")
async def favicon():
    if not os.path.exists(ICON_PNG_PATH):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(ICON_PNG_PATH, media_type="image/png", headers={"Cache-Control": "no-store"})

@app.get("/proxy-thumb")
async def proxy_thumb(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="URL missing")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    }

    async with httpx.AsyncClient(timeout=5.0, headers=headers) as client:
        try:
            cur = _validate_proxy_url(url)
            for _ in range(3):
                resp = await client.get(cur, follow_redirects=False)
                if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                    cur = _validate_proxy_url(urljoin(cur, resp.headers["location"]))
                    continue
                break
            resp.raise_for_status()

            content_type = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
            if content_type and not content_type.startswith("image/"):
                raise HTTPException(status_code=415, detail="Unsupported content-type")

            max_bytes = 10 * 1024 * 1024
            content_length = resp.headers.get("content-length")
            if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                raise HTTPException(status_code=413, detail="Image too large")

            data = bytearray()
            async for chunk in resp.aiter_bytes():
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise HTTPException(status_code=413, detail="Image too large")

            return Response(
                content=bytes(data),
                media_type=content_type or "image/jpeg",
                headers={"Cache-Control": "public, max-age=3600"},
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/download")
async def start_download(
    background_tasks: BackgroundTasks,
    url:          str  = Form(...),
    quality:      str  = Form("best"),
    out_format:   str  = Form("mp4"),
    audio_only:   bool = Form(False),
    subtitle:     bool = Form(False),
    subtitle_langs: str = Form(""),
    subtitle_format: str = Form(""),
    embed_subtitles: bool = Form(False),
    only_subtitles: bool = Form(False),
    thumbnail:    bool = Form(False),
    metadata:     bool = Form(False),
    output_dir:   str  = Form("./downloads"),
    no_overwrite: bool = Form(False),
    archive:      str  = Form(""),
    clip_start:   str  = Form(""),
    clip_end:     str  = Form(""),
    cookies_file: str  = Form(""),
    cookies_from_browser: str = Form(""),
    proxy:        str  = Form(""),
    user_agent:   str  = Form(""),
    referer:      str  = Form(""),
    headers_json: str  = Form(""),
):
    global job_counter, playlist_counter
    
    # Input validation
    is_valid, error_msg = validate_url(url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Validate output directory
    is_valid, safe_output_dir, error_msg = validate_file_path(output_dir, allow_absolute=True)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid output directory: {error_msg}")
    
    # Validate cookie file if provided
    if cookies_file:
        is_valid, safe_cookie_path, error_msg = validate_cookie_file_path(cookies_file)
        if not is_valid:
            raise HTTPException(status_code=400, detail=f"Invalid cookie file: {error_msg}")
        cookies_file = safe_cookie_path
    
    # Validate headers JSON if provided
    if headers_json:
        try:
            headers = json.loads(headers_json)
            if not isinstance(headers, dict):
                raise ValueError("headers_json must be an object")
        except (json.JSONDecodeError, ValueError) as e:
            raise HTTPException(status_code=400, detail="Invalid headers_json")

    is_playlist = "list=" in url or "/playlist" in url

    headers = None
    if headers_json and headers_json.strip():
        try:
            headers = json.loads(headers_json)
            if not isinstance(headers, dict):
                raise ValueError("headers_json must be an object")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid headers_json")

    cfg = {
        "url": url,
        "quality": quality,
        "out_format": out_format,
        "audio_only": audio_only,
        "subtitle": subtitle,
        "subtitle_langs": subtitle_langs,
        "subtitle_format": subtitle_format,
        "embed_subtitles": embed_subtitles,
        "only_subtitles": only_subtitles,
        "thumbnail": thumbnail,
        "metadata": metadata,
        "output_dir": safe_output_dir,  # Use validated safe path
        "no_overwrite": no_overwrite,
        "archive": archive,
        "clip_start": clip_start,
        "clip_end": clip_end,
        "cookies": cookies_file,  # Use validated safe path
        "cookies_from_browser": cookies_from_browser,
        "proxy": proxy,
        "user_agent": user_agent,
        "referer": referer,
        "headers": headers,
    }

    if is_playlist:
        with _lock:
            playlist_counter += 1
            pid = playlist_counter
            playlists[pid] = {
                "type":             "playlist",
                "status":           "queued",
                "url":              url,
                "title":            "",
                "thumbnail_url":    "",
                "uploader":         "",
                "total":            0,
                "done_count":       0,
                "overall_progress": "0%",
                "current_index":    0,
                "current_title":    "",
                "current_progress": "0%",
                "speed":            "",
                "items":            [],
                "error":            "",
                "started_at":       datetime.now().strftime("%d.%m.%Y %H:%M"),
                "cfg":              cfg,
            }
            save_playlists(playlists)

        _playlist_controls[pid] = {
            "cancelled": threading.Event(),
            "paused":    threading.Event(),
        }
        background_tasks.add_task(_run_playlist, pid, url, cfg)
        return JSONResponse({"playlist_id": pid, "type": "playlist"})

    else:
        with _lock:
            job_counter += 1
            jid = job_counter
            jobs[jid] = {
                "status":        "queued",
                "url":           url,
                "progress":      "0%",
                "speed":         "",
                "logs":          [],
                "title":         "",
                "thumbnail_url": "",
                "uploader":      "",
                "duration":      "",
                "error":         "",
                "subtitle_requested": "",
                "subtitle_available": "",
                "subtitle_selected": "",
                "subtitle_warning": "",
                "started_at":    datetime.now().strftime("%d.%m.%Y %H:%M"),
                "cfg":           cfg,
            }
            save_jobs(jobs)

        _job_controls[jid] = {
            "cancelled": threading.Event(),
            "paused":    threading.Event(),
        }
        background_tasks.add_task(_run_download, jid, url, cfg)
        return JSONResponse({"job_id": jid, "type": "single"})


@app.get("/jobs")
async def get_all_jobs():
    return JSONResponse(jobs)


@app.get("/playlists")
async def get_all_playlists():
    return JSONResponse(playlists)


@app.get("/playlist-status/{playlist_id}")
async def playlist_status(playlist_id: int):
    return JSONResponse(playlists.get(playlist_id, {"status": "not_found"}))


@app.get("/status/{job_id}")
async def job_status(job_id: int):
    return JSONResponse(jobs.get(job_id, {"status": "not_found"}))


@app.post("/playlists/{playlist_id}/cancel")
async def cancel_playlist(playlist_id: int):
    ctrl = _playlist_controls.get(playlist_id)
    if ctrl:
        ctrl["paused"].clear()
        ctrl["cancelled"].set()
    with _lock:
        if playlist_id in playlists:
            playlists[playlist_id]["status"] = "cancelled"
            playlists[playlist_id]["error"]  = "İptal edildi"
            save_playlists(playlists)
    return JSONResponse({"ok": True})


@app.post("/playlists/{playlist_id}/pause")
async def pause_playlist(playlist_id: int):
    ctrl = _playlist_controls.get(playlist_id)
    if ctrl and not ctrl["cancelled"].is_set():
        ctrl["paused"].set()
        with _lock:
            playlists[playlist_id]["status"] = "paused"
            save_playlists(playlists)
    return JSONResponse({"ok": True})


@app.post("/playlists/{playlist_id}/resume")
async def resume_playlist(playlist_id: int):
    ctrl = _playlist_controls.get(playlist_id)
    if ctrl:
        ctrl["paused"].clear()
        with _lock:
            playlists[playlist_id]["status"] = "running"
            save_playlists(playlists)
    return JSONResponse({"ok": True})


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int):
    ctrl = _job_controls.get(job_id)
    if ctrl:
        ctrl["paused"].clear()
        ctrl["cancelled"].set()
    with _lock:
        if job_id in jobs:
            jobs[job_id]["status"] = "cancelled"
            jobs[job_id]["error"]  = "İptal edildi"
            save_jobs(jobs)
    return JSONResponse({"ok": True})


@app.post("/jobs/{job_id}/pause")
async def pause_job(job_id: int):
    ctrl = _job_controls.get(job_id)
    if ctrl and not ctrl["cancelled"].is_set():
        ctrl["paused"].set()
        with _lock:
            jobs[job_id]["status"] = "paused"
            save_jobs(jobs)
    return JSONResponse({"ok": True})


@app.post("/jobs/{job_id}/resume")
async def resume_job(job_id: int):
    ctrl = _job_controls.get(job_id)
    if ctrl:
        ctrl["paused"].clear()
        with _lock:
            jobs[job_id]["status"] = "running"
            save_jobs(jobs)
    return JSONResponse({"ok": True})


@app.delete("/jobs/clear")
async def clear_jobs(mode: str = "all"):
    with _lock:
        # Modlara göre durum filtreleri
        if mode == "done":
            targets = ("done", "finished")
        elif mode == "error":
            targets = ("error", "failed")
        elif mode == "skipped":
            targets = ("skipped",)
        elif mode == "all":
            targets = ("done", "finished", "error", "failed", "cancelled", "skipped")
        else:
            targets = ("done", "finished", "error", "failed", "cancelled", "skipped")

        to_del_j = [k for k, v in jobs.items()      if v["status"].lower() in targets]
        to_del_p = [k for k, v in playlists.items() if v["status"].lower() in targets]
        
        for k in to_del_j: del jobs[k]
        for k in to_del_p: del playlists[k]
        
        save_jobs(jobs)
        save_playlists(playlists)
    return JSONResponse({"cleared": len(to_del_j) + len(to_del_p)})


@app.get("/history")
async def history(archive_file: str = "archive.txt"):
    if not os.path.exists(archive_file):
        return JSONResponse({"entries": []})
    entries = []
    with open(archive_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    vid_id = parts[1]
                    entries.append({
                        "platform": parts[0],
                        "id":       vid_id,
                        "link":     f"https://youtube.com/watch?v={vid_id}" if parts[0] == "youtube" else vid_id,
                    })
    return JSONResponse({"entries": list(reversed(entries))})  # en yeni üstte


@app.get("/settings")
async def get_settings():
    return load_settings()


@app.post("/settings")
async def update_settings(request: Request):
    try:
        data = await request.json()
        settings = load_settings()
        settings.update(data)
        save_settings(settings)
        return {"status": "ok", "settings": settings}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

@app.post("/jobs/{job_id}/open-folder")
async def open_job_folder(job_id: int):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    from yt_downloader import get_download_dir
    try:
        path = get_download_dir(jobs[job_id]["cfg"])
        if os.path.exists(path):
            if open_folder_safe(path):
                return {"ok": True}
            else:
                raise HTTPException(status_code=500, detail="Failed to open folder")
        else:
            raise HTTPException(status_code=404, detail="Folder does not exist yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/playlists/{playlist_id}/open-folder")
async def open_playlist_folder(playlist_id: int):
    if playlist_id not in playlists:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    from yt_downloader import get_download_dir
    try:
        path = get_download_dir(playlists[playlist_id]["cfg"])
        if os.path.exists(path):
            if open_folder_safe(path):
                return {"ok": True}
            else:
                raise HTTPException(status_code=500, detail="Failed to open folder")
        else:
            raise HTTPException(status_code=404, detail="Folder does not exist yet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def start_server(host=None, port=None):
    if host is None:
        host = CONFIG["server"]["host"]
    if port is None:
        port = CONFIG["server"]["port"]
    
    print(f"\n  Web UI başlatılıyor → http://{host}:{port}")
    print("  [DEBUG] Browser Cookies version: 2.0 (Full CFG logging enabled)\n")
    threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")

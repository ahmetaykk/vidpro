"""
Web UI - FastAPI backend
Jobs kalıcı olarak jobs_history.json dosyasına kaydedilir.
"""
import os
import json
import threading
import webbrowser
from datetime import datetime
import signal

from fastapi import FastAPI, Request, Form, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import httpx

app = FastAPI(title="YouTube Downloader")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

# Statik dosyaları sun
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

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
        except Exception:
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
        except Exception:
            pass
    return {}

def save_playlists(playlists: dict):
    try:
        with open(PLAYLISTS_FILE, "w", encoding="utf-8") as f:
            json.dump(playlists, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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
        def info(self, msg): pass
        def warning(self, msg): pass
        def error(self, msg): pass

    def progress_hook(d):
        if cancelled.is_set():
            raise yt_dlp.utils.DownloadError("cancelled")
        # Durdurulmuşsa bekle
        while paused.is_set() and not cancelled.is_set():
            jobs[job_id]["status"] = "paused"
            threading.Event().wait(0.5)
        if not paused.is_set() and jobs[job_id]["status"] == "paused":
            jobs[job_id]["status"] = "running"

        filename = os.path.basename(d.get("filename", ""))
        if d["status"] == "downloading":
            jobs[job_id]["progress"] = d.get("_percent_str", "?%").strip()
            jobs[job_id]["speed"]    = d.get("_speed_str", "?").strip()
        elif d["status"] == "finished":
            logs.append(filename)
            jobs[job_id]["logs"] = logs[:]

    cfg_copy = dict(cfg)
    cfg_copy["url"] = url  # build_ydl_opts için URL ekle
    opts = build_ydl_opts(cfg_copy)
    opts["progress_hooks"] = [progress_hook]
    opts["logger"] = MyLogger()
    opts["quiet"] = False  # Logları yakalamak için quiet False olmalı ama logger her şeyi yutar

    try:
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
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

        cfg_copy = dict(cfg)
        cfg_copy["url"] = url
        opts = build_ydl_opts(cfg_copy)
        
        # Metadata'yı video ile aynı yere (paths['home']) kaydet
        if cfg.get("metadata"):
            actual_dir = opts["paths"]["home"]
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

    except Exception as e:
        with _lock:
            if cancelled.is_set():
                jobs[job_id]["status"] = "cancelled"
                jobs[job_id]["error"]  = "İptal edildi"
            else:
                jobs[job_id]["status"] = "error"
                jobs[job_id]["error"]  = str(e)
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
        # Playlist bilgilerini çek
        with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
            info = ydl.extract_info(url, download=False)

        pl_title = info.get("title") or info.get("playlist_title") or "Playlist"
        # Kesin çözüm: playlist_title'ı cfg_copy içine doğru anahtarla yerleştir
        cfg["playlist_title"] = pl_title
        
        print(f"DEBUG: Playlist Title Detected: {pl_title}")
        
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

            cfg_copy = dict(cfg)
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

@app.get("/proxy-thumb")
async def proxy_thumb(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="URL missing")
    
    async with httpx.AsyncClient() as client:
        try:
            # Instagram için gerekli header'ları ekle
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            }
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
            
            return StreamingResponse(
                resp.iter_bytes(), 
                media_type=resp.headers.get("content-type", "image/jpeg"),
                headers={"Cache-Control": "public, max-age=3600"}
            )
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
    thumbnail:    bool = Form(False),
    metadata:     bool = Form(False),
    output_dir:   str  = Form("./downloads"),
    no_overwrite: bool = Form(False),
    archive:      str  = Form(""),
    clip_start:   str  = Form(""),
    clip_end:     str  = Form(""),
):
    global job_counter, playlist_counter

    is_playlist = "list=" in url or "/playlist" in url

    cfg = {
        "url": url,
        "quality": quality, "out_format": out_format,
        "audio_only": audio_only, "subtitle": subtitle,
        "thumbnail": thumbnail, "metadata": metadata,
        "output_dir": output_dir, "no_overwrite": no_overwrite,
        "archive": archive or None,
        "clip_start": clip_start or None,
        "clip_end": clip_end or None,
        "playlist": is_playlist,
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
                "cfg": {"quality": quality, "out_format": out_format, "audio_only": audio_only},
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
                "started_at":    datetime.now().strftime("%d.%m.%Y %H:%M"),
                "cfg": {"quality": quality, "out_format": out_format, "audio_only": audio_only},
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


def start_server(host="127.0.0.1", port=8767):
    print(f"\n  Web UI başlatılıyor → http://{host}:{port}\n")
    threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")

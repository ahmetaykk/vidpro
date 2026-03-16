#!/usr/bin/env python3
"""
YouTube Video Downloader - İnteraktif & CLI & Web UI mod
Kullanım:
  python yt_downloader.py              # interaktif mod
  python yt_downloader.py <URL>        # CLI mod
  python yt_downloader.py --web        # Web UI (tarayıcı)
  python yt_downloader.py --history    # indirme geçmişi
"""

import argparse
import sys
import os
import json
import concurrent.futures
from urllib.parse import urlparse

try:
    import yt_dlp
except ImportError:
    print("yt-dlp bulunamadı: pip install yt-dlp")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import print as rprint
    from tqdm import tqdm
    RICH = True
except ImportError:
    RICH = False

try:
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    INQUIRER = True
except ImportError:
    INQUIRER = False

console = Console() if RICH else None

# ─── Yardımcı çıktı ──────────────────────────────────────────────────────────

def cprint(msg, style=""):
    if RICH:
        console.print(f"[{style}]{msg}[/{style}]" if style else msg)
    else:
        print(msg)

def panel(msg, title="", style="blue"):
    if RICH:
        console.print(Panel(msg, title=title, border_style=style))
    else:
        print(f"\n{'='*60}\n{title}\n{msg}\n{'='*60}")

def ask(prompt, choices=None, default=None):
    if RICH:
        from rich.prompt import Prompt
        return Prompt.ask(prompt, choices=choices, default=default)
    opts = f" ({'/'.join(choices)})" if choices else ""
    dflt = f" [{default}]" if default else ""
    return input(f"{prompt}{opts}{dflt}: ").strip() or default

def confirm(prompt, default=True):
    if RICH:
        from rich.prompt import Confirm
        return Confirm.ask(prompt, default=default)
    ans = input(f"{prompt} ({'Y/n' if default else 'y/N'}): ").strip().lower()
    return (ans in ("y","evet","e")) if ans else default

# ─── İlerleme hook ───────────────────────────────────────────────────────────

def make_progress_hook():
    bars = {}
    def hook(d):
        filename = os.path.basename(d.get("filename", "bilinmeyen"))
        short = filename[:50]
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            downloaded = d.get("downloaded_bytes", 0)
            if filename not in bars:
                bars[filename] = tqdm(
                    total=total or None, unit="B", unit_scale=True,
                    unit_divisor=1024, desc=f"  {short}",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{rate_fmt}] ETA:{remaining}",
                    colour="cyan",
                ) if RICH else None
            if bars.get(filename):
                bars[filename].total = total
                bars[filename].update(downloaded - bars[filename].n)
            else:
                print(f"\r  {d.get('_percent_str','?%').strip()}  {d.get('_speed_str','?').strip()}   ", end="", flush=True)
        elif d["status"] == "finished":
            if bars.get(filename):
                bars[filename].close()
                del bars[filename]
            else:
                print()
            cprint(f"  ✓ {filename}", "bold green")
    return hook

# ─── İndirme geçmişi ─────────────────────────────────────────────────────────

def show_history(archive_file="archive.txt"):
    if not os.path.exists(archive_file):
        cprint(f"Arşiv dosyası bulunamadı: {archive_file}", "yellow")
        return

    entries = []
    with open(archive_file) as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    entries.append({"platform": parts[0], "id": parts[1]})

    if not entries:
        cprint("Arşiv boş.", "yellow")
        return

    if RICH:
        table = Table(title=f"İndirme Geçmişi — {archive_file}", header_style="bold magenta", show_lines=True)
        table.add_column("#", style="dim", width=5)
        table.add_column("Platform", style="cyan", width=12)
        table.add_column("Video ID / URL", style="white")
        table.add_column("Link", style="blue")
        for i, e in enumerate(entries, 1):
            vid_id = e["id"]
            link = f"https://youtube.com/watch?v={vid_id}" if e["platform"] == "youtube" else vid_id
            table.add_row(str(i), e["platform"], vid_id, link)
        console.print(table)
        cprint(f"\nToplam: {len(entries)} video", "cyan")
    else:
        print(f"\n{'#':<5} {'Platform':<12} {'ID'}")
        print("-"*50)
        for i, e in enumerate(entries, 1):
            print(f"{i:<5} {e['platform']:<12} {e['id']}")
        print(f"\nToplam: {len(entries)} video")

# ─── Format listeleme ─────────────────────────────────────────────────────────

def list_formats(url):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    panel(
        f"[bold]{info.get('title')}[/bold]\n"
        f"Süre: [cyan]{info.get('duration_string','?')}[/cyan]  |  "
        f"Kanal: [cyan]{info.get('uploader','?')}[/cyan]",
        title="Video Bilgisi"
    )
    if RICH:
        table = Table(header_style="bold magenta")
        for col, w in [("ID",10),("EXT",6),("ÇÖZÜNÜRLÜK",14),("FPS",6),("BOYUT",10),("NOT",20)]:
            table.add_column(col, width=w)
        for f in info.get("formats", []):
            size = f.get("filesize") or f.get("filesize_approx")
            table.add_row(
                f.get("format_id",""), f.get("ext",""), f.get("resolution",""),
                str(f.get("fps","")) if f.get("fps") else "",
                f"{size/1024/1024:.1f}MB" if size else "?",
                f.get("format_note",""),
            )
        console.print(table)
    else:
        print(f"\n{'ID':<10} {'EXT':<6} {'ÇÖZÜNÜRLÜK':<14} {'FPS':<6} {'BOYUT':<10} NOT")
        print("-"*60)
        for f in info.get("formats", []):
            size = f.get("filesize") or f.get("filesize_approx")
            print(f"{f.get('format_id',''):<10} {f.get('ext',''):<6} {f.get('resolution',''):<14} "
                  f"{str(f.get('fps','')):<6} {(str(round(size/1024/1024,1))+'MB') if size else '?':<10} "
                  f"{f.get('format_note','')}")

# ─── Metadata kaydet ──────────────────────────────────────────────────────────

def save_metadata(info, output_dir):
    meta = {k: info.get(k) for k in ["title","uploader","upload_date","duration",
                                       "description","view_count","like_count","webpage_url"]}
    safe = "".join(c for c in (info.get("title","video")) if c.isalnum() or c in " _-")[:60]
    path = os.path.join(output_dir, f"{safe}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    cprint(f"  ✓ Metadata: {path}", "cyan")

# ─── yt-dlp seçenekleri ───────────────────────────────────────────────────────

def build_ydl_opts(cfg):
    url = cfg.get("url", "")
    platform = "Other"
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        host = ""

    if host.startswith("www."):
        host = host[4:]
    if host.startswith("m."):
        host = host[2:]

    if "youtube.com" in host or host == "youtu.be":
        platform = "YouTube"
    elif host.endswith("instagram.com"):
        platform = "Instagram"
    elif host.endswith("tiktok.com"):
        platform = "TikTok"
    elif host:
        parts = host.split(".")
        base = parts[-2] if len(parts) >= 2 else host
        if base in ("co", "com", "org", "net", "app") and len(parts) >= 3:
            base = parts[-3]
        safe = "".join(c for c in base if c.isalnum() or c in ("-", "_")).strip("-_")
        if safe:
            platform = safe[:1].upper() + safe[1:]
    
    # Ana dizini al (mutlak yol)
    base_dir = os.path.abspath(cfg.get("output_dir", "./downloads"))
    
    # Platform klasörünü oluştur
    platform_dir = os.path.join(base_dir, platform)
    
    # Playlist klasörü varsa ekle
    final_dir = platform_dir
    pl_title = cfg.get("playlist_title")
    if pl_title:
        import re
        safe_title = re.sub(r'[\\/*?:"<>|]', "", str(pl_title)).strip()
        if safe_title:
            final_dir = os.path.join(platform_dir, safe_title)
    
    # Klasörü oluştur
    os.makedirs(final_dir, exist_ok=True)
    
    # Kesin çözüm: outtmpl içine tam yolu (final_dir) göm
    # Bu yöntem yt-dlp'yi o klasöre zorlar
    opts = {
        "outtmpl": f"{final_dir}/%(title)s.%(ext)s",
        "progress_hooks": [make_progress_hook()],
        "noplaylist": not cfg.get("playlist", False),
        "quiet": True,
    }
    if cfg.get("no_overwrite"):
        opts["nooverwrites"] = True
    else:
        opts["overwrites"] = True
        opts["nooverwrites"] = False
    
    if cfg.get("archive"):       opts["download_archive"] = cfg["archive"]

    quality_map = {
        "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "4k":   "bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=2160]+bestaudio/best",
        "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best",
        "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best",
        "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best",
        "360":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best",
    }

    if cfg.get("audio_only"):
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]
    else:
        opts["format"] = cfg.get("format_id") or quality_map.get(cfg.get("quality","best"), quality_map["best"])
        opts["merge_output_format"] = cfg.get("out_format", "mp4")

    subtitle_enabled = bool(cfg.get("subtitle") or cfg.get("only_subtitles"))
    if subtitle_enabled:
        raw_langs = cfg.get("subtitle_langs")
        langs = []
        if isinstance(raw_langs, str):
            langs = [x.strip() for x in raw_langs.replace(";", ",").split(",") if x.strip()]
        elif isinstance(raw_langs, (list, tuple, set)):
            langs = [str(x).strip() for x in raw_langs if str(x).strip()]
        if not langs:
            langs = ["tr", "en"]
        opts["writesubtitles"] = True
        opts["subtitleslangs"] = langs
        opts["writeautomaticsub"] = True
        subtitle_format = (cfg.get("subtitle_format") or "").strip()
        if subtitle_format:
            opts["subtitlesformat"] = subtitle_format
        if cfg.get("embed_subtitles") and not cfg.get("audio_only") and not cfg.get("only_subtitles"):
            opts["embedsubtitles"] = True
    if cfg.get("only_subtitles"):
        opts["skip_download"] = True
        opts["ignoreerrors"] = True
    if cfg.get("thumbnail"):
        opts["writethumbnail"] = True
    if cfg.get("playlist_start"): opts["playliststart"] = cfg["playlist_start"]
    if cfg.get("playlist_end"):   opts["playlistend"]   = cfg["playlist_end"]
    if cfg.get("clip_start") or cfg.get("clip_end"):
        sections = {}
        if cfg.get("clip_start"): sections["start_time"] = cfg["clip_start"]
        if cfg.get("clip_end"):   sections["end_time"]   = cfg["clip_end"]
        opts["download_ranges"] = yt_dlp.utils.download_range_func(None, [sections])
        opts["force_keyframes_at_cuts"] = True
    
    http_headers = {}
    extra_headers = cfg.get("headers") or {}
    if isinstance(extra_headers, dict):
        for k, v in extra_headers.items():
            if isinstance(k, str) and v is not None:
                http_headers[k] = str(v)

    user_agent = cfg.get("user_agent")
    if user_agent:
        http_headers.setdefault("User-Agent", str(user_agent))

    referer = cfg.get("referer")
    if referer:
        http_headers.setdefault("Referer", str(referer))

    if host.endswith("instagram.com"):
        http_headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        http_headers.setdefault("Referer", "https://www.instagram.com/")
    if host.endswith("tiktok.com"):
        http_headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        http_headers.setdefault("Referer", "https://www.tiktok.com/")

    if http_headers:
        opts["http_headers"] = http_headers

    cookies = cfg.get("cookies")
    if cookies:
        opts["cookiefile"] = str(cookies)

    proxy = cfg.get("proxy")
    if proxy:
        opts["proxy"] = str(proxy)
    
    return opts

# ─── İndir ───────────────────────────────────────────────────────────────────

def download_single(url, cfg):
    with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    
    # URL'yi cfg içine ekle (platform klasörü için build_ydl_opts kullanıyor)
    cfg["url"] = url
    opts = build_ydl_opts(cfg)
    # build_ydl_opts içinde oluşturulan output_dir'i al
    actual_output_dir = os.path.dirname(opts["outtmpl"])

    panel(
        f"[bold]{info.get('title')}[/bold]\n"
        f"Süre  : [cyan]{info.get('duration_string','?')}[/cyan]\n"
        f"Kanal : [cyan]{info.get('uploader','?')}[/cyan]\n"
        f"Kalite: [cyan]{'MP3' if cfg.get('audio_only') else cfg.get('quality','best')}[/cyan]  "
        f"Format: [cyan]{'mp3' if cfg.get('audio_only') else cfg.get('out_format','mp4')}[/cyan]\n"
        f"Çıktı : [cyan]{os.path.abspath(actual_output_dir)}[/cyan]",
        title="[bold blue]İndiriliyor[/bold blue]"
    )
    if cfg.get("metadata"):
        save_metadata(info, actual_output_dir)
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])

def download_batch(urls, cfg, concurrent_count=1):
    if concurrent_count > 1:
        cprint(f"\n  {len(urls)} URL, {concurrent_count} paralel indirme...", "cyan")
        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrent_count) as ex:
            futures = {ex.submit(download_single, url, cfg): url for url in urls}
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    cprint(f"  ✗ Hata: {e}", "bold red")
    else:
        for i, url in enumerate(urls, 1):
            cprint(f"\n[{i}/{len(urls)}] {url}", "cyan")
            try:
                download_single(url, cfg)
            except Exception as e:
                cprint(f"  ✗ Hata: {e}", "bold red")

# ─── İnteraktif mod (InquirerPy ok tuşları) ──────────────────────────────────

def interactive_mode():
    panel("[bold cyan]YouTube Downloader[/bold cyan]\nOk tuşlarıyla seçim yap, Enter ile onayla", title="Hoş geldin", style="cyan")

    if not INQUIRER:
        cprint("InquirerPy bulunamadı, basit mod kullanılıyor.", "yellow")
        _interactive_simple()
        return

    # Kaynak
    source = inquirer.select(
        message="Ne indirmek istiyorsun?",
        choices=[Choice("single","Tek URL"), Choice("batch","Batch dosyası (urls.txt)")],
    ).execute()

    urls = []
    if source == "single":
        url = inquirer.text(message="YouTube URL:").execute()
        urls = [url]
    else:
        batch_file = inquirer.text(message="Dosya yolu:", default="urls.txt").execute()
        if not os.path.exists(batch_file):
            cprint(f"Dosya bulunamadı: {batch_file}", "bold red"); sys.exit(1)
        with open(batch_file) as f:
            urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        cprint(f"  {len(urls)} URL yüklendi.", "cyan")

    # Video mu ses mi
    media = inquirer.select(
        message="İndirme türü:",
        choices=[Choice("video","Video (MP4/MKV/WebM)"), Choice("audio","Sadece ses (MP3)")],
    ).execute()
    audio_only = media == "audio"

    cfg = {"audio_only": audio_only}

    if not audio_only:
        cfg["quality"] = inquirer.select(
            message="Kalite:",
            choices=["best","4k","1080","720","480","360"],
            default="best",
        ).execute()
        cfg["out_format"] = inquirer.select(
            message="Çıktı formatı:",
            choices=["mp4","mkv","webm"],
            default="mp4",
        ).execute()

    cfg["output_dir"] = inquirer.text(message="İndirme klasörü:", default="./downloads").execute()

    # Playlist
    if len(urls) == 1 and "list=" in urls[0]:
        cfg["playlist"] = inquirer.confirm(message="Playlist'in tamamını indir?", default=True).execute()
        if cfg["playlist"]:
            do_range = inquirer.confirm(message="Belirli aralık mı?", default=False).execute()
            if do_range:
                cfg["playlist_start"] = int(inquirer.text(message="Başlangıç:", default="1").execute())
                cfg["playlist_end"]   = int(inquirer.text(message="Bitiş:", default="10").execute())

    # Klip
    if inquirer.confirm(message="Belirli bir bölümünü mü indirmek istiyorsun?", default=False).execute():
        cfg["clip_start"] = inquirer.text(message="Başlangıç (ör: 00:01:00):").execute()
        cfg["clip_end"]   = inquirer.text(message="Bitiş (ör: 00:02:30):").execute()

    # Ekstra seçenekler (checkbox)
    extras = inquirer.checkbox(
        message="Ekstra seçenekler (boşluk ile seç):",
        choices=[
            Choice("subtitle", "Altyazı indir"),
            Choice("only_subtitles", "Sadece altyazı indir"),
            Choice("embed_subtitles", "Altyazıyı videoya göm"),
            Choice("thumbnail","Kapak resmi kaydet"),
            Choice("metadata", "Metadata JSON kaydet"),
            Choice("no_overwrite","Zaten indirilmişse atla"),
            Choice("archive",  "Arşiv dosyası kullan (archive.txt)"),
        ],
    ).execute()

    for e in extras:
        cfg[e] = True
    if "archive" in extras:
        cfg["archive"] = inquirer.text(message="Arşiv dosyası:", default="archive.txt").execute()
    if cfg.get("subtitle") or cfg.get("only_subtitles") or cfg.get("embed_subtitles"):
        cfg["subtitle"] = True
        cfg["subtitle_langs"] = inquirer.text(message="Altyazı dilleri (virgülle):", default="tr,en").execute()
        cfg["subtitle_format"] = inquirer.select(
            message="Altyazı formatı:",
            choices=["best", "vtt", "srt", "ass", "ttml"],
            default="best",
        ).execute()

    # Paralel
    concurrent_count = 1
    if len(urls) > 1:
        if inquirer.confirm(message=f"{len(urls)} URL var, paralel indir?", default=False).execute():
            concurrent_count = int(inquirer.text(message="Aynı anda kaç video?", default="3").execute())

    # Özet
    panel("\n".join([f"  [cyan]{k}[/cyan]: {v}" for k,v in cfg.items()]), title="Ayarlar", style="green")

    if not inquirer.confirm(message="İndirmeye başla?", default=True).execute():
        cprint("İptal edildi.", "yellow"); sys.exit(0)

    download_batch(urls, cfg, concurrent_count)
    panel("[bold green]Tüm indirmeler tamamlandı![/bold green]", style="green")


def _interactive_simple():
    """InquirerPy yoksa fallback"""
    from rich.prompt import Prompt, Confirm
    url = Prompt.ask("YouTube URL")
    audio_only = Confirm.ask("Sadece ses (MP3)?", default=False)
    cfg = {
        "audio_only": audio_only,
        "quality": Prompt.ask("Kalite", choices=["best","4k","1080","720","480","360"], default="best") if not audio_only else "best",
        "out_format": "mp4",
        "output_dir": Prompt.ask("İndirme klasörü", default="./downloads"),
        "no_overwrite": Confirm.ask("Zaten indirilmişse atla?", default=True),
    }
    download_batch([url], cfg)
    panel("[bold green]Tamamlandı![/bold green]", style="green")

# ─── CLI main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="YouTube Video Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python yt_downloader.py                          # interaktif mod
  python yt_downloader.py --web                    # web UI
  python yt_downloader.py --history                # indirme geçmişi
  python yt_downloader.py https://youtube.com/watch?v=XXX -q 720
  python yt_downloader.py https://youtube.com/watch?v=XXX --audio
  python yt_downloader.py https://youtube.com/watch?v=XXX --clip 00:01:00 00:02:30
  python yt_downloader.py --batch-file urls.txt --concurrent 3
        """
    )
    parser.add_argument("url", nargs="?")
    parser.add_argument("--web", action="store_true", help="Web UI başlat (tarayıcı)")
    parser.add_argument("--history", action="store_true", help="İndirme geçmişini göster")
    parser.add_argument("--history-file", default="archive.txt", metavar="DOSYA")
    parser.add_argument("-o","--output", default="./downloads", metavar="KLASÖR")
    parser.add_argument("-q","--quality", default="best", choices=["best","4k","1080","720","480","360"])
    parser.add_argument("--out-format", default="mp4", choices=["mp4","mkv","webm"])
    parser.add_argument("-f","--format", dest="format_id", metavar="FORMAT_ID")
    parser.add_argument("--audio", action="store_true")
    parser.add_argument("--subtitle", action="store_true")
    parser.add_argument("--subtitle-langs", metavar="DILLER", help="Altyazı dilleri (ör: tr,en,de)")
    parser.add_argument("--subtitle-format", metavar="FORMAT", choices=["best", "vtt", "srt", "ass", "ttml"])
    parser.add_argument("--embed-subs", action="store_true", help="Altyazıyı videoya göm")
    parser.add_argument("--only-subs", action="store_true", help="Sadece altyazıyı indir (video/ses indirmez)")
    parser.add_argument("--thumbnail", action="store_true")
    parser.add_argument("--metadata", action="store_true")
    parser.add_argument("--playlist", action="store_true")
    parser.add_argument("--playlist-start", type=int, metavar="N")
    parser.add_argument("--playlist-end", type=int, metavar="N")
    parser.add_argument("--clip", nargs=2, metavar=("BAŞLANGIÇ","BİTİŞ"))
    parser.add_argument("--list-formats", action="store_true")
    parser.add_argument("--no-overwrite", action="store_true")
    parser.add_argument("--archive", metavar="DOSYA")
    parser.add_argument("--cookies", metavar="DOSYA", help="Cookies dosyası (Netscape formatı)")
    parser.add_argument("--proxy", metavar="URL", help="Proxy URL (ör: http://127.0.0.1:8080, socks5://127.0.0.1:1080)")
    parser.add_argument("--user-agent", dest="user_agent", metavar="UA", help="Özel User-Agent")
    parser.add_argument("--referer", metavar="URL", help="Özel Referer")
    parser.add_argument("--headers-json", dest="headers_json", metavar="JSON", help='Ek header JSON (ör: {"X-Test":"1"})')
    parser.add_argument("--batch-file", metavar="DOSYA")
    parser.add_argument("--concurrent", type=int, default=1, metavar="N")

    args = parser.parse_args()

    if args.web:
        from web_ui import start_server
        start_server()
        return

    if args.history:
        show_history(args.history_file)
        return

    if not args.url and not args.batch_file:
        interactive_mode()
        return

    if args.list_formats:
        list_formats(args.url)
        return

    headers = None
    if args.headers_json:
        try:
            headers = json.loads(args.headers_json)
            if not isinstance(headers, dict):
                raise ValueError("headers-json must be an object")
        except Exception:
            cprint("Geçersiz --headers-json. Örnek: '{\"X-Test\":\"1\"}'", "bold red")
            sys.exit(2)

    cfg = {
        "output_dir": args.output, "quality": args.quality,
        "out_format": args.out_format, "format_id": args.format_id,
        "audio_only": args.audio, "subtitle": args.subtitle,
        "subtitle_langs": args.subtitle_langs,
        "subtitle_format": args.subtitle_format,
        "embed_subtitles": args.embed_subs,
        "only_subtitles": args.only_subs,
        "thumbnail": args.thumbnail, "metadata": args.metadata,
        "playlist": args.playlist, "playlist_start": args.playlist_start,
        "playlist_end": args.playlist_end, "no_overwrite": args.no_overwrite,
        "archive": args.archive,
        "cookies": args.cookies,
        "proxy": args.proxy,
        "user_agent": args.user_agent,
        "referer": args.referer,
        "headers": headers,
    }
    if args.clip:
        cfg["clip_start"] = args.clip[0]
        cfg["clip_end"]   = args.clip[1]

    urls = []
    if args.batch_file:
        with open(args.batch_file) as f:
            urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        cprint(f"  {len(urls)} URL yüklendi.", "cyan")
    if args.url:
        urls.append(args.url)

    if RICH:
        console.print(Panel("[bold cyan]YouTube Downloader[/bold cyan]", border_style="cyan"))

    download_batch(urls, cfg, args.concurrent)

    if RICH:
        console.print(Panel("[bold green]Tüm indirmeler tamamlandı![/bold green]", border_style="green"))


if __name__ == "__main__":
    main()

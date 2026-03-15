#!/usr/bin/env python3
"""
YouTube Downloader - Başlatıcı
Kullanım: python run.py
"""

import sys
import subprocess
import os

VENV_DIR = os.path.join(os.path.dirname(__file__), "venv")

# Venv içindeki python ve pip yolları
if sys.platform == "win32":
    VENV_PYTHON = os.path.join(VENV_DIR, "Scripts", "python.exe")
    VENV_PIP    = os.path.join(VENV_DIR, "Scripts", "pip.exe")
else:
    VENV_PYTHON = os.path.join(VENV_DIR, "bin", "python")
    VENV_PIP    = os.path.join(VENV_DIR, "bin", "pip")

REQUIRED = ["yt-dlp", "rich", "tqdm", "InquirerPy", "fastapi", "uvicorn", "jinja2", "python-multipart", "httpx"]


def run(cmd, **kwargs):
    return subprocess.run(cmd, **kwargs)


def step(msg):
    print(f"\n  \033[96m→\033[0m {msg}")


def ok(msg):
    print(f"  \033[92m✓\033[0m {msg}")


def err(msg):
    print(f"  \033[91m✗\033[0m {msg}")


# ── 1. venv oluştur ──────────────────────────────────────────────────────────
def ensure_venv():
    if not os.path.exists(VENV_PYTHON):
        step("Sanal ortam (venv) oluşturuluyor...")
        result = run([sys.executable, "-m", "venv", VENV_DIR])
        if result.returncode != 0:
            err("venv oluşturulamadı!")
            sys.exit(1)
        ok("venv oluşturuldu.")
    else:
        ok("venv mevcut.")


# ── 2. pip güncelle ──────────────────────────────────────────────────────────
def upgrade_pip():
    run([VENV_PYTHON, "-m", "pip", "install", "--upgrade", "pip"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)


# ── 3. bağımlılıkları kur ────────────────────────────────────────────────────
def install_deps():
    step("Bağımlılıklar kontrol ediliyor...")
    missing = []
    for pkg in REQUIRED:
        # import adı pip adından farklı olabilir
        import_name = {
            "yt-dlp": "yt_dlp",
            "python-multipart": "multipart",
            "InquirerPy": "InquirerPy",
        }.get(pkg, pkg.replace("-", "_").lower())

        result = run(
            [VENV_PYTHON, "-c", f"import {import_name}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        if result.returncode != 0:
            missing.append(pkg)

    if missing:
        step(f"Kuruluyor: {', '.join(missing)}")
        result = run([VENV_PIP, "install"] + missing)
        if result.returncode != 0:
            err("Kurulum başarısız!")
            sys.exit(1)
        ok(f"{len(missing)} paket kuruldu.")
    else:
        ok("Tüm bağımlılıklar mevcut.")


# ── 4. ffmpeg kontrol ────────────────────────────────────────────────────────
def check_ffmpeg():
    result = run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if result.returncode != 0:
        print("\n  \033[93m⚠\033[0m  ffmpeg bulunamadı. Video+ses birleştirme ve klip kesme için gerekli.")
        print("       macOS : brew install ffmpeg")
        print("       Ubuntu: sudo apt install ffmpeg")
        print("       Windows: https://ffmpeg.org/download.html\n")
    else:
        ok("ffmpeg mevcut.")


# ── 5. web UI başlat ─────────────────────────────────────────────────────────
def start_web():
    step("Web UI başlatılıyor → http://127.0.0.1:8767\n")
    os.execv(VENV_PYTHON, [VENV_PYTHON, "yt_downloader.py", "--web"])


# ── Ana akış ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n\033[91m  ▶ YouTube Downloader\033[0m")
    print("  " + "─" * 40)

    ensure_venv()
    upgrade_pip()
    install_deps()
    check_ffmpeg()

    start_web()

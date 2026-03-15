# YouTube, Instagram & TikTok Downloader

`yt-dlp` tabanlı, modern Web UI + İnteraktif CLI + Platform bazlı otomatik klasörleme destekli medya indirme aracı.

---

## 🚀 Hızlı Başlangıç

Tek komut — gerekli her şeyi kurar ve Web UI'yi açar:

```bash
python3 run.py
```

`run.py` şunları otomatik yapar:
- `venv` oluşturur (yoksa)
- Tüm bağımlılıkları kurar
- `ffmpeg` kontrolü yapar, eksikse kurulum talimatı gösterir
- Web UI'yi başlatır → tarayıcı otomatik açılır (`http://127.0.0.1:8767`)

---

## ✨ Öne Çıkan Özellikler

### 1. Geniş Platform Desteği
- **YouTube**: Video, Playlist, Shorts ve Canlı Yayın kayıtları.
- **Instagram**: Reels, Gönderi (Post) ve IGTV içerikleri.
- **TikTok**: Filigransız video indirme ve metadata desteği.

### 2. Akıllı Klasörleme Sistemi
İndirilen dosyalar karışıklığı önlemek için otomatik olarak gruplanır:
- `downloads/YouTube/`
- `downloads/Instagram/`
- `downloads/TikTok/`
- **Playlist Özel**: YouTube playlistleri, platform klasörü altında kendi başlıklarıyla açılan özel alt klasörlere (ör: `downloads/YouTube/Favori_Listem/`) kaydedilir.

### 3. Gelişmiş Web UI
- **Anlık Önizleme**: Link yapıştırıldığı anda (YouTube & TikTok) kapak resmi, başlık ve kanal bilgisi görünür.
- **Canlı İlerleme**: Pürüzsüz animasyonlu ilerleme çubukları ve anlık indirme hızı takibi.
- **Playlist Yönetimi**: Tüm videoları liste halinde görme, durumlarını (Tamamlandı, Atlandı, Hata) tek tek takip etme.
- **Esnek Temizleme**: Tamamlanan, hatalı veya atlanan işleri geçmişten filtreleyerek temizleme.
- **Mevcut Dosya Kontrolü**: Daha önce indirilen dosyaları algılama ve isteğe bağlı olarak atlama (Uyarı bildirimi ile).
- **Light / Dark Tema**: Göz yormayan modern arayüz seçenekleri.

---

## 🛠 Kullanım Modları

### 1. Web UI
```bash
python3 run.py
# veya
python yt_downloader.py --web
```

### 2. İnteraktif CLI (Ok Tuşlarıyla)
```bash
python yt_downloader.py
```
Terminal ekranında ok tuşlarıyla menüler arasında gezinin ve ayarlarınızı seçin.

### 3. Standart CLI
```bash
python yt_downloader.py <URL> [seçenekler]
```

---

## ⚙️ Tüm Seçenekler

| Seçenek | Varsayılan | Açıklama |
|---|---|---|
| `--web` | — | Web UI başlat (Port: 8767) |
| `-o, --output KLASÖR` | `./downloads` | Ana indirme klasörü |
| `--audio` | — | Sadece ses indir (MP3, 192kbps) |
| `--subtitle` | — | Altyazı indir (TR ve EN dahil) |
| `--thumbnail` | — | Kapak resmini (Thumbnail) kaydet |
| `--metadata` | — | Video bilgilerini JSON olarak kaydet |
| `--no-overwrite` | — | Dosya zaten varsa atla (UI'da uyarı verir) |
| `--clip BAŞLANGIÇ BİTİŞ` | — | Belirli bölümü indir (ör: `00:01:00 00:02:30`) |
| `--playlist` | — | Playlist'in tamamını indir |
| `--batch-file DOSYA` | — | Dosyadan toplu URL listesi oku |

---

## 📝 Gereksinimler
- **Python 3.8+**
- **ffmpeg**: Video ve ses birleştirme işlemleri için sisteminizde kurulu olmalıdır.
- **İnternet Bağlantısı**: Medya verilerini çekmek ve indirmek için gereklidir.

---

## 📂 Klasör Yapısı Örneği
```text
ytdownloader/
├── downloads/
│   ├── YouTube/
│   │   └── Müzik_Playlisti/
│   │       ├── video1.mp4
│   │       └── video2.mp4
│   ├── Instagram/
│   │   └── reel_video.mp4
│   └── TikTok/
│       └── tiktok_trend.mp4
```

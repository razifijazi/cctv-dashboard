# CCTV Dashboard Yogyakarta

Dashboard monitoring CCTV Pemkot Yogyakarta dengan fitur streaming ke YouTube.

## Fitur

- 📡 **148 Kamera** — Data real dari [cctv.jogjakota.go.id](https://cctv.jogjakota.go.id/)
- 🎥 **Streaming ke YouTube** — Live stream dengan bitrate custom (500-8000 kbps)
- 🎵 **Music Overlay** — Tambah lagu dari folder `music/` saat streaming
- 🔄 **Switch Kamera Saat Live** — Ganti kamera tanpa stop stream YouTube
- 🎮 **Preview Browser** — Tonton langsung via HLS di browser (gak perlu download)
- 🎛️ **Control Panel** — Start/Stop stream, simpan setting, refresh logs

## Instalasi

```bash
# Clone repo
git clone https://github.com/razifijazi/cctv-dashboard.git
cd cctv-dashboard

# Install dependencies
python3 -m venv .venv
.venv/bin/pip install flask requests

# Buat folder music (opsional)
mkdir -p music
cp lagumu.mp3 music/

# Jalankan
.venv/bin/python app.py
```

Dashboard akan jalan di `http://localhost:5050`

## Struktur File

```
cctv-dashboard/
├── app.py              # Flask backend + HTML/JS frontend
├── cameras.json        # Data 148 kamera (auto-scraped)
├── config.json         # Setting (RTMP, bitrate, music, kamera aktif)
├── music/              # Folder lagu untuk overlay (.mp3, .wav, .flac, .ogg)
├── logs/               # FFmpeg logs
├── nginx-relay.conf    # Config lama (tidak dipakai sekarang)
└── .gitignore
```

## Cara Pakai

1. Buka `http://localhost:5050`
2. Pilih kamera dari sidebar (bisa search + filter per kategori)
3. Isi YouTube RTMP URL (dari YouTube Studio → Go Live → Stream Key)
4. Pilih bitrate (default: 2000 kbps)
5. Pilih lagu dari folder `music/` (opsional)
6. Klik **▶ Start Stream**
7. Buka YouTube Studio untuk live preview

## Ganti Kamera Saat Live

Klik kamera lain di sidebar — stream akan restart dengan kamera baru. YouTube akan reconnect otomatis (delay 1-2 detik).

## Teknologi

- **Backend:** Python + Flask
- **Streaming:** FFmpeg (HLS → RTMP → YouTube)
- **Frontend:** Vanilla HTML/JS + hls.js
- **Preview:** HLS.js di browser (no download needed)

## Catatan

- File `config.json` tidak di-commit (berisi data pribadi)
- File audio di folder `music/` tidak di-commit
- Pastikan FFmpeg terinstall: `sudo apt install ffmpeg`

## License

MIT

#!/usr/bin/python3
"""CCTV Dashboard - Yogyakarta"""
import json, os, subprocess, threading, time
from flask import Flask, jsonify, request, Response

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CAMERAS_FILE = os.path.join(BASE_DIR, "cameras.json")
MUSIC_DIR = os.path.join(BASE_DIR, "music")
os.makedirs(MUSIC_DIR, exist_ok=True)

MUSIC_EXTENSIONS = ('.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac')

DEFAULT_CONFIG = {
    "youtube_rtmp": "",
    "selected_camera_id": "14",
    "stream_active": False,
    "bitrate": "2000",
    "music_file": ""
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

config = load_config()

with open(CAMERAS_FILE) as f:
    CAMERAS = json.load(f)

CAT_LABELS = {
    "1": "🚦 ATCS (Simpang)",
    "2": "🌊 BPBD (Sungai)",
    "3": "🏛 Malioboro",
    "9": "🌳 RTHP",
    "12": "🏛 Balaikota",
    "33": "🛍 Margo Utomo",
    "34": "🏘 Kotabaru",
    "35": "🏢 Kecamatan",
    "195": "🏛 DPRD"
}

camera_process = None
relay_process = None
stream_lock = threading.Lock()

def get_camera_by_id(cam_id):
    for cam in CAMERAS:
        if str(cam['id']) == str(cam_id):
            return cam
    return None

def get_music_files():
    """Scan music folder for audio files"""
    files = []
    try:
        for f in os.listdir(MUSIC_DIR):
            path = os.path.join(MUSIC_DIR, f)
            if os.path.isfile(path) and f.lower().endswith(MUSIC_EXTENSIONS):
                size_mb = os.path.getsize(path) / (1024 * 1024)
                files.append({
                    "name": f,
                    "path": path,
                    "size_mb": round(size_mb, 1)
                })
    except:
        pass
    return sorted(files, key=lambda x: x["name"])

def kill_process(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try: proc.wait(timeout=3)
        except: proc.kill()
    return None

def kill_all():
    global camera_process, relay_process
    camera_process = kill_process(camera_process)
    relay_process = kill_process(relay_process)

def start_stream_direct(cam_url, rtmp, bitrate, music_file):
    """Single ffmpeg: CCTV HLS → YouTube (with optional music overlay)"""
    global relay_process
    relay_process = kill_process(relay_process)
    
    cmd = ["ffmpeg", "-re"]
    # Input: CCTV HLS
    cmd += [
        "-analyzeduration", "10M", "-probesize", "10M",
        "-timeout", "10000000",
        "-i", cam_url
    ]
    # Input: Music overlay (if selected)
    if music_file and os.path.exists(music_file):
        cmd += ["-stream_loop", "-1", "-i", music_file]
        cmd += ["-map", "0:v?", "-map", "1:a"]
    else:
        cmd += ["-map", "0:v?", "-map", "0:a?"]
    
    # Output encoding
    maxrate = int(bitrate * 1.25)
    bufsize = int(bitrate * 2)
    cmd += [
        "-c:v", "libx264", "-preset", "ultrafast",
        "-b:v", f"{bitrate}k", "-maxrate", f"{maxrate}k", "-bufsize", f"{bufsize}k",
        "-pix_fmt", "yuv420p", "-g", "60",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-f", "flv", rtmp
    ]
    
    logfile = open(os.path.join(BASE_DIR, "logs", "relay.log"), "w")
    relay_process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=logfile)
    return relay_process.poll() is None

import atexit
atexit.register(kill_all)

# ── HTML ──────────────────────────────────────────────────────────────────────

HTML = r"""<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>CCTV Yogyakarta</title>
<script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.7/dist/hls.min.js"></script>
<style>
  :root{--bg:#0a0a0f;--surface:#13131a;--border:#1e1e2e;--accent:#7c3aed;--accent2:#06b6d4;--text:#e2e8f0;--muted:#64748b;--green:#22c55e;--red:#ef4444}
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column;overflow:hidden}

  /* TOP BAR */
  .topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:.6rem 1rem;display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
  .topbar-left{display:flex;align-items:center;gap:.75rem}
  .logo{font-size:1.1rem;font-weight:700;letter-spacing:-.02em}
  .logo span{color:var(--accent)}
  .badge{padding:.2rem .6rem;border-radius:999px;font-size:.7rem;font-weight:600}
  .badge.live{background:#14532d;color:var(--green)}
  .badge.off{background:#450a0a;color:var(--red)}
  .cam-count{font-size:.75rem;color:var(--muted)}

  /* LAYOUT */
  .layout{display:flex;flex:1;overflow:hidden}

  /* SIDEBAR */
  .sidebar{width:280px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;flex-shrink:0}
  .sidebar-header{padding:.75rem;border-bottom:1px solid var(--border);flex-shrink:0}
  .search{width:100%;padding:.5rem .75rem;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.8rem;outline:none}
  .search:focus{border-color:var(--accent)}
  .cat-filter{display:flex;gap:.3rem;flex-wrap:wrap;margin-top:.5rem}
  .cat-btn{padding:.2rem .5rem;border-radius:6px;border:1px solid var(--border);background:transparent;color:var(--muted);font-size:.65rem;cursor:pointer;transition:all .15s}
  .cat-btn:hover,.cat-btn.active{background:var(--accent);border-color:var(--accent);color:white}
  .cam-list{flex:1;overflow-y:auto;padding:.5rem}
  .cam-list::-webkit-scrollbar{width:4px}
  .cam-list::-webkit-scrollbar-thumb{background:#2d2d3d;border-radius:2px}
  .cat-label{font-size:.65rem;color:var(--muted);padding:.4rem .3rem .2rem;text-transform:uppercase;letter-spacing:.05em}
  .cam-item{padding:.55rem .7rem;border-radius:8px;cursor:pointer;transition:all .15s;margin-bottom:2px;border:1px solid transparent;display:flex;align-items:center;gap:.5rem}
  .cam-item:hover{background:#1a1a2e;border-color:var(--border)}
  .cam-item.active{background:#1e1b4b;border-color:var(--accent)}
  .cam-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0}
  .dot-0{background:var(--green)}
  .dot-2{background:#f59e0b}
  .dot-other{background:var(--muted)}
  .cam-name{font-size:.8rem;line-height:1.3}

  /* MAIN */
  .main{flex:1;display:flex;flex-direction:column;overflow:hidden}

  /* PLAYER */
  .player-wrap{height:38%;min-height:240px;background:#000;position:relative;overflow:hidden;flex-shrink:0}
  video{width:100%;height:100%;object-fit:contain}
  .player-overlay{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.75rem;color:var(--muted);pointer-events:none}
  .player-overlay.hidden{display:none}
  .player-overlay svg{width:48px;height:48px;opacity:.3}
  .player-overlay p{font-size:.8rem}
  .player-info{position:absolute;bottom:0;left:0;right:0;padding:.5rem .75rem;background:linear-gradient(transparent,rgba(0,0,0,.8));display:flex;align-items:center;justify-content:space-between}
  .player-title{font-size:.85rem;font-weight:600}
  .player-actions{display:flex;gap:.4rem}
  .icon-btn{background:rgba(255,255,255,.1);border:none;color:white;padding:.3rem .5rem;border-radius:6px;cursor:pointer;font-size:.75rem;transition:all .15s}
  .icon-btn:hover{background:rgba(255,255,255,.2)}

  /* BOTTOM PANEL — STREAM SETTINGS (LARGE) */
  .bottom{flex:1;background:var(--surface);border-top:1px solid var(--border);padding:1rem 1.25rem;overflow-y:auto;display:flex;flex-direction:column;gap:1rem}
  .panel-title{font-size:.95rem;font-weight:700;color:var(--text);display:flex;align-items:center;gap:.5rem;padding-bottom:.5rem;border-bottom:1px solid var(--border)}
  .panel-title small{font-size:.7rem;color:var(--muted);font-weight:400;margin-left:auto}
  .panel-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
  @media(max-width:768px){.panel-grid{grid-template-columns:1fr}}
  .form-group{display:flex;flex-direction:column;gap:.35rem}
  .form-label{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-weight:600}
  .form-input{padding:.55rem .8rem;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);font-size:.85rem;outline:none;width:100%;transition:border .15s}
  .form-input:focus{border-color:var(--accent)}
  .form-input[readonly]{color:var(--green);font-weight:600}
  .info-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.5rem;padding:.6rem;background:var(--bg);border-radius:8px;border:1px solid var(--border)}
  .info-item{display:flex;flex-direction:column;gap:.15rem}
  .info-label{font-size:.65rem;color:var(--muted);text-transform:uppercase}
  .info-value{font-size:.85rem;font-weight:600}
  .info-value.live{color:var(--green)}
  .info-value.off{color:var(--muted)}
  .actions{display:flex;gap:.5rem;flex-wrap:wrap;padding-top:.5rem;border-top:1px solid var(--border)}
  .btn{padding:.55rem 1.1rem;border-radius:8px;border:none;font-size:.85rem;font-weight:600;cursor:pointer;transition:all .15s;display:inline-flex;align-items:center;gap:.4rem}
  .btn-purple{background:var(--accent);color:white}
  .btn-purple:hover{background:#6d28d9}
  .btn-red{background:var(--red);color:white}
  .btn-red:hover{background:#dc2626}
  .btn-cyan{background:var(--accent2);color:#0a0a0f}
  .btn-cyan:hover{background:#0891b2}
  .btn:disabled{opacity:.4;cursor:not-allowed}
  .help{font-size:.7rem;color:var(--muted);margin-top:.2rem}

  /* TOAST */
  #toast{position:fixed;bottom:1.5rem;right:1.5rem;padding:.65rem 1rem;border-radius:8px;font-size:.8rem;font-weight:500;z-index:999;display:none;animation:fadeUp .25s}
  .t-ok{background:#14532d;color:var(--green)}
  .t-err{background:#450a0a;color:var(--red)}
  .t-info{background:#1e3a5f;color:var(--accent2)}
  @keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

  @media(max-width:640px){
    .sidebar{width:220px}
    .bottom-input{width:180px}
  }
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-left">
    <div class="logo">📹 CCTV <span>Yogyakarta</span></div>
    <span class="cam-count" id="camCount">148 kamera</span>
  </div>
  <span class="badge off" id="streamBadge">○ OFF</span>
</div>

<div class="layout">
  <!-- SIDEBAR -->
  <div class="sidebar">
    <div class="sidebar-header">
      <input class="search" id="searchInput" placeholder="🔍 Cari kamera..." oninput="filterCams()">
      <div class="cat-filter" id="catFilter"></div>
    </div>
    <div class="cam-list" id="camList"></div>
  </div>

  <!-- MAIN -->
  <div class="main">
    <div class="player-wrap">
      <video id="video" autoplay muted playsinline></video>
      <div class="player-overlay" id="playerOverlay">
        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"/>
        </svg>
        <p>Pilih kamera dari daftar</p>
      </div>
      <div class="player-info" id="playerInfo" style="display:none">
        <span class="player-title" id="playerTitle">-</span>
        <div class="player-actions">
          <button class="icon-btn" onclick="reloadStream()">🔄 Reload</button>
          <button class="icon-btn" id="btnPause" onclick="togglePause()">⏸ Pause</button>
          <button class="icon-btn" id="btnHide" onclick="toggleHidePlayer()">🙈 Hide</button>
          <button class="icon-btn" onclick="toggleMute()">🔇</button>
          <button class="icon-btn" onclick="toggleFullscreen()">⛶</button>
        </div>
      </div>
    </div>

    <div class="bottom">
      <div class="panel-title">
        🎮 Stream Control
        <small id="streamCamLabel"></small>
      </div>

      <div class="panel-grid">
        <div class="form-group">
          <label class="form-label">YouTube RTMP URL</label>
          <input class="form-input" id="rtmpUrl" placeholder="rtmp://a.rtmp.youtube.com/live2/xxxx-xxxx-xxxx-xxxx">
          <span class="help">💡 Dapatkan dari YouTube Studio → Go Live → Stream Key</span>
        </div>

        <div class="form-group">
          <label class="form-label">Bitrate (kbps)</label>
          <input class="form-input" id="bitrate" type="number" min="500" max="8000" step="100" value="2000" placeholder="2000">
          <span class="help">500-8000 kbps (default: 2000)</span>
        </div>

        <div class="form-group">
          <label class="form-label">Kamera Terpilih</label>
          <input class="form-input" id="selectedCam" value="-" readonly>
          <span class="help">Klik kamera di sidebar untuk memilih</span>
        </div>

        <div class="form-group">
          <label class="form-label">🎵 Music Overlay</label>
          <select class="form-input" id="musicFile" onchange="onMusicChange()">
            <option value="">🔇 Tidak ada (CCTV audio only)</option>
          </select>
          <span class="help" id="musicHelp">Pilih lagu dari folder music/</span>
        </div>
      </div>

      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Status Stream</span>
          <span class="info-value off" id="statusText">🔴 Offline</span>
        </div>
        <div class="info-item">
          <span class="info-label">Mode</span>
          <span class="info-value">Relay (switch tanpa putus)</span>
        </div>
        <div class="info-item">
          <span class="info-label">Preview</span>
          <span class="info-value">Browser HLS (hls.js)</span>
        </div>
      </div>

      <div class="actions">
        <button class="btn btn-purple" id="btnStart" onclick="startStream()">▶ Start Stream</button>
        <button class="btn btn-red" id="btnStop" onclick="stopStream()" disabled>⏹ Stop Stream</button>
        <button class="btn btn-cyan" onclick="saveSettings()">💾 Simpan Setting</button>
      </div>
    </div>
  </div>
</div>

<div id="toast"></div>

<script>
// ── DATA ──────────────────────────────────────────────────────────────────────
const CAMERAS = CAMERAS_DATA;
const CAT_LABELS = CAT_LABELS_DATA;

// ── STATE ─────────────────────────────────────────────────────────────────────
let activeCamId = null;
let activeCat = 'all';
let hls = null;
let muted = true;

// ── INIT ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildCatFilter();
  renderList();
  loadStatus();
  loadMusicList();
  setInterval(loadStatus, 15000);
});

function loadMusicList() {
  fetch('/api/music').then(r => r.json()).then(d => {
    if (!d.success) return;
    const sel = document.getElementById('musicFile');
    sel.innerHTML = '<option value="">🔇 Tidak ada (CCTV audio only)</option>';
    d.files.forEach(f => {
      const opt = document.createElement('option');
      opt.value = f.path;
      opt.textContent = f.name + ' (' + f.size_mb + 'MB)';
      sel.appendChild(opt);
    });
  }).catch(() => {});
}

function onMusicChange() {
  const sel = document.getElementById('musicFile');
  const help = document.getElementById('musicHelp');
  if (sel.value) {
    help.textContent = '✅ ' + sel.options[sel.selectedIndex].text;
  } else {
    help.textContent = 'Pilih lagu dari folder music/';
  }
}

function loadStatus() {
  fetch('/status').then(r => r.json()).then(d => {
    document.getElementById('rtmpUrl').value = d.youtube_rtmp_val || '';
    document.getElementById('selectedCam').value = d.selected_camera_name || '-';
    if (d.bitrate) document.getElementById('bitrate').value = d.bitrate;
    if (d.music_file) {
      const sel = document.getElementById('musicFile');
      sel.value = d.music_file;
      const opt = sel.options[sel.selectedIndex];
      if (opt && opt.value) {
        document.getElementById('musicHelp').textContent = '✅ ' + opt.text;
      }
    }
    updateStreamBadge(d.stream_active);
    document.getElementById('btnStart').disabled = d.stream_active;
    document.getElementById('btnStop').disabled = !d.stream_active;
    if (d.selected_camera_id && !activeCamId) {
      selectCamera(d.selected_camera_id, false);
    }
  }).catch(() => {});
}

// ── CATEGORY FILTER ───────────────────────────────────────────────────────────
function buildCatFilter() {
  const cats = [...new Set(CAMERAS.map(c => c.cat))];
  const wrap = document.getElementById('catFilter');
  const all = document.createElement('button');
  all.className = 'cat-btn active';
  all.textContent = 'Semua';
  all.onclick = () => setCat('all', all);
  wrap.appendChild(all);
  cats.forEach(cat => {
    const btn = document.createElement('button');
    btn.className = 'cat-btn';
    const label = CAT_LABELS[cat] || ('Kat ' + cat);
    btn.textContent = label.replace(/^[^\s]+\s/, ''); // strip emoji
    btn.onclick = () => setCat(cat, btn);
    wrap.appendChild(btn);
  });
}

function setCat(cat, btn) {
  activeCat = cat;
  document.querySelectorAll('.cat-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderList();
}

// ── RENDER LIST ───────────────────────────────────────────────────────────────
function renderList() {
  const q = document.getElementById('searchInput').value.toLowerCase();
  const list = document.getElementById('camList');
  list.innerHTML = '';

  const filtered = CAMERAS.filter(c => {
    const matchCat = activeCat === 'all' || c.cat === activeCat;
    const matchQ = !q || c.title.toLowerCase().includes(q);
    return matchCat && matchQ;
  });

  document.getElementById('camCount').textContent = filtered.length + ' kamera';

  // Group by cat
  const groups = {};
  filtered.forEach(c => {
    if (!groups[c.cat]) groups[c.cat] = [];
    groups[c.cat].push(c);
  });

  Object.entries(groups).forEach(([cat, cams]) => {
    if (activeCat === 'all') {
      const lbl = document.createElement('div');
      lbl.className = 'cat-label';
      lbl.textContent = CAT_LABELS[cat] || ('Kategori ' + cat);
      list.appendChild(lbl);
    }
    cams.forEach(cam => {
      const el = document.createElement('div');
      el.className = 'cam-item' + (String(cam.id) === String(activeCamId) ? ' active' : '');
      el.id = 'cam-' + cam.id;
      el.innerHTML = `
        <div class="cam-dot dot-${cam.status === '0' ? '0' : cam.status === '2' ? '2' : 'other'}"></div>
        <span class="cam-name">${cam.title}</span>
      `;
      el.onclick = () => selectCamera(cam.id, true);
      list.appendChild(el);
    });
  });
}

function filterCams() { renderList(); }

// ── SELECT CAMERA ─────────────────────────────────────────────────────────────
function selectCamera(id, notify) {
  activeCamId = String(id);

  // Update active class
  document.querySelectorAll('.cam-item').forEach(el => el.classList.remove('active'));
  const el = document.getElementById('cam-' + id);
  if (el) {
    el.classList.add('active');
    el.scrollIntoView({block: 'nearest'});
  }

  const cam = CAMERAS.find(c => String(c.id) === String(id));
  if (!cam) return;

  // Update selected cam input
  document.getElementById('selectedCam').value = cam.title;
  document.getElementById('streamCamLabel').textContent = '📡 ' + cam.title;

  // Update player
  loadHLS(cam.link, cam.title);

  // Notify backend
  fetch('/select_camera', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({camera_id: id})
  }).then(r => r.json()).then(d => {
    if (notify) showToast(d.message, d.success ? 'ok' : 'err');
  }).catch(() => {});
}

// ── HLS PLAYER ────────────────────────────────────────────────────────────────
function loadHLS(url, title) {
  const video = document.getElementById('video');
  document.getElementById('playerOverlay').classList.add('hidden');
  document.getElementById('playerInfo').style.display = 'flex';
  document.getElementById('playerTitle').textContent = title;
  document.getElementById('streamCamLabel').textContent = '📡 ' + title;

  if (hls) { hls.destroy(); hls = null; }

  if (Hls.isSupported()) {
    hls = new Hls({
      enableWorker: true,
      lowLatencyMode: true,
      backBufferLength: 30
    });
    hls.loadSource(url);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, () => video.play().catch(() => {}));
    hls.on(Hls.Events.ERROR, (e, data) => {
      if (data.fatal) showToast('Stream error: ' + data.type, 'err');
    });
  } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
    video.src = url;
    video.play().catch(() => {});
  }
}

function reloadStream() {
  if (!activeCamId) return;
  const cam = CAMERAS.find(c => String(c.id) === String(activeCamId));
  if (cam) loadHLS(cam.link, cam.title);
}

function toggleMute() {
  const video = document.getElementById('video');
  muted = !muted;
  video.muted = muted;
  document.querySelector('.icon-btn[onclick="toggleMute()"]').textContent = muted ? '🔇' : '🔊';
}

function toggleFullscreen() {
  const wrap = document.querySelector('.player-wrap');
  if (!document.fullscreenElement) wrap.requestFullscreen();
  else document.exitFullscreen();
}

let paused = false;
function togglePause() {
  const video = document.getElementById('video');
  const btn = document.getElementById('btnPause');
  if (paused) {
    video.play().catch(() => {});
    btn.textContent = '⏸ Pause';
    paused = false;
  } else {
    video.pause();
    btn.textContent = '▶ Play';
    paused = true;
  }
}

let hidden = false;
function toggleHidePlayer() {
  const wrap = document.querySelector('.player-wrap');
  const btn = document.getElementById('btnHide');
  if (hidden) {
    wrap.style.display = '';
    btn.textContent = '🙈 Hide';
    hidden = false;
  } else {
    wrap.style.display = 'none';
    btn.textContent = '👁 Show';
    hidden = true;
  }
}

// ── STREAM CONTROL ────────────────────────────────────────────────────────────
function startStream() {
  const rtmp = document.getElementById('rtmpUrl').value.trim();
  if (!rtmp) { showToast('Isi YouTube RTMP URL dulu', 'err'); return; }
  if (!activeCamId) { showToast('Pilih kamera dulu', 'err'); return; }
  const bitrate = parseInt(document.getElementById('bitrate').value) || 2000;
  const music_file = document.getElementById('musicFile').value;
  document.getElementById('btnStart').disabled = true;
  fetch('/start', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({youtube_rtmp: rtmp, camera_id: activeCamId, bitrate: bitrate, music_file: music_file})
  }).then(r => r.json()).then(d => {
    showToast(d.message, d.success ? 'ok' : 'err');
    if (d.success) { updateStreamBadge(true); document.getElementById('btnStop').disabled = false; }
    else document.getElementById('btnStart').disabled = false;
  }).catch(() => { document.getElementById('btnStart').disabled = false; });
}

function stopStream() {
  fetch('/stop', {method: 'POST'}).then(r => r.json()).then(d => {
    showToast(d.message, d.success ? 'ok' : 'err');
    if (d.success) {
      updateStreamBadge(false);
      document.getElementById('btnStart').disabled = false;
      document.getElementById('btnStop').disabled = true;
    }
  });
}

function saveSettings() {
  const bitrate = parseInt(document.getElementById('bitrate').value) || 2000;
  const music_file = document.getElementById('musicFile').value;
  fetch('/save_settings', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({youtube_rtmp: document.getElementById('rtmpUrl').value, bitrate: bitrate, music_file: music_file})
  }).then(r => r.json()).then(d => showToast(d.message, 'ok'));
}

function updateStreamBadge(active) {
  const b = document.getElementById('streamBadge');
  b.className = 'badge ' + (active ? 'live' : 'off');
  b.textContent = active ? '● LIVE' : '○ OFF';
}

// ── TOAST ─────────────────────────────────────────────────────────────────────
let toastTimer;
function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.className = 't-' + (type || 'ok');
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.style.display = 'none', 3000);
}
</script>
</body>
</html>
"""

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    # Inject camera data + cat labels as JS
    cameras_js = json.dumps(CAMERAS, ensure_ascii=False)
    cat_labels_js = json.dumps(CAT_LABELS, ensure_ascii=False)
    html = HTML.replace('CAMERAS_DATA', cameras_js).replace('CAT_LABELS_DATA', cat_labels_js)
    return Response(html, mimetype='text/html')

@app.route('/status')
def stream_status():
    active = relay_process is not None and relay_process.poll() is None
    config["stream_active"] = active
    save_config(config)
    selected_id = config.get("selected_camera_id", "14")
    cam = get_camera_by_id(selected_id)
    return jsonify({
        "stream_active": active,
        "selected_camera_id": selected_id,
        "selected_camera_name": cam['title'] if cam else "-",
        "youtube_rtmp_val": config.get("youtube_rtmp", ""),
        "bitrate": config.get("bitrate", "2000"),
        "music_file": config.get("music_file", "")
    })

@app.route('/select_camera', methods=['POST'])
def select_camera():
    cam_id = str(request.json.get('camera_id', ''))
    cam = get_camera_by_id(cam_id)
    if not cam:
        return jsonify({"success": False, "message": "Kamera tidak ditemukan"})
    config["selected_camera_id"] = cam_id
    save_config(config)
    # If streaming, restart with new camera
    is_live = relay_process is not None and relay_process.poll() is None
    if is_live:
        rtmp = config.get('youtube_rtmp', '')
        bitrate = int(config.get('bitrate', 2000))
        music_file = config.get('music_file', '')
        with stream_lock:
            ok = start_stream_direct(cam['link'], rtmp, bitrate, music_file)
            if ok:
                return jsonify({"success": True, "message": f"🔄 Ganti ke {cam['title']}"})
            return jsonify({"success": False, "message": "Gagal restart stream"})
    return jsonify({"success": True, "message": f"✅ {cam['title']} dipilih"})

@app.route('/save_settings', methods=['POST'])
def save_settings():
    data = request.json or {}
    if 'youtube_rtmp' in data:
        config["youtube_rtmp"] = data['youtube_rtmp']
    if 'bitrate' in data:
        config["bitrate"] = str(data['bitrate'])
    if 'music_file' in data:
        config["music_file"] = data['music_file']
    save_config(config)
    return jsonify({"success": True, "message": "Setting disimpan ✅"})

@app.route('/api/music')
def api_music():
    return jsonify({"success": True, "files": get_music_files()})

@app.route('/start', methods=['POST'])
def start_stream_route():
    global relay_process
    data = request.get_json(silent=True) or {}
    rtmp = data.get('youtube_rtmp') or config.get('youtube_rtmp', '')
    cam_id = data.get('camera_id') or config.get('selected_camera_id', '14')
    bitrate = int(data.get('bitrate', config.get('bitrate', 2000)))
    music_file = data.get('music_file', config.get('music_file', ''))
    if not rtmp:
        return jsonify({"success": False, "message": "YouTube RTMP URL belum diisi"})
    cam = get_camera_by_id(cam_id)
    if not cam:
        return jsonify({"success": False, "message": "Kamera tidak ditemukan"})
    config["youtube_rtmp"] = rtmp
    config["selected_camera_id"] = str(cam_id)
    config["bitrate"] = str(bitrate)
    config["music_file"] = music_file
    save_config(config)
    with stream_lock:
        ok = start_stream_direct(cam['link'], rtmp, bitrate, music_file)
        if not ok:
            return jsonify({"success": False, "message": "ffmpeg start gagal"})
    config["stream_active"] = True
    save_config(config)
    music_label = os.path.basename(music_file) if music_file else "no music"
    return jsonify({"success": True, "message": f"▶ Streaming {cam['title']} @ {bitrate}kbps ({music_label})"})

@app.route('/stop', methods=['POST'])
def stop_stream_route():
    kill_all()
    config["stream_active"] = False
    save_config(config)
    return jsonify({"success": True, "message": "⏹ Streaming dihentikan"})

if __name__ == '__main__':
    print("CCTV Dashboard running on http://0.0.0.0:5050")
    app.run(host='0.0.0.0', port=5050, debug=False, threaded=True)

/**
 * VidPro Extension — Popup Logic
 */

const VIDPRO_BASE = "http://127.0.0.1:8767";

// ── Supported platforms ──────────────────────────────────────────────────────
const SUPPORTED_PLATFORMS = [
  { match: ["youtube.com", "youtu.be"],   name: "YouTube",   emoji: "▶" },
  { match: ["tiktok.com"],                name: "TikTok",    emoji: "♪" },
  { match: ["instagram.com"],             name: "Instagram", emoji: "◉" },
  { match: ["twitter.com", "x.com"],      name: "Twitter/X", emoji: "✕" },
  { match: ["vimeo.com"],                 name: "Vimeo",     emoji: "◈" },
  { match: ["twitch.tv"],                 name: "Twitch",    emoji: "⬡" },
  { match: ["dailymotion.com"],           name: "Dailymotion", emoji: "◎" },
  { match: ["reddit.com"],               name: "Reddit",    emoji: "◉" },
  { match: ["facebook.com", "fb.watch"], name: "Facebook",  emoji: "f" },
];

// ── State ────────────────────────────────────────────────────────────────────
let state = {
  connected: false,
  currentUrl: "",
  currentTab: null,
  pageMeta: null,
  quality: "best",
  out_format: "mp4",
  audio_only: false,
  subtitle: false,
  thumbnail: false,
  no_overwrite: false,
  metadata: false,
  sending: false,
  platform: null,
  cookies_from_browser: "",
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const statusBadge    = $("statusBadge");
const statusText     = $("statusText");
const stateOffline   = $("stateOffline");
const stateNoVideo   = $("stateNoVideo");
const previewCard    = $("previewCard");
const previewThumb   = $("previewThumb");
const previewNoThumb = $("previewNoThumb");
const platformBadge  = $("platformBadge");
const previewTitle   = $("previewTitle");
const previewAuthor  = $("previewAuthor");
const settingsPanel  = $("settingsPanel");
const btnDownload    = $("btnDownload");
const btnDownloadTxt = $("btnDownloadText");
const jobsSection    = $("jobsSection");
const jobsList       = $("jobsList");
const jobsCount      = $("jobsCount");
const toast          = $("toast");
const toastMsg       = $("toastMsg");
const toastIcon      = $("toastIcon");

// ── Helpers ──────────────────────────────────────────────────────────────────

function detectPlatform(url) {
  try {
    const host = new URL(url).hostname.replace("www.", "");
    return SUPPORTED_PLATFORMS.find(p => p.match.some(m => host === m || host.endsWith("." + m))) || null;
  } catch (_) { return null; }
}

function isSupportedUrl(url) {
  if (!url || url.startsWith("chrome://") || url.startsWith("about:")) return false;
  // Accept any http/https URL — VidPro supports 1000+ sites
  return url.startsWith("http://") || url.startsWith("https://");
}

function showToast(msg, type = "success", icon = "✓") {
  toastMsg.textContent = msg;
  toastIcon.textContent = icon;
  toast.className = `toast ${type}`;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 3000);
}

function setClass(el, ...args) { el.className = args.join(" "); }

// ── Connection check ─────────────────────────────────────────────────────────

async function checkConnection() {
  statusBadge.className = "status-badge loading";
  statusText.textContent = "Checking…";
  try {
    const resp = await fetch(`${VIDPRO_BASE}/jobs`, { signal: AbortSignal.timeout(2500) });
    if (resp.ok) {
      state.connected = true;
      statusBadge.className = "status-badge connected";
      statusText.textContent = "Connected";
      return true;
    }
  } catch (_) {}
  state.connected = false;
  statusBadge.className = "status-badge offline";
  statusText.textContent = "Offline";
  return false;
}

// ── UI rendering ─────────────────────────────────────────────────────────────

function renderUI() {
  // Hide all states first
  stateOffline.classList.add("hidden");
  stateNoVideo.classList.add("hidden");
  previewCard.classList.add("hidden");
  settingsPanel.classList.add("hidden");
  btnDownload.disabled = true;

  if (!state.connected) {
    stateOffline.classList.remove("hidden");
    return;
  }

  const supported = isSupportedUrl(state.currentUrl);
  if (!supported) {
    stateNoVideo.classList.remove("hidden");
    return;
  }

  // Show preview
  previewCard.classList.remove("hidden");
  settingsPanel.classList.remove("hidden");

  // Platform badge
  state.platform = detectPlatform(state.currentUrl);
  if (state.platform) {
    platformBadge.textContent = `${state.platform.emoji} ${state.platform.name}`;
  } else {
    platformBadge.textContent = "🌐 Web";
  }

  // Thumbnail
  if (state.pageMeta?.thumbnail) {
    previewThumb.src = state.pageMeta.thumbnail;
    previewThumb.classList.remove("hidden");
    previewNoThumb.classList.add("hidden");
    previewThumb.onerror = () => {
      previewThumb.classList.add("hidden");
      previewNoThumb.classList.remove("hidden");
    };
  } else {
    previewThumb.classList.add("hidden");
    previewNoThumb.classList.remove("hidden");
  }

  // Title & author
  previewTitle.textContent = state.pageMeta?.title || state.currentUrl;
  previewAuthor.textContent = state.pageMeta?.channel || state.platform?.name || "—";

  // Enable button
  btnDownload.disabled = state.sending;

  // Audio quality note: if audio chip active, disable format row
  const audioActive = state.quality === "audio";
  document.getElementById("formatRow").style.opacity = audioActive ? "0.4" : "1";
  document.getElementById("formatRow").style.pointerEvents = audioActive ? "none" : "";
}

// ── Load page meta from content script ───────────────────────────────────────

async function loadPageMeta(tab) {
  if (!tab || !tab.id || tab.id === chrome.tabs.TAB_ID_NONE) return;
  
  try {
    // We wrap this to catch the "message channel closed" error specifically
    const meta = await chrome.tabs.sendMessage(tab.id, { action: "getPageMeta" });
    state.pageMeta = meta || null;
  } catch (err) {
    // This is expected if the page is in bfcache or content script isn't ready
    // The error message usually contains "Could not establish connection" or "message channel closed"
    if (err.message.includes("Could not establish connection") || 
        err.message.includes("message channel closed") ||
        err.message.includes("Receiving end does not exist")) {
      console.debug("VidPro: Could not get page meta (normal if page is cached or restricted):", err.message);
    } else {
      // Log unexpected errors
      console.warn("VidPro: Unexpected error getting page meta:", err);
    }
    state.pageMeta = null;
  }
}

// ── Settings persistence ──────────────────────────────────────────────────────

async function loadSettings() {
  const saved = await chrome.storage.local.get([
    "quality", "out_format", "audio_only",
    "subtitle", "thumbnail", "no_overwrite", "metadata"
  ]);
  if (saved.quality)     state.quality     = saved.quality;
  if (saved.out_format)  state.out_format  = saved.out_format;
  if (typeof saved.audio_only  === "boolean") state.audio_only  = saved.audio_only;
  if (typeof saved.subtitle    === "boolean") state.subtitle    = saved.subtitle;
  if (typeof saved.thumbnail   === "boolean") state.thumbnail   = saved.thumbnail;
  if (typeof saved.no_overwrite === "boolean") state.no_overwrite = saved.no_overwrite;
  if (typeof saved.metadata    === "boolean") state.metadata    = saved.metadata;
  
  // Fetch browser selection from VidPro Server (Shared)
  try {
    const r = await fetch(`${VIDPRO_BASE}/settings`);
    if (r.ok) {
      const s = await r.json();
      if (s.cookies_from_browser !== undefined) {
        state.cookies_from_browser = s.cookies_from_browser;
      }
    }
  } catch(e) {}
}

async function saveSettings() {
  chrome.storage.local.set({
    quality:      state.quality,
    out_format:   state.out_format,
    audio_only:   state.audio_only,
    subtitle:     state.subtitle,
    thumbnail:    state.thumbnail,
    no_overwrite: state.no_overwrite,
    metadata:     state.metadata,
  });

  // Save browser selection to VidPro Server (Shared)
  try {
    await fetch(`${VIDPRO_BASE}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cookies_from_browser: state.cookies_from_browser })
    });
  } catch(e) {}
}

function applySettingsToUI() {
  // Quality chips
  document.querySelectorAll(".quality-chip").forEach(chip => {
    chip.classList.toggle("active", chip.dataset.value === state.quality);
  });
  // Format chips
  const fmtVal = state.audio_only ? "mp3" : state.out_format;
  document.querySelectorAll(".format-chip").forEach(chip => {
    chip.classList.toggle("active", chip.dataset.value === fmtVal);
  });
  // Toggles
  ["subtitle", "thumbnail", "no_overwrite", "metadata"].forEach(key => {
    const el = document.querySelector(`[data-key="${key}"]`);
    if (el) el.classList.toggle("active", !!state[key]);
  });
  // Browser select
  const browserEl = $("selectBrowserCookies");
  if (browserEl) browserEl.value = state.cookies_from_browser;
}

// ── Quality / Format / Toggle events ─────────────────────────────────────────

function initControls() {
  // Quality chips
  document.querySelectorAll(".quality-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const val = chip.dataset.value;
      state.quality = val;
      if (val === "audio") {
        state.audio_only = true;
        state.quality = "audio";
      } else {
        state.audio_only = false;
      }
      document.querySelectorAll(".quality-chip").forEach(c =>
        c.classList.toggle("active", c.dataset.value === val));
      // Format row dim
      const audioActive = val === "audio";
      document.getElementById("formatRow").style.opacity = audioActive ? "0.4" : "1";
      document.getElementById("formatRow").style.pointerEvents = audioActive ? "none" : "";
      saveSettings();
    });
  });

  // Format chips
  document.querySelectorAll(".format-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const val = chip.dataset.value;
      if (val === "mp3") {
        state.audio_only = true;
        state.quality = "audio";
        document.querySelectorAll(".quality-chip").forEach(c =>
          c.classList.toggle("active", c.dataset.value === "audio"));
      } else {
        state.audio_only = false;
        state.out_format = val;
        if (state.quality === "audio") {
          state.quality = "best";
          document.querySelectorAll(".quality-chip").forEach(c =>
            c.classList.toggle("active", c.dataset.value === "best"));
        }
        document.getElementById("formatRow").style.opacity = "1";
        document.getElementById("formatRow").style.pointerEvents = "";
      }
      document.querySelectorAll(".format-chip").forEach(c =>
        c.classList.toggle("active", c.dataset.value === val));
      saveSettings();
    });
  });

  // Toggles
  document.querySelectorAll(".toggle-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const key = chip.dataset.key;
      state[key] = !state[key];
      chip.classList.toggle("active", state[key]);
      saveSettings();
    });
  });

  // Browser select change
  const browserEl = $("selectBrowserCookies");
  if (browserEl) {
    browserEl.addEventListener("change", (e) => {
      state.cookies_from_browser = e.target.value;
      saveSettings();
    });
  }

  // Poll for settings sync (Shared across UIs)
  setInterval(async () => {
    try {
      const r = await fetch(`${VIDPRO_BASE}/settings`);
      if (r.ok) {
        const s = await r.json();
        if (s.cookies_from_browser !== undefined && s.cookies_from_browser !== state.cookies_from_browser) {
          state.cookies_from_browser = s.cookies_from_browser;
          if (browserEl) browserEl.value = state.cookies_from_browser;
        }
      }
    } catch(e) {}
  }, 3000);
}

// ── Download ──────────────────────────────────────────────────────────────────

async function startDownload() {
  if (state.sending || !state.connected || !isSupportedUrl(state.currentUrl)) return;

  state.sending = true;
  btnDownload.disabled = true;
  btnDownload.classList.add("sending");
  btnDownloadTxt.textContent = "Sending…";
  btnDownload.innerHTML = `<div class="spinner"></div><span>Sending…</span>`;

  const payload = {
    url:          state.currentUrl,
    quality:      state.audio_only ? "best" : state.quality,
    out_format:   state.out_format,
    audio_only:   state.audio_only ? "true" : "false",
    subtitle:     state.subtitle ? "true" : "false",
    subtitle_langs: "en",
    subtitle_format: "",
    embed_subtitles: "false",
    only_subtitles: "false",
    thumbnail:    state.thumbnail ? "true" : "false",
    metadata:     state.metadata ? "true" : "false",
    output_dir:   "./downloads",
    no_overwrite: state.no_overwrite ? "true" : "false",
    cookies_from_browser: state.cookies_from_browser,
    archive:      "",
    clip_start:   "",
    clip_end:     "",
    cookies_file: "",
    proxy:        "",
    user_agent:   "",
    referer:      "",
    headers_json: "",
  };

  try {
    const body = new URLSearchParams(payload);
    const resp = await fetch(`${VIDPRO_BASE}/download`, {
      method: "POST",
      body,
      signal: AbortSignal.timeout(10000),
    });
    const data = await resp.json();

    if (data.job_id || data.playlist_id) {
      showToast("Download started! ✓", "success", "✓");
      jobsSection.classList.remove("hidden");
    } else {
      showToast("Failed to start download", "error", "✕");
    }
  } catch (err) {
    showToast("Connection failed. Is VidPro running?", "error", "✕");
  }

  state.sending = false;
  btnDownload.disabled = false;
  btnDownload.classList.remove("sending");
  btnDownload.innerHTML = `
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
      <polyline points="7 10 12 15 17 10"/>
      <line x1="12" y1="15" x2="12" y2="3"/>
    </svg>
    <span>Send to VidPro</span>`;
}

// ── Jobs polling ──────────────────────────────────────────────────────────────

function parsePercent(str) {
  if (!str) return 0;
  const n = parseFloat(str.replace("%", ""));
  return isNaN(n) ? 0 : Math.min(n, 100);
}

function renderJobs(jobs) {
  const entries = Object.entries(jobs).filter(([, j]) => {
    // Include all statuses now, not just specific ones
    const status = j.status || "queued";
    return status !== "not_found" && status !== "cancelled";
  });

  // Sort: running first, then queued, then paused, then done/error/skipped (most recent)
  entries.sort(([, a], [, b]) => {
    const ord = { running: 0, queued: 1, paused: 2, done: 3, error: 4, skipped: 5 };
    const statusA = a.status || "queued";
    const statusB = b.status || "queued";
    return (ord[statusA] ?? 6) - (ord[statusB] ?? 6);
  });

  const active = entries.filter(([, j]) => {
    const status = j.status || "queued";
    return ["running", "queued", "paused"].includes(status);
  });
  
  // Show recent items that are NOT already in active (to avoid duplicates)
  const recent = entries.filter(([, j]) => {
    const status = j.status || "queued";
    return !["running", "queued", "paused"].includes(status);
  }).slice(0, 8);
  
  // Combine active and recent without duplicates
  const displayed = [...active, ...recent].slice(0, 8);

  jobsCount.textContent = active.length;

  if (displayed.length === 0) {
    jobsList.innerHTML = `<div class="jobs-empty">No active downloads</div>`;
    return;
  }

  jobsList.innerHTML = displayed.map(([id, job]) => {
    const pct = parsePercent(job.progress);
    const status = job.status || "queued";
    const title = job.title || job.url || `Job #${id}`;
    const barClass = status === "done" ? "done" : status === "error" ? "error" : status === "skipped" ? "skipped" : "";
    const speedStr = job.speed ? `<span class="job-speed">${job.speed}</span>` : "";
    
    // Special handling for playlist items
    let displayTitle = title;
    if (id.startsWith("playlist_") && !id.includes("_item_")) {
      displayTitle = `🎵 ${title}`;
    } else if (id.includes("_item_")) {
      displayTitle = `├─ ${title}`;
    }

    return `<div class="job-card">
      <div class="job-card-header">
        <div class="job-title" title="${title}">${displayTitle}</div>
        <div class="job-status-badge ${status}">${status}</div>
      </div>
      <div class="job-progress-bar-wrap">
        <div class="job-progress-bar ${barClass}" style="width:${pct}%"></div>
      </div>
      <div class="job-card-footer">
        <span class="job-progress-text">${job.progress || "0%"}</span>
        <div style="display:flex; align-items:center; gap:8px;">
            ${speedStr}
            <button class="btn-job-action btn-open-folder" data-id="${id}" data-type="${job.type || 'job'}" title="Open Folder">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
            </button>
        </div>
      </div>
    </div>`;
  }).join("");

  // Attach event listeners (Inline onclick is blocked by CSP in Chrome Extensions)
  document.querySelectorAll(".btn-open-folder").forEach(btn => {
    btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openFolder(btn.dataset.id, btn.dataset.type);
    });
  });
}

async function pollJobs() {
  if (!state.connected) return;
  try {
    // Fetch both jobs and playlists
    const [jobsResp, playlistsResp] = await Promise.allSettled([
      fetch(`${VIDPRO_BASE}/jobs`, { signal: AbortSignal.timeout(3000) }),
      fetch(`${VIDPRO_BASE}/playlists`, { signal: AbortSignal.timeout(3000) })
    ]);

    let combinedJobs = {};
    
    // Process jobs
    if (jobsResp.status === 'fulfilled') {
      const jobs = await jobsResp.value.json();
      combinedJobs = { ...jobs };
    }
    
    // Process playlists and convert them to job-like objects
    if (playlistsResp.status === 'fulfilled') {
      const playlists = await playlistsResp.value.json();
      for (const [id, playlist] of Object.entries(playlists)) {
        // Add the playlist itself as a job-like entry
        combinedJobs[`playlist_${id}`] = {
          title: playlist.title || `Playlist #${id}`,
          url: playlist.url,
          status: playlist.status,
          progress: playlist.overall_progress || "0%",
          speed: playlist.speed || "",
          type: "playlist"
        };
        
        // Add individual playlist items as separate entries
        if (playlist.items) {
          for (const item of playlist.items) {
            combinedJobs[`playlist_${id}_item_${item.index}`] = {
              title: item.title || `Item ${item.index}`,
              url: playlist.url,
              status: item.status,
              progress: item.progress || "0%",
              speed: playlist.speed || "",
              type: "playlist_item"
            };
          }
        }
      }
    }

    const hasAny = Object.keys(combinedJobs).length > 0;
    if (hasAny) jobsSection.classList.remove("hidden");
    renderJobs(combinedJobs);
  } catch (error) {
    console.error("Error polling jobs:", error);
  }
}

async function openFolder(id, type = "job") {
  try {
    // Handle different ID formats
    if (id.startsWith("playlist_")) {
      // Extract playlist ID from "playlist_X" or "playlist_X_item_Y"
      const playlistId = id.split("_")[1].split("_")[0];
      await fetch(`${VIDPRO_BASE}/playlists/${playlistId}/open-folder`, { method: "POST" });
    } else {
      // Regular job
      await fetch(`${VIDPRO_BASE}/jobs/${id}/open-folder`, { method: "POST" });
    }
  } catch (err) {
    showToast("Failed to open folder", "error", "✕");
  }
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  // Load settings first
  await loadSettings();

  // Get current tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  state.currentTab = tab;
  state.currentUrl = tab?.url || "";

  // Check server connection
  const connected = await checkConnection();
  state.connected = connected;

  if (connected) {
    // Load page metadata
    await loadPageMeta(tab);
  }

  // Apply saved settings to UI
  applySettingsToUI();

  // Render
  renderUI();

  // Init controls
  initControls();

  // Download button
  btnDownload.addEventListener("click", startDownload);

  // Open UI button
  $("btnOpenUI").addEventListener("click", () => {
    chrome.tabs.create({ url: VIDPRO_BASE });
  });

  // Poll jobs if connected
  if (connected) {
    await pollJobs();
    setInterval(pollJobs, 2500);
  }
}

document.addEventListener("DOMContentLoaded", init);

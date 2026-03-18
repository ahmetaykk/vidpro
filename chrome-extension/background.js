/**
 * VidPro Background Service Worker
 */

const VIDPRO_BASE = "http://127.0.0.1:8767";

// When the extension is installed, set default settings
chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.local.set({
    quality: "best",
    out_format: "mp4",
    audio_only: false,
    subtitle: false,
    thumbnail: false,
    no_overwrite: false,
    output_dir: "./downloads",
  });
});

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "ping") {
    fetch(`${VIDPRO_BASE}/jobs`, { signal: AbortSignal.timeout(2000) })
      .then(() => sendResponse({ ok: true }))
      .catch(() => sendResponse({ ok: false }));
    return true; // async
  }

  if (request.action === "getJobs") {
    fetch(`${VIDPRO_BASE}/jobs`)
      .then(r => r.json())
      .then(data => sendResponse({ ok: true, data }))
      .catch(err => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (request.action === "startDownload") {
    const body = new URLSearchParams(request.payload);
    fetch(`${VIDPRO_BASE}/download`, { method: "POST", body })
      .then(r => r.json())
      .then(data => sendResponse({ ok: true, data }))
      .catch(err => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
  
  // Return true to indicate we will send a response asynchronously
  return true;
});

// Handle tab updates to detect navigation
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  // We can add logic here if needed when tabs are updated
});

// Handle tab removal to clean up any state if necessary
chrome.tabs.onRemoved.addListener((tabId, removeInfo) => {
  // Clean up any state related to this tab if necessary
});
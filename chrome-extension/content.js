/**
 * VidPro Content Script
 * Extracts page metadata (title, thumbnail, author) from the current page
 * and responds to messages from the popup.
 */

function getMetaContent(name) {
  const el =
    document.querySelector(`meta[property="${name}"]`) ||
    document.querySelector(`meta[name="${name}"]`);
  return el ? el.getAttribute("content") || "" : "";
}

function getPageMeta() {
  const url = window.location.href;
  const title =
    getMetaContent("og:title") ||
    getMetaContent("twitter:title") ||
    document.title ||
    "";
  const thumbnail =
    getMetaContent("og:image") ||
    getMetaContent("twitter:image") ||
    "";
  const author =
    getMetaContent("og:site_name") ||
    getMetaContent("twitter:site") ||
    "";

  // Platform-specific author extraction
  let channel = author;
  try {
    const host = new URL(url).hostname.replace("www.", "");
    if (host.includes("youtube.com") || host === "youtu.be") {
      const channelEl =
        document.querySelector('yt-formatted-string.ytd-channel-name a') ||
        document.querySelector('#channel-name a') ||
        document.querySelector('a.yt-simple-endpoint.ytd-video-owner-renderer');
      if (channelEl) channel = channelEl.textContent.trim();
    } else if (host.includes("tiktok.com")) {
      const userEl = document.querySelector('[data-e2e="browse-username"]') ||
        document.querySelector('h2[data-e2e="video-author-uniqueid"]');
      if (userEl) channel = userEl.textContent.trim();
    } else if (host.includes("instagram.com")) {
      const userEl = document.querySelector('header h2') ||
        document.querySelector('a[role="link"] span');
      if (userEl) channel = userEl.textContent.trim();
    }
  } catch (_) {}

  return { url, title, thumbnail, channel };
}

// Keep track of whether we're connected to the page
let isConnected = true;

// Listen for messages from the popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  // Check if we're still connected to the page
  if (!isConnected) {
    sendResponse({ error: "Content script is not connected to the page" });
    return true;
  }

  if (request.action === "getPageMeta") {
    sendResponse(getPageMeta());
  }
  return true;
});

// Handle page visibility changes to detect bfcache events
document.addEventListener('visibilitychange', () => {
  if (document.visibilityState === 'hidden') {
    // Page is being hidden, possibly entering bfcache
    isConnected = false;
  } else {
    // Page is visible again
    isConnected = true;
  }
});

// Handle page unload events
window.addEventListener('pagehide', () => {
  isConnected = false;
});

// Handle potential bfcache restoration
window.addEventListener('pageshow', (event) => {
  if (event.persisted) {
    // Page was restored from bfcache
    isConnected = true;
  }
});
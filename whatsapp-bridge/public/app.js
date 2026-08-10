/**
 * WhatsApp Bridge — Setup UI Client-Side Logic
 *
 * Handles mode switching, QR polling, Meta credential form,
 * test messages, and status polling.
 */

// ─── State ───
let currentMode = "webjs";
let qrPollTimer = null;
let statusPollTimer = null;

// ─── Init ───
document.addEventListener("DOMContentLoaded", () => {
  // Mode toggle buttons
  document.getElementById("btnWebjs").addEventListener("click", () => switchMode("webjs"));
  document.getElementById("btnMeta").addEventListener("click", () => switchMode("meta"));

  // Token eye toggle
  document.getElementById("toggleToken").addEventListener("click", () => {
    const input = document.getElementById("businessToken");
    input.type = input.type === "password" ? "text" : "password";
  });

  // Meta credentials form
  document.getElementById("metaForm").addEventListener("submit", saveMeta);

  // Fetch service token for test messages
  fetchServiceToken();

  // Load saved config if available
  loadSavedConfig();

  // Fetch initial status & decide mode
  fetchStatus();
  statusPollTimer = setInterval(fetchStatus, 5000);
});

// ─── Mode Switching ───
function switchMode(mode) {
  currentMode = mode;

  // Toggle active class
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });

  // Show/hide panels
  document.getElementById("panelWebjs").style.display = mode === "webjs" ? "block" : "none";
  document.getElementById("panelMeta").style.display = mode === "meta" ? "block" : "none";

  // Update test message label
  const label = document.getElementById("recipientLabel");
  const input = document.getElementById("testRecipient");
  if (mode === "webjs") {
    label.textContent = "Group ID";
    input.placeholder = "e.g. 120363012345678901@g.us";
  } else {
    label.textContent = "Phone Number (E.164)";
    input.placeholder = "e.g. 919876543210";
  }

  // QR polling
  if (mode === "webjs") {
    fetchQR();
    startQRPolling();
  } else {
    stopQRPolling();
  }
}

// ─── Status ───
async function fetchStatus() {
  const badge = document.getElementById("statusBadge");
  try {
    const res = await fetch("/health");
    const data = await res.json();

    badge.className = "status-badge " + (data.ready ? "ready" : "connecting");
    badge.querySelector(".status-text").textContent = data.ready
      ? `Ready (${data.mode})`
      : `Connecting (${data.mode || "…"})`;

    // Auto-detect mode from server
    if (data.mode && data.mode !== currentMode) {
      switchMode(data.mode);
    }
  } catch {
    badge.className = "status-badge offline";
    badge.querySelector(".status-text").textContent = "Offline";
  }
}

// ─── QR Code ───
async function fetchQR() {
  try {
    const res = await fetch("/api/qr");
    const data = await res.json();

    const container = document.getElementById("qrContainer");
    const placeholder = document.getElementById("qrPlaceholder");
    const img = document.getElementById("qrImage");

    if (data.qr) {
      img.src = data.qr;
      img.style.display = "block";
      placeholder.style.display = "none";
      container.classList.add("has-qr");
    } else if (data.authenticated) {
      placeholder.innerHTML = `
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        <p style="color: #22c55e; font-weight: 600; margin-top: 12px;">Authenticated ✓</p>
        <p class="qr-hint">WhatsApp session is active</p>
      `;
      placeholder.style.display = "block";
      img.style.display = "none";
      container.classList.remove("has-qr");
    } else {
      placeholder.innerHTML = `
        <div class="qr-spinner"></div>
        <p>Waiting for QR code…</p>
        <p class="qr-hint">The bridge must be running in <code>webjs</code> mode</p>
      `;
      placeholder.style.display = "block";
      img.style.display = "none";
      container.classList.remove("has-qr");
    }
  } catch {
    // Server down or not webjs mode
  }
}

function startQRPolling() {
  stopQRPolling();
  qrPollTimer = setInterval(fetchQR, 3000);
}

function stopQRPolling() {
  if (qrPollTimer) {
    clearInterval(qrPollTimer);
    qrPollTimer = null;
  }
}

// ─── Meta Credentials ───
async function saveMeta(e) {
  e.preventDefault();

  const phoneNumberId = document.getElementById("phoneNumberId").value.trim();
  const businessToken = document.getElementById("businessToken").value.trim();
  const verifyToken = document.getElementById("verifyToken").value.trim();

  if (!phoneNumberId || !businessToken) {
    showToast("Phone Number ID and Business Token are required.", "error");
    return;
  }

  const btn = document.getElementById("btnSaveMeta");
  btn.disabled = true;
  btn.innerHTML = `<div class="qr-spinner" style="width:16px;height:16px;border-width:2px;"></div> Saving…`;

  try {
    const res = await fetch("/api/configure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: "meta",
        phoneNumberId,
        businessToken,
        verifyToken,
      }),
    });

    const data = await res.json();

    if (res.ok) {
      showToast("Meta Cloud API credentials saved! Bridge restarting…", "success");
      // Re-poll status after a short delay
      setTimeout(fetchStatus, 2000);
    } else {
      showToast(data.error || "Failed to save configuration.", "error");
    }
  } catch (err) {
    showToast("Could not reach the bridge. Is it running?", "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      Save & Connect
    `;
  }
}

// ─── Test Meta Connection ───
async function testMetaConnection() {
  const phoneNumberId = document.getElementById("phoneNumberId").value.trim();
  const businessToken = document.getElementById("businessToken").value.trim();

  if (!phoneNumberId || !businessToken) {
    showToast("Fill in Phone Number ID and Token first.", "error");
    return;
  }

  const btn = document.getElementById("btnTestMeta");
  btn.disabled = true;

  try {
    const res = await fetch("/api/test-meta", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phoneNumberId, businessToken }),
    });

    const data = await res.json();

    if (res.ok && data.valid) {
      showToast(`✓ Connection valid! Phone: ${data.display_phone || "OK"}`, "success");
    } else {
      showToast(data.error || "Connection test failed.", "error");
    }
  } catch {
    showToast("Could not reach the bridge.", "error");
  } finally {
    btn.disabled = false;
  }
}

// ─── Send Test Message ───
async function sendTestMessage() {
  const recipient = document.getElementById("testRecipient").value.trim();
  const message = document.getElementById("testMessage").value.trim();

  if (!recipient || !message) {
    showToast("Enter a recipient and message.", "error");
    return;
  }

  const btn = document.getElementById("btnSendTest");
  btn.disabled = true;

  try {
    let url, body;

    if (currentMode === "webjs") {
      url = "/send";
      body = { groupId: recipient, message };
    } else {
      url = "/send-direct";
      body = { phoneNumber: recipient, message };
    }

    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + (window._serviceToken || "change-me"),
      },
      body: JSON.stringify(body),
    });

    const data = await res.json();

    if (res.ok) {
      showToast("Message sent! ✓", "success");
    } else {
      showToast(data.error || "Send failed.", "error");
    }
  } catch {
    showToast("Could not reach the bridge.", "error");
  } finally {
    btn.disabled = false;
  }
}

// ─── Fetch Service Token ───
async function fetchServiceToken() {
  try {
    const res = await fetch("/api/token-hint");
    const data = await res.json();
    window._serviceToken = data.token || "change-me";
  } catch {
    window._serviceToken = "change-me";
  }
}

// ─── Load Saved Config ───
async function loadSavedConfig() {
  try {
    const res = await fetch("/api/qr");
    const data = await res.json();
    if (data.mode) {
      switchMode(data.mode);
    }
  } catch { /* server might be down */ }
}

// ─── Toast Notifications ───
function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");

  const icons = {
    success: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
    error: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
    info: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="#0084ff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
  };

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;

  container.appendChild(toast);

  // Auto-remove after 5s
  setTimeout(() => {
    toast.classList.add("removing");
    setTimeout(() => toast.remove(), 250);
  }, 5000);
}

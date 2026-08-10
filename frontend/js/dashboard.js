/**
 * Gmail Reminder — Dashboard Client-Side Logic
 *
 * Talks to the FastAPI backend at the same origin.
 * Handles navigation, CRUD for accounts/destinations/routing,
 * live data, and WhatsApp Bridge configuration.
 */

const API = "";  // same origin
const WA_API = "/whatsapp-api";  // proxied to Node bridge

// ─── Navigation ───
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-item").forEach((btn) => {
    btn.addEventListener("click", () => navigateTo(btn.dataset.section));
  });

  // Mobile menu toggle
  document.getElementById("menuToggle").addEventListener("click", () => {
    document.getElementById("sidebar").classList.toggle("open");
  });

  // Check for OAuth callback success
  checkOAuthReturn();

  // Load all data
  loadAccounts();
  loadDestinations();
  loadRoutingRules();
  loadEmails();
  loadReminders();
  checkHealth();
  setInterval(checkHealth, 15000);

  // WhatsApp Bridge
  initWhatsAppBridge();
});

function navigateTo(section) {
  document.querySelectorAll(".section").forEach((s) => s.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((n) => n.classList.remove("active"));
  document.getElementById("section" + capitalize(section)).classList.add("active");
  document.querySelector(`[data-section="${section}"]`).classList.add("active");
  document.getElementById("sidebar").classList.remove("open");
}

function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

// ═══════════════════════════════════
//  HEALTH
// ═══════════════════════════════════
async function checkHealth() {
  const el = document.getElementById("healthIndicator");
  try {
    const res = await fetch(`${API}/health`);
    const data = await res.json();
    el.className = "health-indicator ok";
    el.querySelector(".health-text").textContent =
      `OK · ${data.pending_reminders || 0} pending`;
  } catch {
    el.className = "health-indicator err";
    el.querySelector(".health-text").textContent = "Backend offline";
  }
}

// ═══════════════════════════════════
//  ACCOUNTS
// ═══════════════════════════════════
let accountsData = [];

async function loadAccounts() {
  try {
    const res = await fetch(`${API}/accounts`);
    accountsData = await res.json();
    renderAccounts();
  } catch {
    showToast("Could not load accounts", "error");
  }
}

function renderAccounts() {
  const grid = document.getElementById("accountsList");
  const empty = document.getElementById("accountsEmpty");

  if (accountsData.length === 0) {
    grid.innerHTML = "";
    grid.appendChild(empty);
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";
  grid.innerHTML = accountsData.map((a) => `
    <div class="account-card">
      <div class="card-top">
        <div style="display:flex;align-items:center;gap:12px;">
          <div class="card-avatar avatar-gmail">
            ${a.email.charAt(0).toUpperCase()}
          </div>
          <div>
            <div class="card-email">${a.email}</div>
            ${a.label ? `<div class="card-label">${a.label}</div>` : ""}
          </div>
        </div>
        <div style="display:flex;gap:6px;">
          <span class="tag ${a.active ? "tag-active" : "tag-inactive"}">${a.active ? "Active" : "Inactive"}</span>
          <span class="tag ${a.authenticated ? "tag-auth" : "tag-unauth"}">${a.authenticated ? "Auth ✓" : "Re-auth"}</span>
        </div>
      </div>
      <div class="card-meta">
        <span class="card-meta-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          Connected ${new Date(a.created_at).toLocaleDateString()}
        </span>
        <span class="card-meta-item">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/></svg>
          Calendar ${a.calendar_sync_enabled ? "on" : "off"}
        </span>
      </div>
      <div class="card-actions">
        <button class="btn btn-sm btn-ghost" onclick="toggleAccount('${a.id}', ${!a.active})">
          ${a.active ? "Deactivate" : "Activate"}
        </button>
        <button class="btn btn-sm btn-ghost" onclick="toggleCalendar('${a.id}', ${!a.calendar_sync_enabled})">
          ${a.calendar_sync_enabled ? "Disable Calendar" : "Enable Calendar"}
        </button>
        ${!a.authenticated ? `<button class="btn btn-sm btn-success" onclick="connectGmail()">Re-connect</button>` : ""}
        <button class="btn btn-sm btn-danger" onclick="deleteAccount('${a.id}')">Delete</button>
      </div>
    </div>
  `).join("");
}

function connectGmail() {
  window.location.href = `${API}/accounts/gmail/login`;
}

async function toggleAccount(id, active) {
  try {
    await fetch(`${API}/accounts/${id}?active=${active}`, { method: "PATCH" });
    showToast(`Account ${active ? "activated" : "deactivated"}`, "success");
    loadAccounts();
  } catch { showToast("Failed to update account", "error"); }
}

async function toggleCalendar(id, enabled) {
  try {
    await fetch(`${API}/accounts/${id}?calendar_sync_enabled=${enabled}`, { method: "PATCH" });
    showToast(`Calendar sync ${enabled ? "enabled" : "disabled"}`, "success");
    loadAccounts();
  } catch { showToast("Failed to update", "error"); }
}

async function deleteAccount(id) {
  if (!confirm("Delete this Gmail account? This removes the account from polling.")) return;
  try {
    await fetch(`${API}/accounts/${id}`, { method: "DELETE" });
    showToast("Account removed", "success");
    loadAccounts();
  } catch { showToast("Failed to delete", "error"); }
}

function checkOAuthReturn() {
  const params = new URLSearchParams(window.location.search);
  if (params.get("oauth") === "success") {
    const email = params.get("email") || "";
    const banner = document.getElementById("oauthBanner");
    const bannerEmail = document.getElementById("oauthBannerEmail");
    banner.style.display = "flex";
    bannerEmail.textContent = email ? `(${email})` : "";
    window.history.replaceState({}, "", "/dashboard");
  }
}

// ═══════════════════════════════════
//  DESTINATIONS
// ═══════════════════════════════════
let destinationsData = [];

async function loadDestinations() {
  try {
    const res = await fetch(`${API}/destinations`);
    destinationsData = await res.json();
    renderDestinations();
  } catch { /* ignore */ }
}

function renderDestinations() {
  const grid = document.getElementById("destinationsList");
  const empty = document.getElementById("destinationsEmpty");

  if (destinationsData.length === 0) {
    grid.innerHTML = "";
    grid.appendChild(empty);
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";
  const typeIcons = { whatsapp: "WA", whatsapp_meta: "M", telegram: "TG" };
  const typeLabels = { whatsapp: "WhatsApp (web.js)", whatsapp_meta: "WhatsApp (Meta)", telegram: "Telegram" };

  grid.innerHTML = destinationsData.map((d) => `
    <div class="dest-card">
      <div class="card-top">
        <div style="display:flex;align-items:center;gap:12px;">
          <div class="card-avatar avatar-${d.type}">${typeIcons[d.type] || "?"}</div>
          <div>
            <div class="card-email">${d.name}</div>
            <div class="card-label">${typeLabels[d.type] || d.type}</div>
          </div>
        </div>
        <div style="display:flex;gap:6px;">
          <span class="tag ${d.active ? "tag-active" : "tag-inactive"}">${d.active ? "Active" : "Off"}</span>
          ${d.is_default ? '<span class="tag tag-default">Default</span>' : ""}
        </div>
      </div>
      <div class="card-meta">
        <span class="card-meta-item" style="font-family:monospace;font-size:0.72rem;">${d.target_id}</span>
      </div>
      <div class="card-actions">
        <button class="btn btn-sm btn-ghost" onclick="toggleDest('${d.id}', ${!d.active})">${d.active ? "Deactivate" : "Activate"}</button>
        <button class="btn btn-sm btn-ghost" onclick="toggleDefault('${d.id}', ${!d.is_default})">${d.is_default ? "Unset Default" : "Set Default"}</button>
        <button class="btn btn-sm btn-danger" onclick="deleteDest('${d.id}')">Delete</button>
      </div>
    </div>
  `).join("");
}

function showAddDestination() {
  openModal("Add Destination", `
    <form id="addDestForm">
      <div class="form-group">
        <label>Type</label>
        <select class="form-select" id="destType" required>
          <option value="whatsapp">WhatsApp (whatsapp-web.js)</option>
          <option value="whatsapp_meta">WhatsApp (Meta Cloud API)</option>
          <option value="telegram">Telegram</option>
        </select>
      </div>
      <div class="form-group">
        <label>Name</label>
        <input class="form-input" id="destName" placeholder="e.g. CS Batch Group" required>
      </div>
      <div class="form-group">
        <label>Target ID</label>
        <input class="form-input" id="destTarget" placeholder="Group JID / Phone / Chat ID" required>
      </div>
      <div class="form-group" style="display:flex;align-items:center;gap:8px;">
        <input type="checkbox" id="destDefault">
        <label for="destDefault" style="margin:0;text-transform:none;letter-spacing:0;font-weight:400;font-size:0.85rem;">Set as default destination</label>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Add Destination</button>
      </div>
    </form>
  `);
  document.getElementById("addDestForm").addEventListener("submit", addDestination);
}

async function addDestination(e) {
  e.preventDefault();
  const payload = {
    type: document.getElementById("destType").value,
    name: document.getElementById("destName").value,
    target_id: document.getElementById("destTarget").value,
    is_default: document.getElementById("destDefault").checked,
  };
  try {
    const res = await fetch(`${API}/destinations`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Failed");
    showToast("Destination added!", "success");
    closeModal();
    loadDestinations();
  } catch (err) { showToast(err.message, "error"); }
}

async function toggleDest(id, active) {
  await fetch(`${API}/destinations/${id}?active=${active}`, { method: "PATCH" });
  loadDestinations();
}

async function toggleDefault(id, isDefault) {
  await fetch(`${API}/destinations/${id}?is_default=${isDefault}`, { method: "PATCH" });
  loadDestinations();
}

async function deleteDest(id) {
  if (!confirm("Delete this destination?")) return;
  await fetch(`${API}/destinations/${id}`, { method: "DELETE" });
  showToast("Destination deleted", "success");
  loadDestinations();
}

// ═══════════════════════════════════
//  ROUTING RULES
// ═══════════════════════════════════
let routingData = [];

async function loadRoutingRules() {
  try {
    const res = await fetch(`${API}/routing-rules`);
    routingData = await res.json();
    renderRouting();
  } catch { /* ignore */ }
}

function renderRouting() {
  const wrapper = document.getElementById("routingList");
  const empty = document.getElementById("routingEmpty");

  if (routingData.length === 0) {
    wrapper.innerHTML = "";
    wrapper.appendChild(empty);
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";
  wrapper.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Account</th>
          <th>Category</th>
          <th>Destination</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        ${routingData.map((r) => `
          <tr>
            <td>${r.account_email || '<span style="color:var(--text-muted)">Any account</span>'}</td>
            <td>${r.category || '<span style="color:var(--text-muted)">Any category</span>'}</td>
            <td>${r.destination_name || `#${r.destination_id}`}</td>
            <td><button class="btn btn-sm btn-danger" onclick="deleteRule('${r.id}')">Delete</button></td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function showAddRoutingRule() {
  const accOpts = accountsData.map((a) => `<option value="${a.id}">${a.email}</option>`).join("");
  const destOpts = destinationsData.map((d) => `<option value="${d.id}">${d.name} (${d.type})</option>`).join("");

  openModal("Add Routing Rule", `
    <form id="addRuleForm">
      <div class="form-group">
        <label>Account (leave empty for any)</label>
        <select class="form-select" id="ruleAccount">
          <option value="">Any account</option>
          ${accOpts}
        </select>
      </div>
      <div class="form-group">
        <label>Category (leave empty for any)</label>
        <input class="form-input" id="ruleCategory" placeholder="e.g. Exam, Assignment, General">
      </div>
      <div class="form-group">
        <label>Destination</label>
        <select class="form-select" id="ruleDestination" required>
          ${destOpts}
        </select>
      </div>
      <div class="form-actions">
        <button type="button" class="btn btn-ghost" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Add Rule</button>
      </div>
    </form>
  `);
  document.getElementById("addRuleForm").addEventListener("submit", addRoutingRule);
}

async function addRoutingRule(e) {
  e.preventDefault();
  const payload = {
    destination_id: document.getElementById("ruleDestination").value,
    account_id: document.getElementById("ruleAccount").value || null,
    category: document.getElementById("ruleCategory").value.trim() || null,
  };
  try {
    const res = await fetch(`${API}/routing-rules`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.json()).detail || "Failed");
    showToast("Routing rule added!", "success");
    closeModal();
    loadRoutingRules();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteRule(id) {
  if (!confirm("Delete this routing rule?")) return;
  await fetch(`${API}/routing-rules/${id}`, { method: "DELETE" });
  showToast("Rule deleted", "success");
  loadRoutingRules();
}

// ═══════════════════════════════════
//  EMAILS
// ═══════════════════════════════════
async function loadEmails() {
  try {
    const res = await fetch(`${API}/emails?limit=50`);
    const emails = await res.json();
    renderEmails(emails);
  } catch { /* ignore */ }
}

function renderEmails(emails) {
  const wrapper = document.getElementById("emailsList");
  const empty = document.getElementById("emailsEmpty");

  if (emails.length === 0) {
    wrapper.innerHTML = "";
    wrapper.appendChild(empty);
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";
  wrapper.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Subject</th>
          <th>Sender</th>
          <th>Category</th>
          <th>Deadline</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody>
        ${emails.map((e) => `
          <tr>
            <td style="max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-primary);">${e.subject}</td>
            <td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${e.sender}</td>
            <td><span class="tag tag-default">${e.category || "—"}</span></td>
            <td>${e.deadline ? new Date(e.deadline).toLocaleString() : '<span style="color:var(--text-muted)">None</span>'}</td>
            <td style="font-size:0.75rem;">${new Date(e.created_at).toLocaleDateString()}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

async function syncNow() {
  try {
    const res = await fetch(`${API}/sync`, { method: "POST" });
    const data = await res.json();
    showToast(`Synced! ${data.new_emails_processed} new emails processed.`, "success");
    loadEmails();
    loadReminders();
  } catch { showToast("Sync failed", "error"); }
}

// ═══════════════════════════════════
//  REMINDERS
// ═══════════════════════════════════
async function loadReminders() {
  try {
    const res = await fetch(`${API}/reminders`);
    const reminders = await res.json();
    renderReminders(reminders);
  } catch { /* ignore */ }
}

function renderReminders(reminders) {
  const wrapper = document.getElementById("remindersList");
  const empty = document.getElementById("remindersEmpty");

  if (reminders.length === 0) {
    wrapper.innerHTML = "";
    wrapper.appendChild(empty);
    empty.style.display = "block";
    return;
  }

  empty.style.display = "none";
  const statusColors = { pending: "tag-default", sent: "tag-active", failed: "tag-inactive" };

  wrapper.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Destination</th>
          <th>Message</th>
          <th>Reminder Time</th>
          <th>Status</th>
          <th>Retries</th>
        </tr>
      </thead>
      <tbody>
        ${reminders.map((r) => `
          <tr>
            <td>${r.destination_name || `#${r.destination_id}`}</td>
            <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${r.message || "—"}</td>
            <td style="font-size:0.8rem;">${new Date(r.reminder_time).toLocaleString()}</td>
            <td><span class="tag ${statusColors[r.status] || ""}">${r.status}</span></td>
            <td>${r.retries || 0}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

async function sendDueNow() {
  try {
    const res = await fetch(`${API}/send`, { method: "POST" });
    const data = await res.json();
    showToast(`Sent ${data.reminders_sent} due reminders.`, "success");
    loadReminders();
  } catch { showToast("Send failed", "error"); }
}

// ═══════════════════════════════════
//  WHATSAPP BRIDGE
// ═══════════════════════════════════
let waMode = "webjs";
let waQrInterval = null;

function initWhatsAppBridge() {
  // Mode toggle
  document.querySelectorAll(".wa-mode-btn").forEach((btn) => {
    btn.addEventListener("click", () => switchWaMode(btn.dataset.wamode));
  });

  // Meta form submit
  const metaForm = document.getElementById("waMetaForm");
  if (metaForm) {
    metaForm.addEventListener("submit", saveWaMeta);
  }

  // Check bridge health
  checkWaHealth();
  setInterval(checkWaHealth, 20000);
}

function switchWaMode(mode) {
  waMode = mode;
  document.querySelectorAll(".wa-mode-btn").forEach((b) => b.classList.remove("active"));
  document.querySelector(`[data-wamode="${mode}"]`).classList.add("active");
  document.getElementById("waPanelWebjs").style.display = mode === "webjs" ? "block" : "none";
  document.getElementById("waPanelMeta").style.display = mode === "meta" ? "block" : "none";

  // Update test label
  const label = document.getElementById("waRecipientLabel");
  if (label) label.textContent = mode === "webjs" ? "Group ID" : "Phone Number";

  if (mode === "webjs") fetchWaQR();
}

async function checkWaHealth() {
  const badge = document.getElementById("waStatusBadge");
  try {
    const res = await fetch(`${WA_API}/health`);
    const data = await res.json();
    if (data.status === "ready" || data.status === "ok") {
      badge.className = "wa-status-badge ready";
      badge.querySelector("span:last-child").textContent = "Connected";
    } else {
      badge.className = "wa-status-badge offline";
      badge.querySelector("span:last-child").textContent = data.status || "Disconnected";
    }
  } catch {
    badge.className = "wa-status-badge offline";
    badge.querySelector("span:last-child").textContent = "Bridge offline";
  }
}

async function fetchWaQR() {
  const placeholder = document.getElementById("waQrPlaceholder");
  const img = document.getElementById("waQrImage");
  try {
    const res = await fetch(`${WA_API}/api/qr`);
    if (res.ok) {
      const data = await res.json();
      if (data.qr) {
        img.src = data.qr;
        img.style.display = "block";
        placeholder.style.display = "none";
      } else {
        // Already connected, no QR needed
        img.style.display = "none";
        placeholder.innerHTML = `<p style="color:var(--success);">✓ Already connected</p>`;
        placeholder.style.display = "block";
      }
    } else {
      img.style.display = "none";
      placeholder.innerHTML = `<p>QR not available. Start the Node bridge.</p>`;
      placeholder.style.display = "block";
    }
  } catch {
    img.style.display = "none";
    placeholder.innerHTML = `<p style="color:var(--error);">Bridge not reachable (port 3000)</p>`;
    placeholder.style.display = "block";
  }
}

async function saveWaMeta(e) {
  e.preventDefault();
  const payload = {
    mode: "meta",
    phoneNumberId: document.getElementById("waPhoneNumberId").value,
    businessToken: document.getElementById("waBusinessToken").value,
    verifyToken: document.getElementById("waVerifyToken").value || undefined,
  };
  try {
    const res = await fetch(`${WA_API}/api/configure`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      showToast("Meta Cloud API configured!", "success");
      checkWaHealth();
    } else {
      const data = await res.json();
      showToast(data.error || "Configuration failed", "error");
    }
  } catch {
    showToast("Bridge not reachable", "error");
  }
}

async function testWaMeta() {
  try {
    const res = await fetch(`${WA_API}/api/test-meta`);
    const data = await res.json();
    if (data.ok) {
      showToast("Meta API connection is working!", "success");
    } else {
      showToast(data.error || "Connection test failed", "error");
    }
  } catch {
    showToast("Bridge not reachable", "error");
  }
}

async function sendWaTest() {
  const recipient = document.getElementById("waTestRecipient").value.trim();
  const message = document.getElementById("waTestMessage").value.trim();
  if (!recipient || !message) {
    showToast("Enter a recipient and message", "error");
    return;
  }

  const endpoint = waMode === "webjs"
    ? `${WA_API}/api/send-group`
    : `${WA_API}/api/send`;

  const body = waMode === "webjs"
    ? { groupId: recipient, message }
    : { to: recipient, message };

  try {
    const res = await fetch(endpoint, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (res.ok) {
      showToast("Test message sent!", "success");
    } else {
      showToast(data.error || "Send failed", "error");
    }
  } catch {
    showToast("Bridge not reachable", "error");
  }
}

// ═══════════════════════════════════
//  MODAL
// ═══════════════════════════════════
function openModal(title, bodyHTML) {
  document.getElementById("modalTitle").textContent = title;
  document.getElementById("modalBody").innerHTML = bodyHTML;
  document.getElementById("modalOverlay").classList.add("open");
}

function closeModal() {
  document.getElementById("modalOverlay").classList.remove("open");
}

// Close modal on overlay click
document.getElementById("modalOverlay").addEventListener("click", (e) => {
  if (e.target === e.currentTarget) closeModal();
});

// ═══════════════════════════════════
//  TOASTS
// ═══════════════════════════════════
function showToast(msg, type = "info") {
  const container = document.getElementById("toastContainer");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => { toast.classList.add("removing"); setTimeout(() => toast.remove(), 250); }, 4000);
}

/**
 * Dual-mode WhatsApp HTTP bridge with Setup UI.
 *
 * Modes (set via WHATSAPP_API_MODE env var):
 *
 *   "webjs"  – automates a real WhatsApp Web session via whatsapp-web.js.
 *              Supports groups (the only way to post into them), but violates
 *              WhatsApp's Terms of Service — use a burner number.
 *
 *   "meta"   – uses the official WhatsApp Business Cloud API (Meta Graph API).
 *              Only supports 1:1 messaging (template + session messages).
 *              Fully ToS-compliant, requires a Meta Business account.
 *
 * If WHATSAPP_API_MODE is not set, the service shows an interactive menu on
 * first run so the user can pick — or you can use the web UI at /setup.
 *
 * Endpoints (both modes):
 *   GET  /setup             -> Setup UI (enter phone, token, scan QR)
 *   GET  /health            -> { ready, mode }
 *   GET  /api/qr            -> { qr: dataURL | null, authenticated }
 *   POST /api/configure     -> save Meta credentials & restart mode
 *   POST /api/test-meta     -> validate Meta token
 *   POST /send              { groupId, message }       (webjs only)
 *   GET  /groups            -> list groups              (webjs only)
 *   POST /send-direct       { phoneNumber, message }   (meta only)
 *   GET  /webhook           Meta webhook verification  (meta only)
 *   POST /webhook           Meta webhook events        (meta only)
 */
const express = require("express");
const path = require("path");
const fs = require("fs");
const readline = require("readline");

const PORT = process.env.PORT || 3000;
const SERVICE_TOKEN = process.env.WHATSAPP_SERVICE_TOKEN || "change-me";
const CONFIG_FILE = path.join(__dirname, "bridge-config.json");

const app = express();
app.use(express.json());

// Serve static files (setup UI)
app.use(express.static(path.join(__dirname, "..", "public")));

let isReady = false;
let currentMode = null;
let latestQRDataURL = null;  // stores the QR as a base64 PNG data URL
let isAuthenticated = false;

// ──────────────────────────────────────────────
// Persistent config (saves credentials to disk)
// ──────────────────────────────────────────────
function loadConfig() {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      return JSON.parse(fs.readFileSync(CONFIG_FILE, "utf-8"));
    }
  } catch { /* ignore */ }
  return {};
}

function saveConfig(data) {
  const existing = loadConfig();
  const merged = { ...existing, ...data };
  fs.writeFileSync(CONFIG_FILE, JSON.stringify(merged, null, 2), "utf-8");
  return merged;
}

// ──────────────────────────────────────────────
// Auth middleware (shared)
// ──────────────────────────────────────────────
function requireAuth(req, res, next) {
  const header = req.headers.authorization || "";
  const token = header.startsWith("Bearer ") ? header.slice(7) : "";
  if (token !== SERVICE_TOKEN) {
    return res.status(401).json({ error: "unauthorized" });
  }
  next();
}

// ──────────────────────────────────────────────
// Shared routes
// ──────────────────────────────────────────────

// Setup page
app.get("/setup", (_req, res) => {
  res.sendFile(path.join(__dirname, "..", "public", "setup.html"));
});

// Health
app.get("/health", (_req, res) => {
  res.json({ ready: isReady, mode: currentMode });
});

// QR code API (for the setup UI)
app.get("/api/qr", (_req, res) => {
  res.json({
    qr: latestQRDataURL,
    authenticated: isAuthenticated,
    mode: currentMode,
  });
});

// Configure Meta credentials (from setup UI)
app.post("/api/configure", (req, res) => {
  const { mode, phoneNumberId, businessToken, verifyToken } = req.body || {};

  if (mode === "meta") {
    if (!phoneNumberId || !businessToken) {
      return res
        .status(400)
        .json({ error: "phoneNumberId and businessToken are required" });
    }

    // Save to config file
    saveConfig({
      mode: "meta",
      phoneNumberId,
      businessToken,
      verifyToken: verifyToken || "change-me-webhook",
    });

    // Update env vars in-process for hot-reload
    process.env.WHATSAPP_API_MODE = "meta";
    process.env.WHATSAPP_PHONE_NUMBER_ID = phoneNumberId;
    process.env.WHATSAPP_BUSINESS_TOKEN = businessToken;
    if (verifyToken) process.env.WHATSAPP_VERIFY_TOKEN = verifyToken;

    // If we're currently not in meta mode, we need a restart
    if (currentMode !== "meta") {
      res.json({
        status: "saved",
        message:
          "Credentials saved. Restart the service with WHATSAPP_API_MODE=meta to apply.",
        restart_required: true,
      });
    } else {
      // Already in meta mode — update live refs
      metaConfig.phoneNumberId = phoneNumberId;
      metaConfig.businessToken = businessToken;
      metaConfig.verifyToken = verifyToken || metaConfig.verifyToken;
      metaConfig.graphUrl = `https://graph.facebook.com/${metaConfig.graphApiVersion}/${phoneNumberId}/messages`;
      isReady = true;

      res.json({ status: "saved", message: "Credentials updated live." });
    }
  } else {
    res.status(400).json({ error: "Only meta mode can be configured via UI." });
  }
});

// Test Meta connection (validate token by calling Graph API)
app.post("/api/test-meta", async (req, res) => {
  const { phoneNumberId, businessToken } = req.body || {};

  if (!phoneNumberId || !businessToken) {
    return res
      .status(400)
      .json({ error: "phoneNumberId and businessToken are required" });
  }

  try {
    const axios = require("axios");
    const version = process.env.WHATSAPP_GRAPH_API_VERSION || "v21.0";
    const url = `https://graph.facebook.com/${version}/${phoneNumberId}`;

    const response = await axios.get(url, {
      headers: { Authorization: `Bearer ${businessToken}` },
      timeout: 10000,
    });

    res.json({
      valid: true,
      display_phone: response.data?.display_phone_number || null,
      verified_name: response.data?.verified_name || null,
      quality_rating: response.data?.quality_rating || null,
    });
  } catch (err) {
    const detail =
      err.response?.data?.error?.message || err.message || "unknown error";
    res.status(400).json({ valid: false, error: detail });
  }
});

// Service token endpoint (so the UI can send authenticated test messages)
app.get("/api/token-hint", (_req, res) => {
  // Return a masked version + set a JS variable for the UI
  const masked =
    SERVICE_TOKEN.length > 8
      ? SERVICE_TOKEN.slice(0, 4) + "…" + SERVICE_TOKEN.slice(-4)
      : "****";
  res.json({ masked, token: SERVICE_TOKEN });
});

// ══════════════════════════════════════════════
//  MODE: webjs (whatsapp-web.js)
// ══════════════════════════════════════════════
function startWebJS() {
  currentMode = "webjs";

  const QRCode = require("qrcode");
  const { Client, LocalAuth } = require("whatsapp-web.js");

  const client = new Client({
    authStrategy: new LocalAuth({ dataPath: "./session" }),
    puppeteer: {
      headless: true,
      args: ["--no-sandbox", "--disable-setuid-sandbox"],
    },
  });

  client.on("qr", async (qr) => {
    isAuthenticated = false;

    console.log("\n╔══════════════════════════════════════════╗");
    console.log("║  Scan with WhatsApp > Linked Devices     ║");
    console.log("║  or open /setup in your browser          ║");
    console.log("╚══════════════════════════════════════════╝\n");

    // Generate QR as data URL for the web UI
    try {
      latestQRDataURL = await QRCode.toDataURL(qr, {
        width: 256,
        margin: 2,
        color: { dark: "#000000", light: "#ffffff" },
      });
    } catch (err) {
      console.error("QR data URL generation failed:", err.message);
    }

    // Compact QR for terminal
    try {
      const qrText = await QRCode.toString(qr, {
        type: "terminal",
        small: true,
        margin: 1,
        width: 1,
      });
      console.log(qrText);
    } catch (err) {
      const qrcodeTerminal = require("qrcode-terminal");
      qrcodeTerminal.generate(qr, { small: true });
    }
  });

  client.on("ready", () => {
    isReady = true;
    isAuthenticated = true;
    latestQRDataURL = null; // clear QR once authenticated
    console.log("✅ WhatsApp Web bridge ready (webjs mode).");
  });

  client.on("disconnected", (reason) => {
    isReady = false;
    isAuthenticated = false;
    console.error("❌ WhatsApp client disconnected:", reason);
  });

  client.on("auth_failure", (msg) => {
    isReady = false;
    isAuthenticated = false;
    console.error("❌ WhatsApp auth failure:", msg);
  });

  client.initialize();

  // -- webjs-only routes --

  app.get("/groups", requireAuth, async (_req, res) => {
    if (!isReady) return res.status(503).json({ error: "client not ready" });
    try {
      const chats = await client.getChats();
      const groups = chats
        .filter((c) => c.isGroup)
        .map((c) => ({ id: c.id._serialized, name: c.name }));
      res.json({ groups });
    } catch (err) {
      console.error(err);
      res.status(500).json({ error: err.message });
    }
  });

  app.post("/send", requireAuth, async (req, res) => {
    if (!isReady) return res.status(503).json({ error: "client not ready" });

    const { groupId, message } = req.body || {};
    if (!groupId || !message) {
      return res.status(400).json({ error: "groupId and message are required" });
    }

    try {
      await client.sendMessage(groupId, message);
      res.json({ status: "sent" });
    } catch (err) {
      console.error("Send failed:", err);
      res.status(500).json({ error: err.message });
    }
  });

  // Block meta-only routes with a helpful error
  app.post("/send-direct", (_req, res) => {
    res.status(400).json({
      error: "send-direct is only available in meta mode. Current mode: webjs",
    });
  });
}

// ══════════════════════════════════════════════
//  MODE: meta (WhatsApp Business Cloud API)
// ══════════════════════════════════════════════

// Live-updatable config for meta mode
const metaConfig = {
  phoneNumberId: null,
  businessToken: null,
  verifyToken: null,
  graphApiVersion: "v21.0",
  graphUrl: null,
};

function startMeta() {
  currentMode = "meta";
  isAuthenticated = true; // no QR needed

  const axios = require("axios");

  // Load from env first, then config file as fallback
  const savedConfig = loadConfig();
  metaConfig.phoneNumberId =
    process.env.WHATSAPP_PHONE_NUMBER_ID || savedConfig.phoneNumberId || "";
  metaConfig.businessToken =
    process.env.WHATSAPP_BUSINESS_TOKEN || savedConfig.businessToken || "";
  metaConfig.verifyToken =
    process.env.WHATSAPP_VERIFY_TOKEN ||
    savedConfig.verifyToken ||
    "change-me-webhook";
  metaConfig.graphApiVersion =
    process.env.WHATSAPP_GRAPH_API_VERSION || "v21.0";
  metaConfig.graphUrl = `https://graph.facebook.com/${metaConfig.graphApiVersion}/${metaConfig.phoneNumberId}/messages`;

  if (!metaConfig.phoneNumberId || !metaConfig.businessToken) {
    console.warn(
      "⚠️  Meta Cloud API credentials not set yet.\n" +
        `   Open http://localhost:${PORT}/setup in your browser to enter them.`
    );
    // Don't exit — let the UI configure it
    isReady = false;
  } else {
    isReady = true;
    console.log("✅ WhatsApp Cloud API bridge ready (meta mode).");
    console.log(`   Phone Number ID: ${metaConfig.phoneNumberId}`);
    console.log(`   Graph API version: ${metaConfig.graphApiVersion}`);
  }

  // -- Send a text message to a phone number --
  app.post("/send-direct", requireAuth, async (req, res) => {
    if (!isReady) {
      return res.status(503).json({
        error: "Bridge not configured. Open /setup to enter Meta credentials.",
      });
    }

    const { phoneNumber, message, template } = req.body || {};

    if (!phoneNumber) {
      return res.status(400).json({ error: "phoneNumber is required" });
    }

    try {
      let payload;

      if (template) {
        payload = {
          messaging_product: "whatsapp",
          to: phoneNumber,
          type: "template",
          template: {
            name: template.name,
            language: { code: template.language || "en" },
            components: template.components || [],
          },
        };
      } else if (message) {
        payload = {
          messaging_product: "whatsapp",
          to: phoneNumber,
          type: "text",
          text: { body: message },
        };
      } else {
        return res
          .status(400)
          .json({ error: "message or template is required" });
      }

      const response = await axios.post(metaConfig.graphUrl, payload, {
        headers: {
          Authorization: `Bearer ${metaConfig.businessToken}`,
          "Content-Type": "application/json",
        },
        timeout: 15000,
      });

      res.json({
        status: "sent",
        wamid: response.data?.messages?.[0]?.id || null,
      });
    } catch (err) {
      const detail =
        err.response?.data?.error?.message || err.message || "unknown error";
      console.error("Meta send failed:", detail);
      res.status(500).json({ error: detail });
    }
  });

  // -- Webhook verification --
  app.get("/webhook", (req, res) => {
    const mode = req.query["hub.mode"];
    const token = req.query["hub.verify_token"];
    const challenge = req.query["hub.challenge"];

    if (mode === "subscribe" && token === metaConfig.verifyToken) {
      console.log("✅ Webhook verified by Meta.");
      return res.status(200).send(challenge);
    }
    res.status(403).json({ error: "verification failed" });
  });

  // -- Webhook events --
  app.post("/webhook", (req, res) => {
    const body = req.body;

    if (body?.object === "whatsapp_business_account") {
      const entries = body.entry || [];
      for (const entry of entries) {
        const changes = entry.changes || [];
        for (const change of changes) {
          const value = change.value || {};
          if (value.messages) {
            for (const msg of value.messages) {
              console.log(
                `📩 Incoming from ${msg.from}: ${msg.text?.body || "[non-text]"}`
              );
            }
          }
          if (value.statuses) {
            for (const status of value.statuses) {
              console.log(
                `📊 Status ${status.id}: ${status.status} (to ${status.recipient_id})`
              );
            }
          }
        }
      }
    }

    res.sendStatus(200);
  });

  // Block webjs-only routes
  app.post("/send", (_req, res) => {
    res.status(400).json({
      error:
        "POST /send (group messaging) is only available in webjs mode. " +
        "Use POST /send-direct for 1:1 messages in meta mode.",
    });
  });

  app.get("/groups", (_req, res) => {
    res.status(400).json({
      error:
        "GET /groups is only available in webjs mode. " +
        "Meta Cloud API does not support group messaging.",
    });
  });
}

// ══════════════════════════════════════════════
//  Interactive mode selection (terminal)
// ══════════════════════════════════════════════
async function promptModeSelection() {
  return new Promise((resolve) => {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });

    console.log("");
    console.log("╔═══════════════════════════════════════════════════════════╗");
    console.log("║          Select WhatsApp API Mode                        ║");
    console.log("║                                                          ║");
    console.log("║  1. whatsapp-web.js  (unofficial, supports groups)       ║");
    console.log("║  2. Meta Cloud API   (official, 1:1 messages only)       ║");
    console.log("║                                                          ║");
    console.log("║  Tip: Set WHATSAPP_API_MODE=webjs or meta to skip this.  ║");
    console.log("╚═══════════════════════════════════════════════════════════╝");
    console.log("");

    function ask() {
      rl.question("Enter 1 or 2: ", (answer) => {
        const choice = answer.trim();
        if (choice === "1") {
          rl.close();
          resolve("webjs");
        } else if (choice === "2") {
          rl.close();
          resolve("meta");
        } else {
          console.log('Invalid choice. Please enter "1" or "2".');
          ask();
        }
      });
    }

    ask();
  });
}

// ══════════════════════════════════════════════
//  Bootstrap
// ══════════════════════════════════════════════
async function main() {
  let mode = (process.env.WHATSAPP_API_MODE || "").toLowerCase().trim();

  // Also check saved config if env not set
  if (!mode || (mode !== "webjs" && mode !== "meta")) {
    const saved = loadConfig();
    if (saved.mode === "webjs" || saved.mode === "meta") {
      mode = saved.mode;
      console.log(`📄 Loaded mode "${mode}" from saved config.`);
    }
  }

  if (!mode || (mode !== "webjs" && mode !== "meta")) {
    mode = await promptModeSelection();
    saveConfig({ mode });
  }

  console.log(`\n🚀 Starting WhatsApp bridge in "${mode}" mode...`);
  console.log(`🌐 Setup UI: http://localhost:${PORT}/setup\n`);

  if (mode === "webjs") {
    startWebJS();
  } else {
    startMeta();
  }

  app.listen(PORT, () => {
    console.log(`WhatsApp bridge listening on :${PORT} (mode: ${currentMode})`);
  });
}

main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});

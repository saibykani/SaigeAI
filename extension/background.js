// Saige AI v2.1 service worker. Talks to the Saige API with the user's revocable extension token on behalf of the page panel
// (content scripts can't call the API directly because of CORS). It only acts when the panel asks, which happens on a user click.
const DEFAULTS = { api: "https://saige-ai-api.vercel.app", web: "https://saige-ai.vercel.app", token: "" };

async function cfg() {
  return { ...DEFAULTS, ...(await chrome.storage.sync.get(["api", "web", "token"])) };
}

async function api(path, method = "GET", body) {
  const c = await cfg();
  if (!c.token) throw new Error("Add your extension token in Saige settings first.");
  const r = await fetch(`${c.api}/api${path}`, {
    method,
    headers: { Authorization: `Bearer ${c.token}`, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const d = data.detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? d[0]?.msg : d?.status === "VALIDATION FAILED"
      ? "Saige's truth check blocked this text: " + (d.violations || []).map((v) => v.value || v.message || "").filter(Boolean).slice(0, 3).join(", ")
      : "";
    throw new Error(r.status === 401 ? "Token invalid or revoked. Update it in Saige settings." : msg || `Request failed (${r.status})`);
  }
  return data;
}

// Downloads a generated resume into the user's Downloads folder (chrome.downloads needs a URL, so use a data URL).
async function download(path) {
  const c = await cfg();
  const r = await fetch(`${c.api}${path}`, { headers: { Authorization: `Bearer ${c.token}` } });
  if (!r.ok) throw new Error(`Download failed (${r.status})`);
  const cd = r.headers.get("Content-Disposition") || "";
  const star = cd.match(/filename\*=UTF-8''([^;]+)/i);
  const plain = cd.match(/filename="?([^";]+)"?/i);
  const name = star ? decodeURIComponent(star[1]) : plain ? plain[1] : "Resume";
  const bytes = new Uint8Array(await r.arrayBuffer());
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  const type = r.headers.get("Content-Type") || "application/octet-stream";
  await chrome.downloads.download({ url: `data:${type};base64,${btoa(bin)}`, filename: name, saveAs: false });
  return { name };
}

chrome.runtime.onMessage.addListener((msg, _sender, send) => {
  const run = msg.type === "api" ? api(msg.path, msg.method, msg.body) : msg.type === "download" ? download(msg.path)
    : msg.type === "config" ? cfg() : null;
  if (!run) return false;
  run.then((data) => send({ ok: true, data })).catch((e) => send({ ok: false, error: e.message }));
  return true; // async response
});

/** Open (or close) the panel on a tab. On pages without the content script, inject it once: the user's click grants activeTab. */
async function toggle(tab, scan = false) {
  if (!tab?.id || !/^https?:/.test(tab.url || "")) return;
  const ping = () => chrome.tabs.sendMessage(tab.id, { type: scan ? "scan" : "toggle" });
  try {
    await ping();
  } catch {
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["extract.js", "content.js"] });
    await ping();
  }
}

chrome.commands.onCommand.addListener(async (cmd) => {
  if (cmd !== "toggle-panel") return;
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  await toggle(tab);
});

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "open-panel-from-popup") {
    chrome.tabs.query({ active: true, currentWindow: true }).then(([tab]) => toggle(tab, !!msg.scan));
  }
});

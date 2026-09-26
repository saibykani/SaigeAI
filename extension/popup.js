// Saige AI popup. Reads ONLY the active tab, ONLY when the popup is opened (activeTab), and talks
// only to the Saige API with the user's revocable extension token. It never submits forms.

const DEFAULTS = { api: "https://saige-ai-api.vercel.app", web: "https://saige-ai.vercel.app", token: "" };
const $ = (id) => document.getElementById(id);
let cfg = DEFAULTS;
let page = null;

function setStatus(text, tone = "") {
  const el = $("status");
  el.textContent = text;
  el.className = `status ${tone}`;
}

async function call(path, options = {}) {
  const r = await fetch(`${cfg.api}/api${path}`, {
    ...options,
    headers: { Authorization: `Bearer ${cfg.token}`, "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await r.json().catch(() => ({}));
  if (!r.ok) {
    const detail = typeof body.detail === "string" ? body.detail : Array.isArray(body.detail) ? body.detail[0]?.msg : "";
    throw new Error(r.status === 401 ? "Token invalid or revoked. Update it in Settings." : detail || `Request failed (${r.status})`);
  }
  return body;
}

/** Same heuristics as Saige's capture page: "Senior SDET - PayCo | LinkedIn", "Senior SDET at PayCo". */
function guessTitleCompany(pageTitle) {
  const clean = pageTitle.replace(/\s*[|·–-]\s*(LinkedIn|Naukri\.com|Naukri|Indeed(\.com)?|Glassdoor|Wellfound|Instahyre|Foundit).*$/i, "").trim();
  const at = clean.match(/^(.+?)\s+(?:at|@)\s+(.+)$/i);
  if (at) return { title: at[1].trim(), company: at[2].trim() };
  const parts = clean.split(/\s+[-–|]\s+/);
  if (parts.length >= 2) return { title: parts[0].trim(), company: parts[1].trim() };
  return { title: clean, company: "" };
}

async function readActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id || !/^https?:/.test(tab.url || "")) throw new Error("Open a job posting in this tab first.");
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    // Runs in the page, once, because the user clicked the extension.
    func: () => ({
      url: location.href,
      title: document.title,
      text: (String(getSelection() || "").trim() || document.body.innerText || "").slice(0, 60000),
    }),
  });
  return result;
}

function payload() {
  return { url: page.url, title: $("title").value.trim(), company: $("company").value.trim(), text: page.text };
}

function showResult(r, savedId) {
  $("result").hidden = false;
  const ring = $("ring");
  ring.style.setProperty("--v", String(r.score));
  ring.style.setProperty("--c", r.score >= 75 ? "var(--green)" : r.score >= 60 ? "var(--orange)" : "var(--red)");
  $("scoreValue").textContent = `${r.score}%`;
  $("cls").textContent = r.classification;
  const chips = (el, items) => { el.replaceChildren(...(items.length ? items : ["—"]).map((s) => Object.assign(document.createElement("span"), { textContent: s }))); };
  chips($("matched"), r.matched_skills || []);
  chips($("missing"), r.missing_skills || []);
  const id = savedId || r.saved_job_id;
  const saved = $("saved");
  saved.replaceChildren();
  if (id) {
    const a = Object.assign(document.createElement("a"), { href: `${cfg.web}/jobs/${id}`, target: "_blank", textContent: "Open in Saige →" });
    saved.append("Saved · ", a);
  } else {
    saved.textContent = "Not saved yet";
  }
}

async function loadAnswers() {
  try {
    const r = await call(`/ext/answers?url=${encodeURIComponent(page.url)}`);
    const box = $("answers");
    if (!r.answers.length) return;
    box.replaceChildren(...r.answers.map((a) => {
      const div = document.createElement("div");
      div.className = "answer";
      const q = Object.assign(document.createElement("q"), { textContent: a.question });
      const p = Object.assign(document.createElement("p"), { textContent: a.answer });
      const btn = Object.assign(document.createElement("button"), { className: "btn small", textContent: "Copy" });
      btn.onclick = async () => { await navigator.clipboard.writeText(a.answer); btn.textContent = "Copied"; setTimeout(() => (btn.textContent = "Copy"), 1200); };
      div.append(q, p, btn);
      if (a.needs_review) div.append(Object.assign(document.createElement("span"), { className: "review", textContent: "  Review before using" }));
      return div;
    }));
  } catch {
    /* answers are optional */
  }
}

async function init() {
  cfg = { ...DEFAULTS, ...(await chrome.storage.sync.get(["api", "web", "token"])) };
  if (!cfg.token) {
    $("setup").hidden = false;
    return;
  }
  $("app").hidden = false;
  try {
    page = await readActiveTab();
    const g = guessTitleCompany(page.title || "");
    $("title").value = g.title.slice(0, 200);
    $("company").value = g.company.slice(0, 200);
    $("source").textContent = new URL(page.url).hostname;
    void loadAnswers();
  } catch (e) {
    setStatus(e.message, "error");
    $("score").disabled = $("save").disabled = true;
  }
}

$("score").onclick = async () => {
  setStatus("Scoring against your verified profile…");
  try {
    showResult(await call("/ext/analyze", { method: "POST", body: JSON.stringify(payload()) }));
    setStatus("");
  } catch (e) {
    setStatus(e.message, "error");
  }
};

$("save").onclick = async () => {
  setStatus("Saving…");
  try {
    const r = await call("/ext/save", { method: "POST", body: JSON.stringify(payload()) });
    const scored = await call("/ext/analyze", { method: "POST", body: JSON.stringify(payload()) });
    showResult(scored, r.job_id);
    setStatus(r.created ? "Saved to Saige." : "Already in Saige: merged with the existing job.", "ok");
  } catch (e) {
    setStatus(e.message, "error");
  }
};

void init();

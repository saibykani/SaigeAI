// Saige AI popup. Reads ONLY the active tab, ONLY when the popup is opened (activeTab), and talks
// only to the Saige API with the user's revocable extension token. When the user clicks "Fill", it
// types verified details into the form on the page; it never clicks Save / Submit.

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

async function activeTabId() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab.id;
}

// ---- Fill an application form (Greenhouse, Lever, Ashby, Workday, company career sites)
$("fill").onclick = async () => {
  setStatus("Filling the form with your verified details…");
  try {
    const data = await call(`/ext/autofill?url=${encodeURIComponent(page.url)}`);
    let resume = null;
    if (data.resume) {
      const r = await fetch(`${cfg.api}/api/ext/resume.docx?url=${encodeURIComponent(page.url)}`, { headers: { Authorization: `Bearer ${cfg.token}` } });
      if (r.ok) resume = { name: data.resume, bytes: Array.from(new Uint8Array(await r.arrayBuffer())) };
    }
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: await activeTabId() },
      args: [data.fields, data.answers, resume],
      func: (fields, answers, resume) => {
        const RULES = [
          ["first_name", /first.?name|given.?name|fname/i], ["last_name", /last.?name|surname|family.?name|lname/i],
          ["full_name", /full.?name|your name|candidate name|legal name|^name$/i], ["email", /e-?mail/i],
          ["phone", /phone|mobile|contact number/i], ["linkedin", /linkedin/i], ["github", /github/i],
          ["portfolio", /portfolio|website|personal site/i], ["current_company", /current (company|employer)|company name|employer/i],
          ["current_title", /current (title|role|designation)|job title|designation/i],
          ["years_experience", /years of experience|total experience|experience \(years\)/i],
          ["notice_period", /notice period/i], ["expected_ctc", /expected (ctc|salary|compensation)/i],
          ["current_ctc", /current (ctc|salary|compensation)/i], ["location", /location|city|where are you based/i], ["country", /country/i],
        ];
        const labelOf = (el) => {
          const byFor = el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
          return [byFor?.innerText, el.closest("label")?.innerText, el.getAttribute("aria-label"), el.placeholder, el.name,
                  el.getAttribute("autocomplete")].filter(Boolean).join(" ").slice(0, 200);
        };
        const setValue = (el, value) => {
          const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          el.style.outline = "2px solid #30d158";
          el.style.outlineOffset = "2px";
        };
        let filled = 0, attached = false;
        const inputs = [...document.querySelectorAll("input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=file]):not([type=submit]), textarea")]
          .filter((el) => !el.disabled && !el.readOnly && el.offsetParent !== null && !el.value);
        for (const el of inputs) {
          const label = labelOf(el);
          const rule = RULES.find(([key, re]) => fields[key] && re.test(label));
          if (rule) { setValue(el, fields[rule[0]]); filled++; continue; }
          const ans = answers.find((a) => a.question && label.toLowerCase().includes(a.question.toLowerCase().slice(0, 40)));
          if (ans) { setValue(el, ans.answer); filled++; }
        }
        if (resume) {
          const files = [...document.querySelectorAll("input[type=file]")];
          const file = files.find((el) => /resume|cv/i.test(labelOf(el))) || files[0];
          if (file && !file.files?.length) {
            const dt = new DataTransfer();
            dt.items.add(new File([new Uint8Array(resume.bytes)], resume.name, { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }));
            file.files = dt.files;
            file.dispatchEvent(new Event("change", { bubbles: true }));
            attached = true;
          }
        }
        return { filled, attached };
      },
    });
    setStatus(result.filled || result.attached
      ? `Filled ${result.filled} field(s)${result.attached ? " and attached your resume" : ""}. Check them (green outline), then submit on the site.`
      : "No empty form fields found. Open the application form first.", result.filled || result.attached ? "ok" : "");
  } catch (e) {
    setStatus(e.message, "error");
  }
};

// ---- LinkedIn / Naukri profile edits: fill the field the user clicked on the page
async function loadEdits() {
  const host = new URL(page.url).hostname;
  const platform = /naukri\.com$/.test(host) ? "naukri" : /linkedin\.com$/.test(host) ? "linkedin" : null;
  if (!platform) return;
  const edits = await call(`/ext/profile-edits?platform=${platform}`).catch(() => []);
  if (!edits.length) return;
  $("editsBox").hidden = false;
  $("editsTitle").textContent = `${edits[0].platform_name} edits ready · ${edits.length}`;
  $("edits").replaceChildren(...edits.map((ed) => {
    const div = document.createElement("div");
    div.className = "answer";
    div.append(Object.assign(document.createElement("q"), { textContent: ed.field_name }),
               Object.assign(document.createElement("p"), { textContent: ed.text }));
    const fill = Object.assign(document.createElement("button"), { className: "btn small primary", textContent: "Fill" });
    fill.onclick = async () => {
      const [{ result }] = await chrome.scripting.executeScript({
        target: { tabId: await activeTabId() }, args: [ed.text],
        func: (text) => {
          const el = document.activeElement;
          if (!el || !(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el.isContentEditable)) return false;
          if (el.isContentEditable) { el.focus(); document.execCommand("selectAll"); document.execCommand("insertText", false, text); return true; }
          const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
          Object.getOwnPropertyDescriptor(proto, "value").set.call(el, text);
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          return true;
        },
      });
      setStatus(result ? `${ed.field_name} filled. Click Save on the page, then Mark updated.` : "Click inside the field on the page first, then press Fill.", result ? "ok" : "error");
    };
    const copy = Object.assign(document.createElement("button"), { className: "btn small", textContent: "Copy" });
    copy.onclick = async () => { await navigator.clipboard.writeText(ed.text); copy.textContent = "Copied"; };
    const done = Object.assign(document.createElement("button"), { className: "btn small", textContent: "Mark updated" });
    done.onclick = async () => { await call(`/ext/profile-edits/${ed.id}/applied`, { method: "POST" }); div.remove(); setStatus("Marked as updated in Saige.", "ok"); };
    div.append(fill, copy, done);
    return div;
  }));
}


// ---- Replies to comments on your own LinkedIn post
function fillFocused(text) {
  const el = document.activeElement;
  if (!el || !(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el.isContentEditable)) return false;
  if (el.isContentEditable) { el.focus(); document.execCommand("selectAll"); document.execCommand("insertText", false, text); return true; }
  const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, text);
  el.dispatchEvent(new Event("input", { bubbles: true }));
  return true;
}

$("drafts").onclick = async () => {
  setStatus("Reading comments on this page…");
  try {
    const [{ result: comments }] = await chrome.scripting.executeScript({
      target: { tabId: await activeTabId() },
      func: () => [...document.querySelectorAll("article[class*='comments-comment'], [class*='comments-comment-entity']")]
        .slice(0, 30)
        .map((el) => ({
          author: (el.querySelector("[class*='comment-meta__description-title'], [class*='__name'], a[href*='/in/'] span[dir]")?.innerText || "").trim().split("\n")[0],
          text: (el.querySelector("[class*='comment-item__main-content'], [class*='__main-content'], [class*='comment-content']")?.innerText || "").trim(),
        }))
        .filter((c) => c.text),
    });
    if (!comments.length) { setStatus("No comments found. Open your post (its own page) and expand the comments first."); return; }
    const r = await call("/ext/comment-replies", { method: "POST", body: JSON.stringify({ comments }) });
    $("replies").replaceChildren(...r.replies.map((x) => {
      const div = document.createElement("div");
      div.className = "answer";
      div.append(Object.assign(document.createElement("q"), { textContent: `${x.author}: ${x.comment.slice(0, 120)}` }),
                 Object.assign(document.createElement("p"), { textContent: x.reply }));
      const fill = Object.assign(document.createElement("button"), { className: "btn small primary", textContent: "Fill" });
      fill.onclick = async () => {
        const [{ result }] = await chrome.scripting.executeScript({ target: { tabId: await activeTabId() }, args: [x.reply], func: fillFocused });
        setStatus(result ? "Reply filled. Press Reply on the page." : "Click the comment's reply box first, then press Fill.", result ? "ok" : "error");
      };
      const copy = Object.assign(document.createElement("button"), { className: "btn small", textContent: "Copy" });
      copy.onclick = async () => { await navigator.clipboard.writeText(x.reply); copy.textContent = "Copied"; };
      div.append(fill, copy);
      return div;
    }));
    setStatus(`${r.replies.length} repl${r.replies.length === 1 ? "y" : "ies"} drafted.`, "ok");
  } catch (e) {
    setStatus(e.message, "error");
  }
};

void init().then(() => {
  if (!page) return;
  void loadEdits();
  if (/linkedin\.com\/(feed\/update|posts)\//.test(page.url)) $("commentsBox").hidden = false;
});

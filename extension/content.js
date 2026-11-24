// Saige AI v2 content script.
// Reads ONLY the page the user has open, from the DOM already on screen: no crawling, no extra requests to the site.
// Shows a small "Saige" pill when a job description (or a hiring post on the LinkedIn feed) is visible. Clicking it opens a
// shadow-DOM side panel. Everything the panel does is user-triggered, goes to the Saige API through the background worker,
// and NEVER sends an email, presses Submit/Apply/Save, or clicks anything on the site.
(() => {
  if (window.__saigeV2) {
    return;
  }
  window.__saigeV2 = true;

  const HOST = location.hostname;
  const ON = (re) => re.test(HOST);

  // ------------------------------------------------------------------ detection (visible DOM only)
  const txt = (el) => (el ? (el.innerText || el.textContent || "").replace(/ /g, " ").replace(/\n{3,}/g, "\n\n").trim() : "");
  const first = (sels, root = document) => {
    for (const s of sels) {
      const el = root.querySelector(s);
      if (el && txt(el)) return el;
    }
    return null;
  };
  const visible = (el) => !!el && el.getClientRects().length > 0;

  /** schema.org JobPosting in the page's own JSON-LD (already in the DOM). */
  function jsonLd() {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const walk = (n) => (Array.isArray(n) ? n.flatMap(walk) : n && n["@graph"] ? walk(n["@graph"]) : n ? [n] : []);
        const jp = walk(JSON.parse(s.textContent)).find((n) => String(n["@type"]).includes("JobPosting"));
        if (jp?.description) {
          const d = document.createElement("div");
          d.innerHTML = jp.description; // parsed inert in a detached node, only textContent is read
          const loc = jp.jobLocation?.address;
          return { title: jp.title || "", company: jp.hiringOrganization?.name || "", text: txt(d) || d.textContent,
                   location: loc ? [loc.addressLocality, loc.addressCountry].filter(Boolean).join(", ") : "" };
        }
      } catch { /* not JSON */ }
    }
    return null;
  }

  const SITES = [
    { name: "LinkedIn", test: () => ON(/linkedin\.com$/) && (/\/jobs\//.test(location.pathname)),
      desc: ["#job-details", ".jobs-description__content", ".jobs-box__html-content", ".show-more-less-html__markup", ".jobs-search__job-details--container", ".description__text"],
      title: [".job-details-jobs-unified-top-card__job-title", ".jobs-unified-top-card__job-title", ".top-card-layout__title", "h1"],
      company: [".job-details-jobs-unified-top-card__company-name", ".jobs-unified-top-card__company-name", ".topcard__org-name-link", ".top-card-layout__card a[href*='/company/']"] },
    { name: "Naukri", test: () => ON(/naukri\.com$/),
      desc: ["[class*='dang-inner-html']", ".job-desc", "section[class*='job-desc']", "[class*='JDC__dang']"],
      title: ["h1.jd-header-title", "[class*='jd-header-title']", "h1"], company: ["[class*='jd-header-comp-name'] a", "a[class*='comp-name']", "[class*='comp-name']"] },
    { name: "Indeed", test: () => ON(/indeed\.(com|co\.in)$/),
      desc: ["#jobDescriptionText", "[data-testid='jobsearch-JobComponent-description']"],
      title: ["[data-testid='jobsearch-JobInfoHeader-title']", "h1.jobsearch-JobInfoHeader-title", "h1"],
      company: ["[data-testid='inlineHeader-companyName']", "[data-company-name='true']", ".jobsearch-CompanyInfoContainer a"] },
    { name: "Greenhouse", test: () => ON(/greenhouse\.io$/),
      desc: ["#content .job__description", ".job__description", "#content", "main"], title: [".app-title", ".job__title h1", "h1"],
      company: [".company-name", ".job__company"], companyFrom: () => (document.title.match(/ at (.+)$/) || [])[1] },
    { name: "Lever", test: () => ON(/(^|\.)lever\.co$/),
      desc: [".posting-page .content", ".content", "[data-qa='job-description']"], title: [".posting-headline h2", "h2"],
      company: [], companyFrom: () => (document.title.split(/\s[-–|]\s/)[0] || location.pathname.split("/")[1] || "") },
    { name: "Ashby", test: () => ON(/ashbyhq\.com$/),
      desc: ["[class*='_descriptionText']", "[class*='ashby-job-posting']", "main"], title: ["h1"], company: [],
      companyFrom: () => location.pathname.split("/")[1] || "" },
    { name: "Workday", test: () => ON(/myworkdayjobs\.com$/),
      desc: ["[data-automation-id='jobPostingDescription']"], title: ["[data-automation-id='jobPostingHeader']", "h2", "h1"], company: [],
      companyFrom: () => HOST.split(".")[0] },
  ];

  const HIRING = /\b(we(?:'re|\s+are)\s+hiring|hiring\s*[:!]|now\s+hiring|job\s+opening|opening\s+for|looking\s+for|walk-?in|send\s+(?:your\s+)?(?:cv|resume)|share\s+(?:your\s+)?(?:cv|resume)|apply\s+(?:at|via|to)|vacanc)/i;
  const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/;

  function detectJob() {
    const ld = jsonLd();
    for (const site of SITES) {
      if (!site.test()) continue;
      const d = first(site.desc);
      if (d && visible(d) && txt(d).length > 200) {
        const title = txt(first(site.title)).split("\n")[0];
        const company = txt(first(site.company)).split("\n")[0] || (site.companyFrom?.() || "");
        return { kind: "job", source: site.name, title, company: company.trim(), text: txt(d).slice(0, 60000), location: ld?.location || "" };
      }
    }
    if (ld && ld.text.length > 200) return { kind: "job", source: HOST, ...ld, text: ld.text.slice(0, 60000) };
    return null;
  }

  /** Visible LinkedIn feed posts that look like hiring posts. We read the post the user clicked on, nothing else. */
  const POST_SELECTOR = "[data-urn^='urn:li:activity'], .feed-shared-update-v2, div.update-components-text, [role='listitem'] .update-components-text";
  function postTextOf(el) {
    const body = el.querySelector?.(".update-components-text, .feed-shared-update-v2__description, [dir='ltr'] span") || el;
    return txt(body);
  }
  function postAuthor(el) {
    return txt(el.querySelector?.(".update-components-actor__title span[aria-hidden='true'], .update-components-actor__name")).split("\n")[0];
  }
  function looksLikeHiring(t) {
    return t.length > 40 && (HIRING.test(t) || (EMAIL.test(t) && /\b(cv|resume|role|position|experience|years)\b/i.test(t)));
  }

  // ------------------------------------------------------------------ API through the background worker
  const call = (msg) => new Promise((resolve, reject) => {
    try {
      chrome.runtime.sendMessage(msg, (res) => (res?.ok ? resolve(res.data) : reject(new Error(res?.error || chrome.runtime.lastError?.message || "No answer from Saige"))));
    } catch (e) {
      reject(new Error("The extension was updated. Reload this page."));
    }
  });
  const api = (path, method = "GET", body) => call({ type: "api", path, method, body });

  // ------------------------------------------------------------------ UI (shadow DOM, Graphite black, one green accent)
  const CSS = `
    :host { all: initial; }
    * { box-sizing: border-box; }
    .pill { position: fixed; right: 18px; bottom: 22px; z-index: 2147483646; display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 16px 0 12px;
      border-radius: 999px; background: #000; color: #f5f5f7; border: 1px solid #2c2c2e; font: 600 13px/1 "Google Sans", system-ui, sans-serif; cursor: pointer;
      box-shadow: 0 6px 24px rgba(0,0,0,.45); }
    .pill i { width: 10px; height: 10px; border-radius: 50%; background: #30d158; }
    .pill:hover { border-color: #30d158; }
    .pill:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible, a:focus-visible { outline: 2px solid #30d158; outline-offset: 2px; }
    .panel { position: fixed; top: 0; right: 0; bottom: 0; width: 400px; max-width: 100vw; z-index: 2147483647; background: #000; color: #f5f5f7;
      border-left: 1px solid #2c2c2e; display: flex; flex-direction: column; font: 13px/1.5 "Google Sans", system-ui, sans-serif; box-shadow: -10px 0 40px rgba(0,0,0,.5); }
    .panel[hidden], .pill[hidden] { display: none; }
    header { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border-bottom: 1px solid #1c1c1e; }
    .brand { font-size: 16px; font-weight: 600; } .brand b { color: #8e8e93; font-weight: 600; }
    .x { background: none; border: 0; color: #8e8e93; font-size: 20px; cursor: pointer; line-height: 1; padding: 4px 8px; }
    .x:hover { color: #fff; }
    main { flex: 1; overflow: auto; padding: 14px 16px 24px; display: grid; gap: 12px; align-content: start; }
    .card { background: #0b0b0c; border: 1px solid #1c1c1e; border-radius: 16px; padding: 14px; }
    h3 { margin: 0 0 8px; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: #8e8e93; font-weight: 600; }
    label { display: grid; gap: 4px; font-size: 11px; color: #8e8e93; margin-bottom: 8px; }
    input, textarea { width: 100%; padding: 8px 10px; border-radius: 10px; border: 1px solid #2c2c2e; background: #000; color: #f5f5f7; font: inherit; }
    textarea { min-height: 170px; resize: vertical; line-height: 1.45; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    button.btn, a.btn { display: inline-flex; align-items: center; justify-content: center; height: 34px; padding: 0 14px; border-radius: 999px; border: 1px solid #2c2c2e;
      background: transparent; color: #f5f5f7; font: 600 12px/1 inherit; cursor: pointer; text-decoration: none; }
    button.btn:hover, a.btn:hover { border-color: #8e8e93; }
    .btn.primary { background: #30d158; color: #000; border-color: #30d158; }
    .btn.primary:hover { background: #28b84c; }
    .btn:disabled { opacity: .5; cursor: default; }
    .btn.sm { height: 28px; padding: 0 11px; font-size: 11px; }
    .score { display: flex; gap: 14px; align-items: center; }
    .ring { --v: 0; width: 66px; height: 66px; border-radius: 50%; display: grid; place-items: center; background: conic-gradient(#30d158 calc(var(--v) * 1%), #1c1c1e 0); flex: none; }
    .ring span { width: 54px; height: 54px; border-radius: 50%; background: #0b0b0c; display: grid; place-items: center; font-size: 18px; font-weight: 600; }
    .v { font-weight: 600; margin: 0; } .dim { color: #8e8e93; font-size: 12px; margin: 2px 0 0; }
    .chips { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }
    .chips span { padding: 2px 9px; border-radius: 999px; font-size: 11px; border: 1px solid #2c2c2e; color: #8e8e93; }
    .chips.have span { border-color: #30d158; color: #30d158; }
    .note { font-size: 12px; color: #8e8e93; margin: 8px 0 0; } .ok { color: #30d158; } .err { color: #ff453a; }
    .contact { padding: 10px 0; border-top: 1px solid #1c1c1e; } .contact:first-of-type { border-top: 0; }
    .contact p { margin: 0; } .small { font-size: 11px; color: #8e8e93; }
    .status { min-height: 18px; font-size: 12px; color: #8e8e93; padding: 0 16px 12px; } .status.error { color: #ff453a; } .status.ok { color: #30d158; }
    .hint { font-size: 11px; color: #636366; margin-top: 6px; }
  `;

  const h = (tag, props = {}, ...kids) => {
    const el = Object.assign(document.createElement(tag), props);
    for (const k of kids.flat()) if (k != null && k !== false) el.append(k);
    return el;
  };
  const chips = (items, cls = "") => h("div", { className: `chips ${cls}` }, (items.length ? items : ["none"]).map((s) => h("span", { textContent: s })));

  const host = h("div");
  host.id = "saige-ai-root";
  const root = host.attachShadow({ mode: "open" });
  root.append(h("style", { textContent: CSS }));
  const pill = h("button", { className: "pill", title: "Saige AI (Ctrl+Shift+S)" }, h("i"), "Saige");
  const panel = h("div", { className: "panel", hidden: true, role: "dialog", ariaLabel: "Saige AI panel" });
  const body = h("main");
  const status = h("div", { className: "status", role: "status" });
  const closeBtn = h("button", { className: "x", ariaLabel: "Close", textContent: "×" });
  panel.append(h("header", {}, h("span", { className: "brand" }, "Saige ", h("b", { textContent: "AI" })), closeBtn), body, status);
  root.append(pill, panel);
  pill.hidden = true;
  document.documentElement.append(host);

  let ctx = null;            // what the panel works on: { kind, source, title, company, text, location, url }
  let analysis = null, resume = null;
  const say = (t, tone = "") => { status.textContent = t; status.className = `status ${tone}`; };
  const busy = async (btn, label, fn) => {
    const old = btn.textContent;
    btn.disabled = true; btn.textContent = label; say("");
    try { return await fn(); } catch (e) { say(e.message, "error"); } finally { btn.disabled = false; btn.textContent = old; }
  };
  const payload = () => ({ url: location.href, title: ctx.title, company: ctx.company, location: ctx.location || undefined, text: ctx.text });

  async function openCfgWeb() { return (await call({ type: "config" })).web; }

  function render() {
    body.replaceChildren();
    if (!ctx) return;
    const t = h("input", { value: ctx.title || "", maxLength: 200, placeholder: "Role" });
    const co = h("input", { value: ctx.company || "", maxLength: 200, placeholder: "Company" });
    t.oninput = () => { ctx.title = t.value; };
    co.oninput = () => { ctx.company = co.value; };
    const scoreBtn = h("button", { className: "btn primary", textContent: "Check my match" });
    const saveBtn = h("button", { className: "btn", textContent: "Save to Saige" });
    const analysisBox = h("div");
    scoreBtn.onclick = () => busy(scoreBtn, "Scoring…", async () => {
      analysis = await api("/ext/analyze-jd", "POST", payload());
      if (!ctx.company && analysis.company) { ctx.company = analysis.company; co.value = analysis.company; }
      if (!ctx.title && analysis.title) { ctx.title = analysis.title; t.value = analysis.title; }
      showAnalysis(analysisBox);
      hrBox.replaceChildren(hrCard());
    });
    saveBtn.onclick = () => busy(saveBtn, "Saving…", async () => {
      const r = await api("/ext/save", "POST", { ...payload(), title: ctx.title || "Job", company: ctx.company });
      say(r.created ? "Saved to Saige." : "Already in Saige. Merged with the existing job.", "ok");
    });
    body.append(
      h("section", { className: "card" }, h("h3", {}, ctx.kind === "post" ? "Hiring post" : "Job on this page"),
        h("label", {}, "Role", t), h("label", {}, "Company", co),
        h("p", { className: "dim", textContent: `${ctx.source}${ctx.kind === "post" ? " post" : ""} · ${ctx.text.length.toLocaleString()} characters read from this page` }),
        h("div", { className: "row" }, scoreBtn, saveBtn)),
      analysisBox,
      resumeCard(),
      emailCard(),
    );
    const hrBox = h("section");
    hrBox.append(hrCard());
    body.append(hrBox);
    if (analysis) showAnalysis(analysisBox);
  }

  function showAnalysis(box) {
    const a = analysis;
    const ring = h("div", { className: "ring" }, h("span", { textContent: `${a.score}%` }));
    ring.style.setProperty("--v", String(a.score));
    box.replaceChildren(h("section", { className: "card" }, h("h3", {}, "Match"),
      h("div", { className: "score" }, ring, h("div", {}, h("p", { className: "v", textContent: a.verdict?.label || a.classification }),
        h("p", { className: "dim", textContent: a.summary || "" }))),
      h("h3", { style: "margin-top:12px" }, "You have"), chips(a.have, "have"),
      h("h3", {}, "Missing"), chips(a.missing),
      ...(a.eligibility || []).filter((e) => e.status === "not_met").map((e) => h("p", { className: "note err", textContent: `${e.label}: ${e.text}` })),
      h("p", { className: "hint" }, "Scored against your verified profile. Nothing is saved until you press Save.")));
  }

  // ---- ATS resume
  function resumeCard() {
    const out = h("div");
    const gen = h("button", { className: "btn primary", textContent: "Generate ATS resume" });
    const show = () => {
      out.replaceChildren(h("p", { className: "v ok", textContent: `ATS score ${resume.score}% · ${resume.verdict}` }),
        h("p", { className: "dim", textContent: resume.missing?.length ? `Still missing: ${resume.missing.join(", ")}` : "No required keywords missing." }),
        h("div", { className: "row" }, dlBtn("Download PDF", resume.downloads.pdf), dlBtn("Download DOCX", resume.downloads.docx)));
    };
    gen.onclick = () => busy(gen, "Generating…", async () => {
      resume = await api("/ext/generate-resume", "POST", payload());
      show();
    });
    if (resume) show();
    return h("section", { className: "card" }, h("h3", {}, "ATS resume"), h("div", { className: "row", style: "margin-top:0" }, gen), out,
      h("p", { className: "hint" }, "Built only from your verified profile, aimed at this description."));
  }
  const dlBtn = (label, path) => {
    const b = h("button", { className: "btn", textContent: label });
    b.onclick = () => busy(b, "Downloading…", async () => { const r = await call({ type: "download", path }); say(`Saved ${r.name} to Downloads.`, "ok"); });
    return b;
  };

  // ---- application email (never sent)
  let draft = null;
  function emailCard() {
    const box = h("div");
    const go = h("button", { className: "btn primary", textContent: ctx.kind === "post" ? "Generate resume + draft email" : "Draft application email" });
    go.onclick = () => busy(go, "Drafting…", async () => {
      draft = await api("/ext/draft-application-email", "POST", { ...payload(), resume_id: resume?.id });
      resume = resume || { id: draft.resume_id, score: draft.score ?? 0, verdict: "Generated", missing: [], downloads: draft.downloads };
      draftView(box);
      render();
    });
    if (draft) draftView(box);
    return h("section", { className: "card" }, h("h3", {}, "Apply by email"), h("div", { className: "row", style: "margin-top:0" }, go), box,
      h("p", { className: "hint" }, "Saige never sends. You review it, then send from your own mail."));
  }

  function draftView(box) {
    const to = h("input", { value: draft.to || "", placeholder: "recipient@company.com", type: "email" });
    const subject = h("input", { value: draft.subject, maxLength: 200 });
    const text = h("textarea", { value: draft.body, maxLength: 5000 });
    const gmail = h("a", { className: "btn primary", target: "_blank", rel: "noopener", textContent: "Open in Gmail" });
    const mailto = h("a", { className: "btn", textContent: "Mail app" });
    const links = () => {
      const q = `to=${encodeURIComponent(to.value)}&su=${encodeURIComponent(subject.value)}&body=${encodeURIComponent(text.value)}`;
      gmail.href = `https://mail.google.com/mail/?view=cm&fs=1&${q}`;
      mailto.href = `mailto:${encodeURIComponent(to.value)}?subject=${encodeURIComponent(subject.value)}&body=${encodeURIComponent(text.value)}`;
    };
    [to, subject, text].forEach((e) => e.addEventListener("input", links));
    links();
    const copy = h("button", { className: "btn", textContent: "Copy" });
    copy.onclick = async () => { await navigator.clipboard.writeText(`Subject: ${subject.value}\n\n${text.value}`); say("Copied.", "ok"); };
    const save = h("button", { className: "btn", textContent: "Save as draft in Saige" });
    save.onclick = () => busy(save, "Saving…", async () => {
      if (!to.value) throw new Error("Add a recipient first.");
      const r = await api("/ext/save-draft", "POST", { company: ctx.company || "Unknown company", email: to.value, subject: subject.value, body: text.value,
        kind: "cold", page: ctx.kind === "job" ? payload() : undefined });
      say(r.note, "ok");
    });
    const pdf = dlBtn("Download PDF", draft.downloads.pdf), docx = dlBtn("DOCX", draft.downloads.docx);
    box.replaceChildren(
      h("label", { style: "margin-top:10px" }, "To", to), h("label", {}, "Subject", subject), h("label", {}, "Message (edit freely)", text),
      h("p", { className: "note ok", textContent: "Every line is a fact from your verified profile." }),
      h("div", { className: "row" }, gmail, mailto, copy), h("div", { className: "row" }, pdf, docx, save),
      h("p", { className: "hint", textContent: draft.attach_note }),
      ...(draft.emails_found?.length > 1 ? [h("p", { className: "small", textContent: `Other addresses in the post: ${draft.emails_found.slice(1).join(", ")}` })] : []));
  }

  // ---- HR contacts at the company (the user's own contacts only)
  function hrCard() {
    const box = h("div");
    const load = h("button", { className: "btn", textContent: `HR contacts at ${ctx.company || "this company"}` });
    load.onclick = () => busy(load, "Looking…", async () => {
      if (!ctx.company) throw new Error("Add the company name first.");
      const r = await api(`/ext/company-contacts?company=${encodeURIComponent(ctx.company)}`);
      box.replaceChildren();
      const c = r.caps;
      box.append(h("p", { className: "small", textContent: `Outreach today ${c.sent_today}/${c.daily_limit} · ${c.company_sent_this_week}/${c.company_week_cap} at this company this week` }));
      if (!r.contacts.length) box.append(h("p", { className: "note", textContent: "No contacts for this company in your Saige yet. Saige only uses people you added, your own inbox and postings you saved. It never looks people up or guesses emails." }));
      for (const k of r.contacts) box.append(contactRow(k, box));
    });
    return h("div", { className: "card" }, h("h3", {}, "HR contacts"), h("div", { className: "row", style: "margin-top:0" }, load), box,
      h("p", { className: "hint" }, "Only your own contacts. Drafts wait for your approval in Saige. Caps: 10/day, 3 per company per week."));
  }
  function contactRow(k, parent) {
    const row = h("div", { className: "contact" }, h("p", { textContent: k.name }),
      h("p", { className: "small", textContent: [k.title || k.role, k.email].filter(Boolean).join(" · ") }));
    const b = h("button", { className: "btn sm", textContent: "Draft outreach" });
    const out = h("div");
    b.onclick = () => busy(b, "Drafting…", async () => {
      const r = await api("/ext/save-draft", "POST", { company: ctx.company, contact_id: k.id, kind: "cold", page: ctx.kind === "job" ? payload() : undefined });
      let d = r.draft;
      const subj = h("input", { value: d.subject }), msg = h("textarea", { value: d.body });
      const upd = h("button", { className: "btn sm", textContent: "Update draft" });
      upd.onclick = () => busy(upd, "Saving…", async () => {
        d = (await api("/ext/save-draft", "POST", { company: ctx.company, outreach_id: d.id, subject: subj.value, body: msg.value })).draft;
        say("Draft updated in Saige. Approve it there.", "ok");
      });
      const cp = h("button", { className: "btn sm", textContent: "Copy" });
      cp.onclick = async () => { await navigator.clipboard.writeText(`Subject: ${subj.value}\n\n${msg.value}`); say("Copied.", "ok"); };
      const gm = d.gmail_compose ? h("a", { className: "btn sm primary", href: d.gmail_compose, target: "_blank", rel: "noopener", textContent: "Open in Gmail" }) : null;
      out.replaceChildren(h("label", { style: "margin-top:8px" }, "Subject", subj), h("label", {}, "Message", msg),
        h("p", { className: "note ok", textContent: "Saved as a draft in Saige (Outreach). Not sent." }), h("div", { className: "row" }, upd, cp, gm));
      say(r.note, "ok");
    });
    row.append(h("div", { className: "row" }, b), out);
    return row;
  }

  // ------------------------------------------------------------------ open / close / scan
  function openPanel(next) {
    if (next) { if (!ctx || ctx.text !== next.text) { analysis = resume = draft = null; } ctx = next; }
    if (!ctx) ctx = scan(true);
    render();
    panel.hidden = false;
    pill.hidden = true;
    if (!ctx.text || ctx.text.length < 30) say("Select the job text on the page, then press Scan again.", "error");
  }
  function closePanel() { panel.hidden = true; pill.hidden = !current; }

  /** "Scan this page": the user's selection, else the page's JobPosting data, else the main readable text. Visible DOM only. */
  function scan(force) {
    const sel = String(getSelection() || "").trim();
    const base = { url: location.href, source: HOST, title: "", company: "", location: "" };
    if (sel.length > 80) return { ...base, kind: EMAIL.test(sel) ? "post" : "job", text: sel.slice(0, 60000), title: (document.title || "").replace(/\s*[|·–-].*$/, "") };
    const found = detectJob();
    if (found) return found;
    if (!force) return null;
    const main = first(["main", "article", "[role='main']"]) || document.body;
    return { ...base, kind: "job", text: txt(main).slice(0, 60000), title: (document.title || "").replace(/\s*[|·–-].*$/, "").slice(0, 200) };
  }

  let current = null;
  function refresh() {
    if (!document.contains(host)) document.documentElement.append(host);
    const found = detectJob();
    current = found ? { ...found, url: location.href } : null;
    if (panel.hidden) pill.hidden = !current && !feedBtns;
    if (current && !panel.hidden && ctx && ctx.url !== current.url && ctx.kind === "job") { ctx = current; analysis = resume = draft = null; render(); }
  }

  pill.onclick = () => openPanel(current || scan(true));
  closeBtn.onclick = closePanel;
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) closePanel(); });

  chrome.runtime.onMessage.addListener((msg, _s, reply) => {
    if (msg.type === "toggle") { panel.hidden ? openPanel(current || scan(true)) : closePanel(); }
    if (msg.type === "scan") { openPanel(scan(true)); }
    reply?.({ ok: true });
  });

  // ---- LinkedIn feed: a small "Saige" button on posts that look like hiring posts (reads the post text already shown)
  let feedBtns = 0;
  function decoratePosts() {
    if (!ON(/linkedin\.com$/) || /\/jobs\//.test(location.pathname)) return;
    for (const el of document.querySelectorAll(POST_SELECTOR)) {
      const post = el.closest("[data-urn], .feed-shared-update-v2") || el;
      if (post.dataset.saigeChecked) continue;
      const t = postTextOf(post);
      if (!t) continue;
      post.dataset.saigeChecked = "1";
      if (!looksLikeHiring(t)) continue;
      const b = h("button", { textContent: "Saige: apply to this post", title: "Open Saige for this hiring post" });
      b.style.cssText = "margin:6px 12px;height:28px;padding:0 12px;border-radius:999px;border:1px solid #30d158;background:#000;color:#30d158;font:600 12px system-ui;cursor:pointer";
      b.onclick = (ev) => {
        ev.preventDefault(); ev.stopPropagation();
        const author = postAuthor(post);
        openPanel({ kind: "post", source: "LinkedIn", title: "", company: "", location: "", text: postTextOf(post).slice(0, 60000), url: location.href, author });
      };
      post.append(b);
      feedBtns++;
    }
  }

  let lastHref = "", timer = null;
  const tick = () => { refresh(); decoratePosts(); };
  new MutationObserver(() => { clearTimeout(timer); timer = setTimeout(tick, 600); }).observe(document.body, { childList: true, subtree: true });
  setInterval(() => { if (location.href !== lastHref) { lastHref = location.href; tick(); } }, 1500);
  tick();
})();

// Saige AI v2.1 content script: a Gemini-style side panel on the job or hiring post the user is looking at.
// Reads ONLY what is already on screen for the ONE job or post the user chose (never the whole LinkedIn feed, no crawling, no
// extra requests to the site, no clicking "see more" for the user). Everything the panel does is user-triggered and goes to the
// Saige API through the background worker. It NEVER presses Submit/Apply/Save on a site. Emails are sent only when the user
// presses Send in the panel and confirms "Send to x@y.com?".
(() => {
  if (window.__saigeV21) return;
  window.__saigeV21 = true;
  const X = globalThis.SaigeExtract;
  if (!X) return; // extract.js is loaded first by the manifest / background injection

  const HOST = location.hostname;
  const ON = (re) => re.test(HOST);

  // ------------------------------------------------------------------ small DOM helpers
  const txt = (el) => (el ? (el.innerText || el.textContent || "").replace(/ /g, " ").replace(/\n{3,}/g, "\n\n").trim() : "");
  const first = (sels, root = document) => {
    for (const s of sels) {
      let el = null;
      try { el = root.querySelector(s); } catch { /* bad selector on this site version */ }
      if (el && txt(el)) return el;
    }
    return null;
  };
  const visible = (el) => !!el && el.getClientRects().length > 0;
  const h = (tag, props = {}, ...kids) => {
    const el = Object.assign(document.createElement(tag), props);
    for (const k of kids.flat()) if (k != null && k !== false) el.append(k);
    return el;
  };

  // ------------------------------------------------------------------ detection (visible DOM only)
  /** schema.org JobPosting in the page's own JSON-LD (already in the DOM). */
  function jsonLd() {
    for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
      try {
        const jp = X.fromJsonLd(JSON.parse(s.textContent));
        if (jp && jp.html) {
          const d = document.createElement("div");
          d.innerHTML = jp.html; // parsed inert in a detached node, only text is read
          return { title: jp.title, company: jp.company, location: jp.location, text: txt(d) || d.textContent || "" };
        }
      } catch { /* not JSON */ }
    }
    return null;
  }

  const SITES = [
    { name: "LinkedIn", test: () => ON(/linkedin\.com$/) && /\/jobs\//.test(location.pathname),
      desc: ["#job-details", ".jobs-description__content", ".jobs-box__html-content", ".show-more-less-html__markup", ".jobs-search__job-details--container", ".description__text"],
      title: [".job-details-jobs-unified-top-card__job-title h1", ".job-details-jobs-unified-top-card__job-title", ".jobs-unified-top-card__job-title", ".top-card-layout__title",
              ".jobs-details-top-card__job-title", "[class*='job-details-jobs-unified-top-card'] h1", ".jobs-search__job-details--container h1", "h1"],
      company: [".job-details-jobs-unified-top-card__company-name a", ".job-details-jobs-unified-top-card__company-name", ".jobs-unified-top-card__company-name",
                ".topcard__org-name-link", ".top-card-layout__card a[href*='/company/']", ".job-details-jobs-unified-top-card__primary-description-container a[href*='/company/']",
                ".jobs-details-top-card__company-url", "a[href*='/company/'][class*='company-name']"] },
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

  const onFeedLike = () => X.isFeedLike(HOST, location.pathname);

  /** A job page (not a feed): role and company from the page's own job card / JSON-LD, never from document.title on LinkedIn. */
  function detectJob() {
    if (onFeedLike()) return null;
    const ld = jsonLd();
    for (const site of SITES) {
      if (!site.test()) continue;
      const d = first(site.desc);
      if (d && visible(d) && txt(d).length > 200) {
        const title = X.titleCandidate(txt(first(site.title)).split("\n")[0], ld?.title);
        const company = (txt(first(site.company)).split("\n")[0] || site.companyFrom?.() || ld?.company || "").trim();
        return { kind: "job", source: site.name, title, company, text: X.capText(txt(d)), location: ld?.location || "", url: location.href, structured: true };
      }
    }
    if (ld && ld.text.length > 200) {
      return { kind: "job", source: HOST, title: ld.title, company: ld.company, text: X.capText(ld.text), location: ld.location, url: location.href, structured: true };
    }
    return null;
  }

  // ---- LinkedIn posts: only the one post the user chose
  const POST_SELECTOR = "[data-urn^='urn:li:activity'], [data-urn^='urn:li:share'], .feed-shared-update-v2";
  const postRoot = (el) => el.closest("[data-urn], .feed-shared-update-v2") || el;
  const TEXT_SEL = ".update-components-text, .feed-shared-update-v2__description, .feed-shared-inline-show-more-text, [dir='ltr'] span";
  const SEE_MORE_SEL = "button[class*='see-more'], .feed-shared-inline-show-more-text__see-more-less-toggle";

  function postText(post) {
    const body = post.querySelector(TEXT_SEL);
    if (!body) return { text: "", truncated: false };
    let t = txt(body);
    const full = (body.textContent || "").replace(/ /g, " ").trim();
    if (full.length > t.length + 20) t = full; // the expanded text is already in the DOM: read it, don't click anything
    const more = post.querySelector(SEE_MORE_SEL);
    const collapsed = !!more && more.getAttribute("aria-expanded") !== "true" && !(full.length > txt(body).length + 20);
    return { text: X.capText(t.replace(/\s*(?:…|\.\.\.)\s*(?:see\s+)?more\s*$/i, "")), truncated: X.isTruncated(t, collapsed) };
  }
  function postAuthor(post) {
    return txt(post.querySelector(".update-components-actor__title span[aria-hidden='true'], .update-components-actor__name")).split("\n")[0];
  }
  /** Images / carousel pages of THIS post (not avatars, reactions or comments): their URLs and alt text. */
  function postImages(post) {
    const out = [];
    for (const img of post.querySelectorAll("img")) {
      if (img.closest(".update-components-actor, .social-details-social-counts, .comments-comment-item, .feed-shared-actor, [class*='reaction']")) continue;
      const src = img.currentSrc || img.src || "";
      if (!/^https:/.test(src) || (img.naturalWidth || img.width || 0) < 200) continue;
      out.push({ src, alt: (img.alt || "").trim() });
      if (out.length >= 4) break;
    }
    return out;
  }
  function postsOnScreen() {
    const seen = new Set();
    const list = [];
    for (const el of document.querySelectorAll(POST_SELECTOR)) {
      const post = postRoot(el);
      if (seen.has(post)) continue;
      seen.add(post);
      const r = post.getBoundingClientRect();
      list.push({ post, top: r.top, bottom: r.bottom, text: postText(post).text });
    }
    return list;
  }
  function ctxFromPost(post) {
    const p = postText(post);
    const imgs = postImages(post);
    return { kind: "post", source: "LinkedIn", title: "", company: "", location: "", text: p.text, url: location.href, author: postAuthor(post),
             truncated: p.truncated, images: imgs, emails: [] };
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

  // ------------------------------------------------------------------ UI (shadow DOM, Graphite black, one soft accent)
  const CSS = `
    :host { all: initial; }
    * { box-sizing: border-box; }
    :host, .panel, .pill { --bg:#0b0b0c; --surface:#161618; --line:#242427; --fg:#ececee; --dim:#9a9aa0; --acc:#6fd89a; --err:#ff6b62;
      font-family: "Google Sans","Google Sans Text","Product Sans",system-ui,-apple-system,"Segoe UI",sans-serif; }
    .pill { position: fixed; right: 18px; bottom: 22px; z-index: 2147483646; display: flex; align-items: center; gap: 8px; height: 42px; padding: 0 18px 0 12px;
      border-radius: 999px; background: var(--bg); color: var(--fg); border: 1px solid var(--line); font-size: 13px; font-weight: 500; cursor: pointer;
      box-shadow: 0 8px 28px rgba(0,0,0,.5); }
    .pill svg { width: 18px; height: 18px; }
    .pill:hover { border-color: #3a3a3f; }
    button:focus-visible, input:focus-visible, textarea:focus-visible, a:focus-visible, select:focus-visible { outline: 2px solid var(--acc); outline-offset: 2px; }
    .panel { position: fixed; top: 0; right: 0; bottom: 0; width: 420px; max-width: 100vw; z-index: 2147483647; background: var(--bg); color: var(--fg);
      border-left: 1px solid var(--line); display: flex; flex-direction: column; font-size: 14px; line-height: 1.55; box-shadow: -12px 0 44px rgba(0,0,0,.55); }
    .panel[hidden], .pill[hidden], [hidden] { display: none !important; }
    header { display: flex; align-items: center; gap: 10px; padding: 14px 16px 10px; }
    .mark { width: 22px; height: 22px; flex: none; color: var(--acc); }
    .brand { font-size: 17px; font-weight: 500; letter-spacing: -.01em; }
    .ctx { margin-left: auto; max-width: 62%; display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 12px; border-radius: 999px; border: 1px solid var(--line);
      background: var(--surface); color: var(--fg); font: inherit; font-size: 12px; cursor: pointer; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
    .ctx:hover { border-color: #3a3a3f; }
    .x { background: none; border: 0; color: var(--dim); font-size: 22px; cursor: pointer; line-height: 1; padding: 2px 6px; border-radius: 50%; }
    .x:hover { color: var(--fg); }
    .edit { display: grid; gap: 8px; padding: 0 16px 12px; border-bottom: 1px solid var(--line); }
    input, textarea, select { width: 100%; padding: 9px 12px; border-radius: 12px; border: 1px solid var(--line); background: var(--surface); color: var(--fg); font: inherit; font-size: 13px; }
    textarea { min-height: 150px; resize: vertical; line-height: 1.5; }
    label { display: grid; gap: 4px; font-size: 11px; color: var(--dim); margin-top: 8px; }
    #msgs { flex: 1; overflow: auto; padding: 8px 16px 12px; display: flex; flex-direction: column; gap: 18px; scroll-behavior: smooth; }
    .m { animation: in .28s ease both; }
    .me { align-self: flex-end; max-width: 85%; background: var(--surface); border-radius: 18px 18px 6px 18px; padding: 8px 14px; font-size: 13px; }
    .bot { display: grid; gap: 8px; }
    .bot p { margin: 0; } .bot ul { margin: 0; padding-left: 18px; display: grid; gap: 4px; } .bot b { font-weight: 600; }
    .dim { color: var(--dim); font-size: 12px; } .ok { color: var(--acc); } .err { color: var(--err); }
    .shimmer { display: grid; gap: 8px; }
    .shimmer i { display: block; height: 11px; border-radius: 6px; background: linear-gradient(90deg, #1b1b1e 25%, #2a2a2e 50%, #1b1b1e 75%); background-size: 200% 100%; animation: sh 1.3s linear infinite; }
    .shimmer i:nth-child(1) { width: 86%; } .shimmer i:nth-child(2) { width: 64%; } .shimmer i:nth-child(3) { width: 40%; }
    .score { display: flex; gap: 14px; align-items: center; }
    .ring { --v: 0; width: 62px; height: 62px; border-radius: 50%; display: grid; place-items: center; background: conic-gradient(var(--acc) calc(var(--v) * 1%), #242427 0); flex: none; }
    .ring span { width: 50px; height: 50px; border-radius: 50%; background: var(--bg); display: grid; place-items: center; font-size: 16px; font-weight: 500; }
    .chips { display: flex; flex-wrap: wrap; gap: 6px; }
    .chips span { padding: 2px 10px; border-radius: 999px; font-size: 12px; border: 1px solid var(--line); color: var(--dim); }
    .chips.have span { border-color: #2f5b43; color: var(--acc); }
    .lbl { font-size: 11px; letter-spacing: .05em; text-transform: uppercase; color: var(--dim); }
    .row { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
    .btn { display: inline-flex; align-items: center; justify-content: center; height: 32px; padding: 0 14px; border-radius: 999px; border: 1px solid var(--line); background: transparent;
      color: var(--fg); font: inherit; font-size: 12px; font-weight: 500; cursor: pointer; text-decoration: none; }
    .btn:hover { background: var(--surface); }
    .btn.primary { background: var(--acc); color: #06150c; border-color: var(--acc); } .btn.primary:hover { background: #5cc486; }
    .btn:disabled { opacity: .5; cursor: default; }
    .draft { display: grid; gap: 2px; border-left: 2px solid var(--line); padding-left: 12px; }
    .confirm { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 8px 0; }
    .contact { padding: 8px 0; border-top: 1px solid var(--line); } .contact:first-child { border-top: 0; }
    .tail { padding: 8px 16px 14px; display: grid; gap: 10px; border-top: 1px solid #151517; }
    #sug { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; padding-bottom: 2px; }
    #sug::-webkit-scrollbar { display: none; }
    #sug button { flex: none; height: 30px; padding: 0 13px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--fg); font: inherit; font-size: 12px; cursor: pointer; }
    #sug button:hover { border-color: #3a3a3f; } #sug button:disabled { opacity: .45; cursor: default; }
    .composer { display: flex; align-items: center; gap: 8px; background: var(--surface); border: 1px solid var(--line); border-radius: 999px; padding: 4px 4px 4px 16px; }
    .composer:focus-within { border-color: #3a3a3f; }
    .composer input { border: 0; background: transparent; padding: 8px 0; border-radius: 0; outline: none; }
    .send { width: 34px; height: 34px; flex: none; border-radius: 50%; border: 0; background: var(--acc); color: #06150c; cursor: pointer; display: grid; place-items: center; }
    .send:disabled { opacity: .4; cursor: default; } .send svg { width: 16px; height: 16px; }
    @keyframes in { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: none; } }
    @keyframes sh { to { background-position: -200% 0; } }
    @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; scroll-behavior: auto !important; } }
  `;

  const SVG = "http://www.w3.org/2000/svg";
  const sparkle = (cls) => {
    const s = document.createElementNS(SVG, "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("class", cls);
    s.setAttribute("aria-hidden", "true");
    const p = document.createElementNS(SVG, "path");
    p.setAttribute("d", "M12 2c.6 5.2 4.8 9.4 10 10-5.2.6-9.4 4.8-10 10-.6-5.2-4.8-9.4-10-10 5.2-.6 9.4-4.8 10-10z");
    p.setAttribute("fill", "currentColor");
    s.append(p);
    return s;
  };
  const sendIcon = () => {
    const s = document.createElementNS(SVG, "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    const p = document.createElementNS(SVG, "path");
    p.setAttribute("d", "M3 20l18-8L3 4v6l11 2-11 2z");
    p.setAttribute("fill", "currentColor");
    s.append(p);
    return s;
  };

  const host = h("div");
  host.id = "saige-ai-root";
  const root = host.attachShadow({ mode: "open" });
  root.append(h("style", { textContent: CSS }));
  const pill = h("button", { className: "pill", title: "Saige (Ctrl+Shift+S)" }, sparkle(""), "Saige");
  const panel = h("div", { className: "panel", hidden: true, role: "dialog", ariaLabel: "Saige panel" });
  const ctxBtn = h("button", { className: "ctx", title: "Tap to edit the role and company" });
  const closeBtn = h("button", { className: "x", ariaLabel: "Close", textContent: "×" });
  const editBox = h("div", { className: "edit", hidden: true });
  const msgs = h("main", { id: "msgs", ariaLive: "polite" });
  const sug = h("div", { id: "sug" });
  const input = h("input", { placeholder: "Ask Saige about this job…", maxLength: 2000, ariaLabel: "Ask Saige about this job" });
  const sendBtn = h("button", { className: "send", ariaLabel: "Send", title: "Send" }, sendIcon());
  panel.append(h("header", {}, sparkle("mark"), h("span", { className: "brand", textContent: "Saige" }), ctxBtn, closeBtn), editBox, msgs,
    h("div", { className: "tail" }, sug, h("div", { className: "composer" }, input, sendBtn)));
  root.append(pill, panel);
  pill.hidden = true;
  document.documentElement.append(host);

  // ------------------------------------------------------------------ conversation state
  let ctx = null;              // { kind: job|post|none, source, title, company, location, text, url, emails, images, truncated }
  let analysis = null, resume = null, me = null;
  let chat = [];               // [{role, content}] for /ext/chat
  let working = false, epoch = 0;

  const payload = () => ({ url: ctx.url || location.href, title: (ctx.title || "").slice(0, 200), company: ctx.company || "", location: ctx.location || undefined, text: X.capText(ctx.text) });
  const hasJob = () => ctx && ctx.kind !== "none" && ctx.text && ctx.text.length >= 30;
  const firstName = () => String(me?.name || "").trim().split(/\s+/)[0] || "";

  const scrollEnd = () => { msgs.scrollTop = msgs.scrollHeight; };
  function add(cls, ...kids) {
    const el = h("div", { className: `m ${cls}` }, ...kids);
    msgs.append(el);
    scrollEnd();
    return el;
  }
  const you = (t) => add("me", t);
  const bot = (...kids) => add("bot", ...kids);

  /** Markdown-ish text -> safe DOM: **bold**, "- " bullets, blank-line paragraphs. No innerHTML. */
  function md(text) {
    const frag = document.createDocumentFragment();
    const inline = (s) => String(s).split(/(\*\*[^*]+\*\*)/).map((p) => (/^\*\*[^*]+\*\*$/.test(p) ? h("b", { textContent: p.slice(2, -2) }) : p));
    let ul = null;
    for (const line of String(text || "").split("\n")) {
      const b = /^\s*(?:[-*•])\s+(.*)$/.exec(line);
      if (b) {
        if (!ul) { ul = h("ul"); frag.append(ul); }
        ul.append(h("li", {}, inline(b[1])));
      } else {
        ul = null;
        if (line.trim()) frag.append(h("p", {}, inline(line)));
      }
    }
    return frag;
  }
  const botText = (t, cls = "") => bot(h("div", { className: cls }, md(t)));
  const chipsEl = (items, cls = "") => h("div", { className: `chips ${cls}` }, items.map((s) => h("span", { textContent: s })));
  const thinking = () => add("bot", h("div", { className: "shimmer", ariaLabel: "Saige is thinking" }, h("i"), h("i"), h("i")));

  const CHIPS = [
    ["Check my match", () => doMatch()], ["Write ATS resume", () => doResume()], ["Draft email to HR", () => doEmail()],
    ["Find HR contacts", () => doHr()], ["Interview questions", () => doChat("Interview questions")], ["What's missing?", () => doChat("What's missing?")],
    ["Drafts", () => doDrafts()],
  ];
  const chipBtns = CHIPS.map(([label, fn]) => {
    const b = h("button", { textContent: label, type: "button" });
    b.onclick = () => run(label, fn, label !== "Drafts");
    sug.append(b);
    return { b, label };
  });
  function setBusy(on) {
    working = on;
    for (const { b, label } of chipBtns) b.disabled = on || (!hasJob() && label !== "Drafts");
    sendBtn.disabled = on;
  }

  /** One user-triggered turn: show the user's message, a shimmer while waiting, then the result (or a friendly error). */
  async function run(label, fn, needsJob = true) {
    if (working) return;
    if (needsJob && !hasJob()) {
      you(label);
      return botText("I need a job or a hiring post first. Open a job, or click **Saige** on a hiring post, then ask again.");
    }
    you(label);
    setBusy(true);
    const wait = thinking();
    const mine = epoch;
    try {
      const nodes = await fn();
      wait.remove();
      if (mine === epoch && nodes) bot(...[].concat(nodes));
    } catch (e) {
      wait.remove();
      botText(e.message || "Something went wrong.", "err");
    } finally {
      setBusy(false);
    }
  }

  function renderCtx() {
    const label = ctx && ctx.kind !== "none" && (ctx.title || ctx.company) ? [ctx.title || "Role", ctx.company || "Company"].join(" · ") : "Set role · company";
    ctxBtn.textContent = `${label} ▾`;
    ctxBtn.hidden = !ctx || ctx.kind === "none";
    setBusy(working);
  }
  ctxBtn.onclick = () => {
    if (!editBox.hidden) { editBox.hidden = true; return; }
    const t = h("input", { value: ctx.title || "", maxLength: 200, placeholder: "Role" });
    const co = h("input", { value: ctx.company || "", maxLength: 200, placeholder: "Company" });
    t.oninput = () => { ctx.title = t.value; renderCtx(); };
    co.oninput = () => { ctx.company = co.value; renderCtx(); };
    const done = h("button", { className: "btn", textContent: "Done" });
    done.onclick = () => { editBox.hidden = true; };
    editBox.replaceChildren(t, co, h("div", { className: "row" }, done));
    editBox.hidden = false;
    t.focus();
  };

  // ------------------------------------------------------------------ actions (each is a chip-triggered message)
  function matchView(a) {
    const ring = h("div", { className: "score" });
    const r = h("div", { className: "ring" }, h("span", { textContent: `${a.score}%` }));
    r.style.setProperty("--v", String(a.score));
    ring.append(r, h("div", {}, h("p", {}, h("b", { textContent: a.verdict?.label || a.classification || "Match" })), h("p", { className: "dim", textContent: a.summary || "" })));
    const save = h("button", { className: "btn", textContent: "Save job to Saige" });
    save.onclick = async () => {
      save.disabled = true;
      try { const s = await api("/ext/save", "POST", { ...payload(), title: ctx.title || "Job" }); save.textContent = s.created ? "Saved" : "Already saved"; } catch (e) { save.textContent = e.message; }
    };
    return [ring, h("div", {}, h("div", { className: "lbl", textContent: "You have" }), chipsEl(a.have?.length ? a.have : ["none yet"], "have")),
      h("div", {}, h("div", { className: "lbl", textContent: "Missing" }), chipsEl(a.missing?.length ? a.missing : ["nothing important"])),
      ...(a.eligibility || []).filter((e) => e.status === "not_met").map((e) => h("p", { className: "err", textContent: `${e.label}: ${e.text}` })),
      h("p", { className: "dim", textContent: "Scored against your verified profile. Nothing is saved until you ask." }), h("div", { className: "row" }, save)];
  }
  async function doMatch() {
    analysis = analysis || (await api("/ext/analyze-jd", "POST", payload()));
    if (analysis.company && !ctx.company) ctx.company = analysis.company;
    if (analysis.title && !ctx.title) ctx.title = analysis.title;
    if (analysis.emails?.length) ctx.emails = analysis.emails;
    renderCtx();
    return matchView(analysis);
  }

  const dlBtn = (label, path) => {
    const b = h("button", { className: "btn", textContent: label });
    b.onclick = async () => {
      b.disabled = true;
      try { const r = await call({ type: "download", path }); b.textContent = `Saved ${r.name}`; } catch (e) { b.textContent = e.message; b.disabled = false; }
    };
    return b;
  };
  async function doResume() {
    resume = resume || (await api("/ext/generate-resume", "POST", payload()));
    return [h("p", {}, h("b", { className: "ok", textContent: `ATS score ${resume.score}%` }), ` · ${resume.verdict}`),
      h("p", { className: "dim", textContent: resume.missing?.length ? `Still missing: ${resume.missing.join(", ")}` : "No required keywords missing." }),
      h("div", { className: "row" }, dlBtn("Download PDF", resume.downloads.pdf), dlBtn("Download DOCX", resume.downloads.docx)),
      h("p", { className: "dim", textContent: "Built only from your verified profile, aimed at this description." })];
  }

  /** An editable email draft with Copy / Open in Gmail / Send (confirm) / Discard. Saige never sends without the user's click + confirm. */
  function draftBlock(d) {
    const to = h("input", { value: d.to || "", placeholder: "recipient@company.com", type: "email" });
    const subject = h("input", { value: d.subject || "", maxLength: 200 });
    const text = h("textarea", { value: d.body || "", maxLength: 5000 });
    const attach = h("select", { ariaLabel: "Attach resume" });
    for (const [v, l] of [["pdf", "Attach resume (PDF)"], ["docx", "Attach resume (DOCX)"], ["", "No attachment"]]) attach.append(h("option", { value: v, textContent: l }));
    if (!d.resumeId) attach.value = "";
    const gmail = h("a", { className: "btn", target: "_blank", rel: "noopener", textContent: "Open in Gmail" });
    const links = () => { gmail.href = `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(to.value)}&su=${encodeURIComponent(subject.value)}&body=${encodeURIComponent(text.value)}`; };
    [to, subject, text].forEach((e) => e.addEventListener("input", links));
    links();
    const copy = h("button", { className: "btn", textContent: "Copy" });
    copy.onclick = async () => { await navigator.clipboard.writeText(`Subject: ${subject.value}\n\n${text.value}`); copy.textContent = "Copied"; };
    const send = h("button", { className: "btn primary", textContent: "Send" });
    const discard = d.draftId ? h("button", { className: "btn", textContent: "Discard" }) : null;
    const note = h("div", { className: "dim" });
    const actions = h("div", { className: "row" }, send, copy, gmail, discard);
    const box = h("div", { className: "draft" }, h("div", { className: "lbl", textContent: "Draft · not sent" }),
      h("label", {}, "To", to), h("label", {}, "Subject", subject), h("label", {}, "Message (edit freely)", text), attach, actions, note,
      h("p", { className: "dim", textContent: d.attach_note || "You review it. It is sent only when you press Send and confirm." }));
    const setNote = (t, cls = "dim") => { note.className = cls; note.textContent = t; };
    send.onclick = () => {
      if (!to.value || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(to.value)) return setNote("Add a valid recipient first.", "err");
      const yes = h("button", { className: "btn primary", textContent: "Yes, send" });
      const no = h("button", { className: "btn", textContent: "Cancel" });
      const conf = h("div", { className: "confirm" }, h("span", { textContent: `Send to ${to.value}?` }), yes, no);
      actions.hidden = true;
      note.replaceChildren(conf);
      note.className = "";
      no.onclick = () => { actions.hidden = false; note.replaceChildren(); };
      yes.onclick = async () => {
        yes.disabled = no.disabled = true;
        yes.textContent = "Sending…";
        try {
          const r = await api("/ext/send-email", "POST", { draft_id: d.draftId || undefined, to: to.value, subject: subject.value, body: text.value,
            company: ctx?.company || d.company || "", role: ctx?.title || d.role || "", attach_resume_id: attach.value ? d.resumeId : undefined,
            format: attach.value || "pdf", confirm: true });
          const when = new Date(r.sent_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
          [to, subject, text, attach].forEach((e) => { e.disabled = true; });
          actions.replaceChildren();
          actions.hidden = false;
          setNote(`Sent to ${r.to} at ${when}${r.attached?.length ? ` with ${r.attached[0]}` : ""}. Replies are tracked in Saige.`, "ok");
        } catch (e) {
          actions.hidden = false;
          note.className = "err";
          note.replaceChildren(e.message);
          if (/Connect Gmail/i.test(e.message)) {
            const open = h("a", { className: "btn", target: "_blank", rel: "noopener", textContent: "Open Integrations" });
            call({ type: "config" }).then((c) => { open.href = `${c.web}/integrations`; });
            note.append(" ", open);
          }
        }
      };
    };
    if (discard) {
      discard.onclick = async () => {
        discard.disabled = true;
        try { await api(`/ext/drafts/${encodeURIComponent(d.draftId)}/discard`, "POST"); box.replaceChildren(h("p", { className: "dim", textContent: "Draft discarded." })); } catch (e) { setNote(e.message, "err"); discard.disabled = false; }
      };
    }
    return box;
  }

  async function doEmail() {
    const d = await api("/ext/draft-application-email", "POST", { ...payload(), resume_id: resume?.id });
    resume = resume || { id: d.resume_id, score: d.score ?? 0, verdict: "Generated", missing: [], downloads: d.downloads };
    if (d.emails_found?.length) ctx.emails = d.emails_found;
    return [h("p", { textContent: d.to ? `Here's a draft to ${d.to}. Every line is a fact from your verified profile.` : "Here's a draft. I couldn't find an address in this post: add one below." }),
      draftBlock({ ...d, draftId: null, resumeId: d.resume_id, company: d.company }),
      h("div", { className: "row" }, dlBtn("Resume PDF", d.downloads.pdf), dlBtn("DOCX", d.downloads.docx))];
  }

  async function doHr() {
    if (!ctx.company) throw new Error("Tap the chip at the top and add the company name first.");
    const r = await api(`/ext/company-contacts?company=${encodeURIComponent(ctx.company)}`);
    const out = [h("p", { className: "dim", textContent: `Outreach today ${r.caps.sent_today}/${r.caps.daily_limit} · ${r.caps.company_sent_this_week}/${r.caps.company_week_cap} at ${ctx.company} this week` })];
    if (!r.contacts.length) out.push(h("p", { textContent: `No contacts for ${ctx.company} in your Saige yet. I only use people you added, your own inbox and postings you saved. I never look people up or guess emails.` }));
    for (const k of r.contacts) {
      const b = h("button", { className: "btn", textContent: "Draft outreach" });
      const slot = h("div");
      b.onclick = async () => {
        b.disabled = true;
        try {
          const s = await api("/ext/save-draft", "POST", { company: ctx.company, contact_id: k.id, kind: "cold", page: hasJob() && ctx.kind === "job" ? payload() : undefined });
          slot.replaceChildren(draftBlock({ to: k.email || "", subject: s.draft.subject, body: s.draft.body, draftId: `out:${s.draft.id}`, company: ctx.company, attach_note: s.note }));
        } catch (e) { slot.replaceChildren(h("p", { className: "err", textContent: e.message })); b.disabled = false; }
      };
      out.push(h("div", { className: "contact" }, h("p", {}, h("b", { textContent: k.name })), h("p", { className: "dim", textContent: [k.title || k.role, k.email].filter(Boolean).join(" · ") }), h("div", { className: "row" }, b), slot));
    }
    return out;
  }

  async function doDrafts() {
    const r = await api("/ext/drafts");
    if (!r.drafts.length) return [h("p", { textContent: "No pending drafts. Drafts you save from the panel, plus application emails waiting for approval, show up here." })];
    const out = [h("p", { textContent: `You have ${r.drafts.length} pending draft${r.drafts.length > 1 ? "s" : ""}.` })];
    if (!r.gmail_connected) out.push(h("p", { className: "dim", textContent: "Connect Gmail in Saige → Integrations to send from here. You can still copy or open them in Gmail." }));
    for (const d of r.drafts) {
      const slot = h("div");
      const open = h("button", { className: "btn", textContent: "Open" });
      const drop = h("button", { className: "btn", textContent: "Discard" });
      open.onclick = () => { slot.replaceChildren(draftBlock({ to: d.to, subject: d.subject, body: d.body, draftId: d.id, resumeId: d.resume_id, company: d.company, role: d.role })); open.hidden = true; };
      drop.onclick = async () => {
        drop.disabled = true;
        try { await api(`/ext/drafts/${encodeURIComponent(d.id)}/discard`, "POST"); row.replaceChildren(h("p", { className: "dim", textContent: "Draft discarded." })); } catch (e) { slot.replaceChildren(h("p", { className: "err", textContent: e.message })); drop.disabled = false; }
      };
      const row = h("div", { className: "contact" }, h("p", {}, h("b", { textContent: d.subject })),
        h("p", { className: "dim", textContent: [d.source === "application" ? "Application" : "Outreach", d.company, d.to].filter(Boolean).join(" · ") + (d.cooldown ? " · emailed this company recently" : "") }),
        h("div", { className: "row" }, d.can_send ? open : null, drop), slot);
      out.push(row);
    }
    return out;
  }

  async function doChat(message) {
    const r = await api("/ext/chat", "POST", { message, job: { role: ctx?.title || "", company: ctx?.company || "", text: hasJob() ? X.capText(ctx.text) : "" }, history: chat.slice(-10) });
    chat.push({ role: "user", content: message }, { role: "assistant", content: r.reply });
    return [md(r.reply)];
  }

  async function ask() {
    const q = input.value.trim();
    if (!q || working) return;
    input.value = "";
    run(q, () => doChat(q), false);
  }
  sendBtn.onclick = ask;
  input.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask(); } });

  // ------------------------------------------------------------------ preparing the chosen job / post
  const article = (w) => (/^[aeiou]/i.test(w) ? "an" : "a");

  async function prepare() {
    const mine = ++epoch;
    analysis = resume = null;
    chat = [];
    msgs.replaceChildren();
    editBox.hidden = true;
    renderCtx();
    if (!ctx || ctx.kind === "none") {
      botText(ctx?.note || "**Open a job** or click **Saige** on a hiring post, and I'll check your match, write an ATS resume and draft the email. You can also select a job description on any page and press Scan.");
      return;
    }
    setBusy(true);
    const wait = thinking();
    try {
      if (ctx.truncated) ctx.note = "This post is cut off. Click **see more** on LinkedIn, then open Saige on it again for the full text.";
      // images / carousels of THIS post: Claude vision on the server (needs the AI key), alt text otherwise
      const alts = (ctx.images || []).map((i) => i.alt).filter(Boolean);
      const imageTexts = [];
      if (ctx.kind === "post" && ctx.images?.length && (ctx.text.length < 600 || !X.looksLikeHiring(ctx.text))) {
        for (const img of ctx.images.slice(0, 3)) {
          try {
            const r = await api("/ext/read-image", "POST", { image_url: img.src, alt: img.alt });
            if (r.text) imageTexts.push(r.text);
            if (r.message && !ctx.imageNote) ctx.imageNote = r.message;
          } catch (e) { ctx.imageNote = ctx.imageNote || e.message; }
          if (mine !== epoch) return;
        }
      }
      ctx.text = X.mergePostText({ text: ctx.text, alts, imageTexts });
      // the backend extractor is preferred; the local parser is the fallback
      let info = null;
      try {
        info = await api("/ext/extract", "POST", { text: ctx.text.slice(0, X.MAX_TEXT), title: ctx.structured ? ctx.title : "", company: ctx.structured ? ctx.company : "", source: ctx.source });
      } catch { /* offline or no token: the greeting below reports it */ }
      info = info || X.parseHiringPost(ctx.text, { title: ctx.structured ? ctx.title : "", company: ctx.structured ? ctx.company : "" });
      if (info.role && !ctx.structured) ctx.title = info.role; else if (!ctx.title) ctx.title = info.role || "";
      if (!ctx.company) ctx.company = info.company || "";
      ctx.location = ctx.location || info.location || "";
      ctx.emails = info.emails || [];
      ctx.isJob = ctx.structured ? true : info.is_job !== false;
      renderCtx();
      if (mine !== epoch) return;
      if (!ctx.isJob) {
        wait.remove();
        ctx.kind = ctx.kind === "post" ? "none" : ctx.kind;
        renderCtx();
        botText((ctx.imageNote ? ctx.imageNote + "\n\n" : "") + "This doesn't look like a hiring post, so I didn't analyse it. **Click Saige on a hiring post** or open a job and I'll take it from there.");
        return;
      }
      try { me = me || (await api("/ext/me")); } catch { /* name is optional */ }
      analysis = await api("/ext/analyze-jd", "POST", payload());
      if (mine !== epoch) return;
      ctx.title = ctx.title || analysis.title || "";
      ctx.company = ctx.company || analysis.company || "";
      renderCtx();
      wait.remove();
      const role = ctx.title || "role";
      const hi = firstName() ? `Hi ${firstName()}, ` : "Hi, ";
      bot(h("p", {}, `${hi}this looks like ${article(role)} `, h("b", { textContent: role }), ctx.company ? ` role at ${ctx.company}` : " role", " — ", h("b", { className: "ok", textContent: `${analysis.score}% match` }), "."),
        ...(ctx.note ? [md(ctx.note)] : []), ...(ctx.imageNote ? [h("p", { className: "dim", textContent: ctx.imageNote })] : []),
        ...matchView(analysis), h("p", { className: "dim", textContent: "Ask me anything about it, or pick an option below." }));
    } catch (e) {
      wait.remove();
      botText(e.message || "I couldn't read this one.", "err");
    } finally {
      if (mine === epoch) setBusy(false);
    }
  }

  // ------------------------------------------------------------------ open / close / scan
  function selectionCtx() {
    const sel = String(getSelection() || "").trim();
    if (sel.length < 80) return null;
    return { kind: X.emailsIn(sel).length ? "post" : "job", source: HOST, title: "", company: "", location: "", text: X.capText(sel), url: location.href, images: [], emails: [] };
  }
  const NONE_FEED = "I only read the one post you pick. **Click Saige on a hiring post** in your feed (or scroll so a hiring post is in the middle of the screen and press Ctrl+Shift+S), or open a job.";

  /** What to analyse when the panel opens from the pill, the shortcut or the popup: the user's selection, a job page, or the post nearest the centre. */
  function chooseContext() {
    const sel = selectionCtx();
    if (sel) return sel;
    if (onFeedLike()) {
      const posts = postsOnScreen();
      const i = X.pickPost(posts.map(({ top, bottom, text }) => ({ top, bottom, text })), window.innerHeight);
      return i >= 0 ? ctxFromPost(posts[i].post) : { kind: "none", note: NONE_FEED, text: "", images: [] };
    }
    return detectJob() || { kind: "none", note: "I couldn't find a job on this page. Select the job description text, then press Scan, or open a job page.", text: "", images: [] };
  }
  function openWith(next) {
    ctx = next;
    panel.hidden = false;
    pill.hidden = true;
    prepare();
  }
  function closePanel() { panel.hidden = true; pill.hidden = !current && !feedBtns; }

  let current = null;
  function refresh() {
    if (!document.contains(host)) document.documentElement.append(host);
    current = detectJob();
    if (panel.hidden) pill.hidden = !current && !feedBtns;
    if (current && !panel.hidden && ctx && ctx.kind === "job" && ctx.url !== current.url) { ctx = current; prepare(); }
  }

  pill.onclick = () => openWith(chooseContext());
  closeBtn.onclick = closePanel;
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); closePanel(); } });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !panel.hidden) closePanel(); });

  chrome.runtime.onMessage.addListener((msg, _s, reply) => {
    if (msg.type === "toggle") { panel.hidden ? openWith(chooseContext()) : closePanel(); }
    if (msg.type === "scan") { openWith(chooseContext()); }
    reply?.({ ok: true });
  });

  // ---- LinkedIn feed: a small "Saige" button on posts that look like hiring posts (reads the post text already shown)
  let feedBtns = 0;
  function decoratePosts() {
    if (!ON(/linkedin\.com$/) || !onFeedLike()) return;
    for (const el of document.querySelectorAll(POST_SELECTOR)) {
      const post = postRoot(el);
      if (post.dataset.saigeChecked) continue;
      const t = postText(post).text;
      const hasImg = postImages(post).length > 0;
      if (!t && !hasImg) continue;
      post.dataset.saigeChecked = "1";
      if (!X.looksLikeHiring(t) && !(hasImg && t.length < 200 && X.looksLikeHiring(t + " " + postImages(post).map((i) => i.alt).join(" ")))) continue;
      const b = h("button", { textContent: "Saige: apply to this post", title: "Open Saige for this hiring post" });
      b.style.cssText = "margin:6px 12px;height:28px;padding:0 12px;border-radius:999px;border:1px solid #6fd89a;background:#0b0b0c;color:#6fd89a;font:500 12px system-ui;cursor:pointer";
      b.onclick = (ev) => { ev.preventDefault(); ev.stopPropagation(); openWith(ctxFromPost(post)); };
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

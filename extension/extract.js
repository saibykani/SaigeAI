// Saige AI: pure detection helpers (no DOM, no network). Loaded before content.js and unit-tested with `node --test extension/`.
// Everything here works on plain strings / objects the content script reads from the post or job the user is looking at.
(function (root) {
  const MAX_TEXT = 8000;

  const ROLE_WORDS = /\b(engineer|engineering|sdet|tester|qa|qe|developer|programmer|analyst|architect|lead|manager|consultant|specialist|administrator|designer|scientist|researcher|associate|executive|recruiter|officer|director|intern|trainee|coordinator|technician|devops|sre|admin|writer|accountant|strategist|representative|head|principal|supervisor|assistant|advisor|owner)\b/i;
  const NOT_ROLE_PAGE = /^(feed|home|jobs|search|search results|notifications|messaging|my network|linkedin|saved jobs|job search|people|companies)$/i;
  const HIRING = /\b(we(?:'re|\s+are)\s+hiring|hiring\s*[:!]|now\s+hiring|job\s+opening|opening\s+for|looking\s+for|walk-?in|send\s+(?:your\s+)?(?:cv|resume)|share\s+(?:your\s+)?(?:cv|resume)|apply\s+(?:at|via|to|now)|vacanc|urgent\s+requirement|we\s+are\s+looking)/i;
  const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;
  const SEG = "([^\\n.!?,;|()@:]{3,80}?)";
  const SEG_END = "(?=\\s+(?:at|in|with|for|to|@|[-\\u2013\\u2014])\\s|\\s*[\\n.!?,;|(:]|\\s*$)";
  const ROLE_PATTERNS = [
    new RegExp("\\b(?:role|position|designation|job\\s+title|job\\s+role|post)\\s*[:\\-\\u2013]\\s*" + SEG + SEG_END, "i"),
    new RegExp("\\b(?:hiring|looking\\s+for|opening\\s+for|openings?\\s+for|vacanc(?:y|ies)\\s+for|recruiting|seeking|need)\\b[\\s:!.\\-\\u2013]*(?:an?\\s+|the\\s+)?(?:urgent(?:ly)?\\s+)?(?:for\\s+(?:an?\\s+|the\\s+)?)?" + SEG + SEG_END, "i"),
    new RegExp("(?:^|\\n|[.!?:]\\s)\\s*" + SEG + "\\s+(?:opening|vacancy|position|role)\\s+(?:at|in|with)\\b", "i"),
  ];
  const CO = "([A-Z][A-Za-z0-9&.'\\-]*(?:\\s+(?:[A-Z][A-Za-z0-9&.'\\-]*|&|of|and)){0,3})";
  const COMPANY_PATTERNS = [
    /^\s*(?:company|company name|organi[sz]ation|employer|client)\s*[:\-\u2013]\s*(.+?)\s*$/im,
    new RegExp("(?:[Hh]iring|[Oo]pening|[Vv]acancy|[Pp]osition|[Rr]ole|[Oo]penings)\\s+(?:[Ff]or\\s+)?(?:[^\\n.!?]{0,60}?\\s)?(?:[Aa]t|@|[Ww]ith)\\s+" + CO + "(?=[\\s,.!)\\n]|$)"),
    new RegExp("(?:\\bat|@)\\s+" + CO + "\\s*[,.!\\n(]"),
    new RegExp("^\\s*" + CO + "\\s+(?:is|are)\\s+(?:now\\s+)?hiring\\b", "m"),
  ];
  const BAD_COMPANY = new Set(["us", "the", "our", "this", "my", "linkedin", "naukri", "indeed", "india", "remote", "hybrid", "immediate", "the company"]);
  const CITIES = ["Bengaluru", "Bangalore", "Hyderabad", "Pune", "Chennai", "Mumbai", "Delhi", "Gurgaon", "Gurugram", "Noida", "Kolkata", "Ahmedabad", "Kochi", "Coimbatore", "Jaipur", "Chandigarh", "Indore", "Remote", "Hybrid", "Pan India", "London", "Dubai", "Singapore", "Berlin", "Toronto"];

  /** Strip LinkedIn's "(23)" notification counter and " | LinkedIn" style suffixes. */
  function cleanTitle(s) {
    let t = String(s || "").trim(), prev = null;
    while (prev !== t) {
      prev = t;
      t = t.replace(/^\(\d+\+?\)\s*/, "").replace(/\s*[|\u00b7\-\u2013\u2014]\s*(?:LinkedIn|Naukri(?:\.com)?|Indeed(?:\.com)?|Glassdoor|Greenhouse|Lever)\s*$/i, "").trim();
    }
    return t;
  }

  function cleanRole(s) {
    let t = cleanTitle(s).replace(/[^\w\s/&+.#()\-\u2013|,@':]/g, " ").replace(/#(\w)/g, "$1").replace(/\s+/g, " ").trim();
    t = t.replace(/^(?:(?:urgent(?:ly)?|immediate|hiring|now\s+hiring|opening|job\s+opening|walk-?in|role)\b[\s:!\-\u2013|]*)+/i, "");
    t = t.replace(/\s*(?:[|\-\u2013\u2014,(@]\s*(?:india|remote|hybrid|onsite|on-site|wfh|full[- ]time|contract|immediate joiner)\)?\s*)+$/i, "").trim();
    return t.replace(/^[\s:\-\u2013|,.]+|[\s:\-\u2013|,.]+$/g, "");
  }

  function roleOk(s) {
    return !!s && ROLE_WORDS.test(s) && s.split(/\s+/).length <= 7 && !/\b(we|our|you|your|is|are|will|can)\b/i.test(s) && !NOT_ROLE_PAGE.test(s);
  }

  /** A page title is a usable role only when it reads like a role; never on feed/search pages. */
  function titleCandidate(...cands) {
    for (const c of cands) {
      const r = cleanRole(c);
      if (roleOk(r)) return r;
    }
    return "";
  }

  function emailsIn(text) {
    const skip = /^(no-?reply|donotreply|notifications?|mailer-daemon|privacy|support)@/i;
    const seen = [...new Set((String(text || "").match(EMAIL) || []).map((e) => e.replace(/^\.+|\.+$/g, "").toLowerCase()).filter((e) => !skip.test(e)))];
    const rank = ["career", "hr", "job", "talent", "hiring", "recruit", "resume", "cv"];
    return seen.sort((a, b) => (rank.some((r) => b.startsWith(r)) ? 1 : 0) - (rank.some((r) => a.startsWith(r)) ? 1 : 0));
  }

  function findRole(text) {
    for (const rx of ROLE_PATTERNS) {
      const g = new RegExp(rx.source, rx.flags + "g");
      let m;
      while ((m = g.exec(text))) {
        const r = cleanRole(m[1]);
        if (roleOk(r)) return r;
      }
    }
    return "";
  }

  function findCompany(text, role) {
    for (const rx of COMPANY_PATTERNS) {
      const g = new RegExp(rx.source, rx.flags.replace("g", "") + "g");
      let m;
      while ((m = g.exec(text))) {
        const name = String(m[1]).replace(/\s+/g, " ").replace(/^[\s.,:;\-\u2013|"']+|[\s.,:;\-\u2013|"']+$/g, "");
        if (name && !BAD_COMPANY.has(name.toLowerCase()) && name.length >= 2 && name.length <= 60 && !ROLE_WORDS.test(name) && !(role && role.toLowerCase().includes(name.toLowerCase()))) return name;
      }
    }
    return "";
  }

  function findLocation(text) {
    const m = /\b(?:location|job\s+location|work\s+location|based\s+(?:out\s+)?(?:in|at))\s*[:\-\u2013]?\s*([^\n]{2,60}?)\s*(?:$|[|\n.;])/im.exec(text);
    if (m) return m[1].replace(/^[\s,.\-]+|[\s,.\-]+$/g, "");
    const found = [];
    for (const c of CITIES) if (new RegExp("\\b" + c + "\\b", "i").test(text) && !found.includes(c)) found.push(c);
    return found.slice(0, 2).join(", ");
  }

  function findExperience(text) {
    const m = /\b(\d{1,2})\s*(?:\+|-|\u2013|to)\s*(\d{1,2})?\s*(?:years?|yrs?)\b/i.exec(text);
    return m ? m[0].trim() : "";
  }

  /** Best-effort role / company / location / experience / emails from one post or job text. The backend /ext/extract is preferred. */
  function parseHiringPost(text, hints = {}) {
    const t = capText(text);
    const hinted = titleCandidate(hints.title);
    const role = hinted || findRole(t);
    const company = (hints.company || "").trim() || findCompany(t, role);
    return { role, company, location: findLocation(t), experience: findExperience(t), emails: emailsIn(t).slice(0, 5), is_job: looksLikeHiring(t) || (!!role && t.length > 200) };
  }

  function looksLikeHiring(t) {
    t = String(t || "");
    return t.length > 40 && (HIRING.test(t) || (emailsIn(t).length > 0 && /\b(cv|resume|role|position|experience|years)\b/i.test(t)));
  }

  const isLinkedIn = (host) => /(^|\.)linkedin\.com$/.test(host || "");
  /** LinkedIn pages whose DOM is a stream of unrelated posts: the whole page must never be analysed. */
  function isFeedLike(host, path) {
    return isLinkedIn(host) && !/^\/jobs\/(view|collections|search|search-results|tracker)\b/.test(path || "");
  }
  const isLinkedInJobView = (host, path, search) => isLinkedIn(host) && (/^\/jobs\/view\//.test(path || "") || /[?&]currentJobId=\d+/.test(search || ""));

  /** Which post to use: the one nearest the viewport centre among hiring-looking posts. posts: [{top, bottom, text}] in viewport px. */
  function pickPost(posts, viewportHeight) {
    const mid = viewportHeight / 2;
    let best = -1, bestD = Infinity;
    posts.forEach((p, i) => {
      if (!looksLikeHiring(p.text) || p.bottom < 0 || p.top > viewportHeight) return;
      const d = p.top <= mid && p.bottom >= mid ? 0 : Math.min(Math.abs(p.top - mid), Math.abs(p.bottom - mid));
      if (d < bestD) { best = i; bestD = d; }
    });
    return best;
  }

  /** "...see more" still showing: the visible text is cut off and the user has to expand it on LinkedIn. */
  const isTruncated = (text, hasSeeMore) => !!hasSeeMore || /(?:\u2026|\.\.\.)\s*(?:see\s+)?more\s*$/i.test(String(text || "").trim());

  function capText(t) {
    const s = String(t || "").replace(/\u00a0/g, " ").replace(/\n{3,}/g, "\n\n").trim();
    return s.length > MAX_TEXT ? s.slice(0, MAX_TEXT) : s;
  }

  /** Post text + image alt text + transcribed image text, de-duplicated, capped. */
  function mergePostText({ text = "", alts = [], imageTexts = [] } = {}) {
    const parts = [text];
    for (const x of [...imageTexts, ...alts]) {
      const s = String(x || "").trim();
      if (s && s.length > 3 && !parts.some((p) => p.includes(s)) && !/^(image|photo|picture|no alternative text)/i.test(s)) parts.push(s);
    }
    return capText(parts.join("\n\n"));
  }

  /** schema.org JobPosting object -> {title, company, location, text-html}. */
  function fromJsonLd(node) {
    const list = [];
    const walk = (n) => { if (Array.isArray(n)) n.forEach(walk); else if (n && n["@graph"]) walk(n["@graph"]); else if (n) list.push(n); };
    walk(node);
    const jp = list.find((n) => String(n["@type"]).includes("JobPosting"));
    if (!jp) return null;
    const a = Array.isArray(jp.jobLocation) ? jp.jobLocation[0]?.address : jp.jobLocation?.address;
    const org = jp.hiringOrganization;
    return { title: cleanRole(jp.title || ""), company: (typeof org === "string" ? org : org?.name) || "", html: jp.description || "",
             location: a ? [a.addressLocality, a.addressCountry].filter(Boolean).join(", ") : "" };
  }

  const api = { MAX_TEXT, cleanTitle, cleanRole, roleOk, titleCandidate, emailsIn, parseHiringPost, looksLikeHiring, isFeedLike, isLinkedInJobView, pickPost, isTruncated, capText, mergePostText, fromJsonLd };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  root.SaigeExtract = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

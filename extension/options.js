const DEFAULTS = { api: "https://saige-ai-api.vercel.app", web: "https://saige-ai.vercel.app", token: "" };
const $ = (id) => document.getElementById(id);

chrome.storage.sync.get(["api", "web", "token"]).then((saved) => {
  const cfg = { ...DEFAULTS, ...saved };
  $("api").value = cfg.api;
  $("web").value = cfg.web;
  $("token").value = cfg.token;
});

$("saveBtn").onclick = async () => {
  const cfg = {
    api: ($("api").value.trim() || DEFAULTS.api).replace(/\/+$/, ""),
    web: ($("web").value.trim() || DEFAULTS.web).replace(/\/+$/, ""),
    token: $("token").value.trim(),
  };
  const status = $("status");
  if (!cfg.token.startsWith("saige_pat_")) {
    status.textContent = "That doesn't look like a Saige extension token (it starts with saige_pat_).";
    status.className = "status error";
    return;
  }
  await chrome.storage.sync.set(cfg);
  try {
    const r = await fetch(`${cfg.api}/api/ext/me`, { headers: { Authorization: `Bearer ${cfg.token}` } });
    if (!r.ok) throw new Error(r.status === 401 ? "Token invalid or revoked." : `Server answered ${r.status}.`);
    const me = await r.json();
    status.textContent = `Connected as ${me.name || me.email}. You can close this tab.`;
    status.className = "status ok";
  } catch (e) {
    status.textContent = `Saved, but the test failed: ${e.message}`;
    status.className = "status error";
  }
};

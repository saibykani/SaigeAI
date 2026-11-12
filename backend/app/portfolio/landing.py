# ruff: noqa: E501  (inline CSS strings)
"""Product-launch style portfolio sites: built like a SaaS / sales landing page, not a resume. The candidate is the
"product": sticky glass nav with a CTA, an animated hero (app mock-up, skill orbit, command palette or spotlight),
an employer marquee, skills as feature cards, counters, projects as case studies, a scroll-drawn journey, FAQ from
profile facts and a closing CTA band. Every value comes from `data.build()` (verified profile) and is escaped."""

from html import escape as h

from app.portfolio.templates import _bul, _chips, _contact, page

GLYPHS = ["◆", "✦", "⬢", "◎", "▲", "✺", "◐", "⬡", "✚", "❖"]


def _counters(d: dict) -> list[tuple[str, str, str]]:
    out = [(d["years"], "+", "Years building")] if d["years"] else []
    out += [(str(len(d["projects"])), "", "Projects shipped")] if d["projects"] else []
    out += [(str(len(d["skills"])), "+", "Tools mastered")] if d["skills"] else []
    out += [(str(len(d["experience"])), "", "Teams joined")] if d["experience"] else []
    out += [(str(len(d["certifications"])), "", "Certifications")] if d["certifications"] else []
    return out[:4]


def _metric_html(d: dict) -> str:
    return "".join(f"<div class='met'><b data-count='{h(n)}' data-suffix='{s}'>{h(n)}{s}</b><span>{h(lbl)}</span></div>" for n, s, lbl in _counters(d))


def _headline(d: dict) -> str:
    """Big hero line: the user's own tagline, else their role. Last word gets the accent."""
    text = d["tagline"] or d["role"]
    words = text.split()
    if len(words) > 1:
        return " ".join(f"<span class='w'>{h(w)}</span>" for w in words[:-1]) + f" <span class='w acc'>{h(words[-1])}</span>"
    return f"<span class='w acc'>{h(text)}</span>"


# ---------------------------------------------------------------- hero visuals


def _mock(d: dict) -> str:
    now = d["experience"][0] if d["experience"] else None
    tiles = "".join(f"<div class='mt'><b data-count='{h(n)}' data-suffix='{s}'>{h(n)}{s}</b><i>{h(lbl)}</i></div>" for n, s, lbl in _counters(d)[:3])
    now_card = (f"<div class='mnow'><span class='live'></span><div><small>Now</small><b>{h(now['title'])}</b><i>{h(now['company'])}</i></div></div>" if now else "")
    proj = "".join(f"<div class='mrow'><span class='bar' style='--w:{92 - i * 14}%'></span><em>{h(p['name'][:28])}</em></div>" for i, p in enumerate(d["projects"][:4]))
    chips = "".join(f"<span>{h(s)}</span>" for s in d["skills"][:14])
    return ("<div class='stage'><div class='mock'><div class='mbar'><i></i><i></i><i></i><span>" + h(d["first"].lower()) + ".app</span></div>"
            "<div class='mbody'><aside><b>" + h(d["initials"]) + "</b><span class='on'></span><span></span><span></span><span></span></aside><div class='mmain'>"
            f"{now_card}<div class='mtiles'>{tiles}</div>" + (f"<div class='mproj'><small>Recent work</small>{proj}</div>" if proj else "")
            + f"<div class='mchips'><div class='mci'>{chips}{chips}</div></div></div></div></div>"
            + (f"<div class='float f1'>✓ {h(d['skills'][0])}</div>" if d["skills"] else "")
            + (f"<div class='float f2'>● {h(d['location'])}</div>" if d["location"] else "")
            + "</div>")


def _orbit(d: dict) -> str:
    s = d["skills"][:16]
    inner, outer = s[:6], s[6:16]
    ring = lambda items, cls: "".join(f"<span class='orb {cls}' style='--a:{i * 360 / max(len(items), 1):.0f}deg'><em>{h(x)}</em></span>" for i, x in enumerate(items))  # noqa: E731
    return (f"<div class='stage orbit'><div class='ring r1'>{ring(inner, 'o1')}</div><div class='ring r2'>{ring(outer, 'o2')}</div>"
            f"<div class='core'>{h(d['initials'])}</div></div>")


def _cmdk(d: dict) -> str:
    rows = [("Role", d["role"])] + [("Skill", x) for x in d["skills"][:4]] + [("Project", p["name"]) for p in d["projects"][:2]]
    rows += [("Based in", d["location"])] if d["location"] else []
    items = "".join(f"<div class='ck'><span class='kk'>{h(k)}</span>{h(v)}<kbd>↵</kbd></div>" for k, v in rows if v)
    return (f"<div class='stage'><div class='cmd'><div class='cq'><span>⌘K</span><b id='cq'>Search {h(d['first'])}…</b></div>"
            f"<div class='cl'>{items}</div></div></div>")


def _spot(d: dict) -> str:
    return f"<div class='stage spot'><div class='spotcard'>{_mock(d)}</div></div>"


HEROES = {"mock": _mock, "orbit": _orbit, "cmdk": _cmdk, "spot": _spot}


# ---------------------------------------------------------------- sections


def _logos(d: dict) -> str:
    names = list(dict.fromkeys(e["company"] for e in d["experience"] if e["company"]))
    names += [e["school"] for e in d["education"] if e["school"]][:2]
    if not names:
        return ""
    row = "".join(f"<span>{h(n)}</span>" for n in names)
    rep = row * max(2, 8 // len(names) + 1)
    return f"<div class='logos'><p>Experience at</p><div class='lgm'><div class='lgi'>{rep}{rep}</div></div></div>"


def _features(d: dict) -> str:
    groups = d["skill_groups"] or ([("Skills", d["skills"])] if d["skills"] else [])
    if not groups:
        return ""
    cards = "".join(f"<article class='feat'><div class='gl'>{GLYPHS[i % len(GLYPHS)]}</div><h3>{h(g)}</h3><p>{h(', '.join(items[:6]))}</p>"
                    f"<div class='tags'>{_chips(items[:8], 'tag')}</div></article>" for i, (g, items) in enumerate(groups[:6]))
    return f"<section id='skills' class='sec'><div class='eyebrow'>What I bring</div><h2>Everything your team needs, <span class='acc'>in one hire.</span></h2><div class='feats'>{cards}</div></section>"


def _cases(d: dict) -> str:
    if not d["projects"]:
        return ""
    out = []
    for i, p in enumerate(d["projects"][:6]):
        link = f"<a class='btn ghost' href='{h(p['url'])}' target='_blank' rel='noopener'>See it live ↗</a>" if p["url"] else ""
        stack = "".join(f"<span style='--d:{k * 0.12:.2f}s'>{h(t)}</span>" for k, t in enumerate(p["tech"][:6]))
        hl = "".join(f"<li>{h(x)}</li>" for x in p["highlights"][:3])
        screen = (f"<div class='screen'><div class='mbar'><i></i><i></i><i></i><span>{h(p['name'][:30])}</span></div><div class='scr'>"
                  f"<div class='big'>{i + 1:02d}</div><div class='stk'>{stack}</div></div></div>")
        out.append(f"<article class='case{' rev' if i % 2 else ''}'><div class='ctext'><div class='eyebrow'>Case study {i + 1:02d}</div><h3>{h(p['name'])}</h3>"
                   f"<p>{h(p['description'])}</p>" + (f"<ul class='ticks'>{hl}</ul>" if hl else "") + f"{link}</div>{screen}</article>")
    return f"<section id='work' class='sec'><div class='eyebrow'>Selected work</div><h2>Shipped, <span class='acc'>not just planned.</span></h2>{''.join(out)}</section>"


def _journey(d: dict) -> str:
    if not d["experience"]:
        return ""
    steps = "".join(f"<div class='step'><span class='node'></span><div class='when'>{h(e['dates'])}</div><h3>{h(e['title'])}</h3><div class='at'>{h(e['company'])}"
                    f"{' · ' + h(e['location']) if e['location'] else ''}</div>{_bul(e['bullets'][:3])}<div class='tags'>{_chips(e['tech'][:6], 'tag')}</div></div>"
                    for e in d["experience"])
    return f"<section id='journey' class='sec'><div class='eyebrow'>The journey</div><h2>How I got <span class='acc'>here.</span></h2><div class='jr'><span class='jline'></span>{steps}</div></section>"


def _creds(d: dict) -> str:
    items = [(e["degree"] or "Education", " · ".join(x for x in (e["school"], e["years"]) if x)) for e in d["education"]]
    items += [(c["name"], c["issuer"]) for c in d["certifications"]]
    if not items:
        return ""
    cards = "".join(f"<div class='cred'><span>🎓</span><b>{h(a)}</b><i>{h(b)}</i></div>" for a, b in items[:8])
    return f"<section id='creds' class='sec'><div class='eyebrow'>Credentials</div><div class='creds'>{cards}</div></section>"


def _faq(d: dict) -> str:
    qa = []
    if d["summary"]:
        qa.append((f"Who is {d['first']}?", d["summary"]))
    if d["experience_text"]:
        qa.append(("How much experience?", d["experience_text"]))
    if d["location"]:
        qa.append(("Where are you based?", d["location"]))
    if d["skills"]:
        qa.append(("What's in the toolbox?", ", ".join(d["skills"][:12])))
    if d["domains"]:
        qa.append(("Which domains?", ", ".join(d["domains"])))
    if d["open_to_work"]:
        qa.append(("Are you available?", "Yes, open to new opportunities. Reach out below."))
    if not qa:
        return ""
    items = "".join(f"<details{' open' if i == 0 else ''}><summary>{h(q)}<span>+</span></summary><p>{h(a)}</p></details>" for i, (q, a) in enumerate(qa))
    return f"<section id='faq' class='sec narrow'><div class='eyebrow'>FAQ</div><h2>Questions recruiters ask.</h2><div class='faq'>{items}</div></section>"


def _cta(d: dict) -> str:
    mail = f"<a class='btn primary mag' href='mailto:{h(d['email'])}'>Start a conversation →</a>" if d["email"] else ""
    return (f"<section id='contact' class='ctaband'><div class='glowbg'></div><h2>Let's build what's next, <span class='acc'>together.</span></h2>"
            f"<p>{_contact(d, ' · ')}</p>{mail}</section>")


# ---------------------------------------------------------------- theme + assembly

BASE_CSS = """
body{font-family:var(--font),system-ui,sans-serif;background:var(--bg);color:var(--fg);overflow-x:hidden;-webkit-font-smoothing:antialiased}
.acc{color:var(--acc)}a{text-decoration:none}
.bgfx{position:fixed;inset:0;z-index:-2;background:var(--bgfx);pointer-events:none}
.grid-bg{position:fixed;inset:0;z-index:-1;pointer-events:none;background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:64px 64px;mask:radial-gradient(70% 60% at 50% 20%,#000,transparent)}
nav.top{position:sticky;top:14px;z-index:30;max-width:1120px;margin:14px auto 0;display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px 10px 20px;border-radius:999px;background:var(--glass);border:1px solid var(--line);backdrop-filter:blur(18px) saturate(1.4)}
nav.top .logo{font-weight:800;letter-spacing:-.02em;display:flex;align-items:center;gap:8px}nav.top .logo i{width:26px;height:26px;border-radius:8px;background:var(--acc);display:grid;place-items:center;color:var(--on);font-style:normal;font-size:12px}
nav.top .ln a{color:var(--muted);margin:0 12px;font-size:14px;transition:color .2s}nav.top .ln a:hover{color:var(--fg)}
.btn{display:inline-flex;align-items:center;gap:8px;padding:13px 22px;border-radius:14px;font-weight:700;font-size:15px;transition:transform .2s,box-shadow .2s,background .2s}
.btn.primary{background:var(--acc);color:var(--on);box-shadow:0 12px 40px -10px var(--acc)}.btn.primary:hover{box-shadow:0 18px 50px -8px var(--acc)}
.btn.ghost{border:1px solid var(--line2);color:var(--fg)}.btn.ghost:hover{background:var(--card)}.btn.sm{padding:9px 16px;font-size:14px;border-radius:999px}
.hero{min-height:92vh;max-width:1160px;margin:0 auto;padding:90px 24px 40px;display:grid;grid-template-columns:1.05fr 1fr;gap:40px;align-items:center}
.hero.center{grid-template-columns:1fr;text-align:center;justify-items:center}
.pill{display:inline-flex;align-items:center;gap:8px;padding:6px 14px 6px 8px;border-radius:999px;border:1px solid var(--line2);background:var(--card);font-size:13px;color:var(--muted)}
.pill b{background:var(--acc);color:var(--on);border-radius:999px;padding:2px 9px;font-size:11px;letter-spacing:.04em}
.pill .dotp{width:8px;height:8px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 0 #22c55e88;animation:ping 1.8s infinite}@keyframes ping{70%{box-shadow:0 0 0 10px #22c55e00}}
.hero h1{font-family:var(--hfont),var(--font),sans-serif;font-size:clamp(44px,6.6vw,88px);line-height:.98;letter-spacing:-.045em;margin:20px 0 6px;font-weight:800}
.hero h1 .w{display:inline-block;opacity:0;translate:0 .5em;filter:blur(8px);animation:wup .9s cubic-bezier(.2,.8,.2,1) forwards}
@keyframes wup{to{opacity:1;translate:0 0;filter:blur(0)}}
.hero .who{font-size:18px;color:var(--muted);margin-top:4px}.hero .who b{color:var(--fg)}
.hero .lede{font-size:18px;line-height:1.65;color:var(--muted);max-width:560px;margin:18px 0 0}.hero.center .lede{margin-inline:auto}
.sg-typer{color:var(--acc);font-weight:600}
.ctas{display:flex;gap:12px;flex-wrap:wrap;margin-top:28px}.hero.center .ctas{justify-content:center}
.proof{display:flex;gap:26px;margin-top:34px;flex-wrap:wrap}.proof div b{display:block;font-size:26px;font-weight:800}.proof div span{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.stage{position:relative;perspective:1400px}
.mock{border-radius:22px;background:var(--panel);border:1px solid var(--line2);box-shadow:0 40px 120px -30px var(--shadow),0 0 0 1px var(--line) inset;overflow:hidden;transform:rotateY(-14deg) rotateX(8deg);transform-style:preserve-3d;animation:hov 7s ease-in-out infinite;transition:transform .6s}
.stage:hover .mock{transform:rotateY(-4deg) rotateX(2deg)}@keyframes hov{50%{translate:0 -14px}}
.mbar{display:flex;align-items:center;gap:6px;padding:12px 14px;border-bottom:1px solid var(--line)}.mbar i{width:10px;height:10px;border-radius:50%;background:var(--line2)}.mbar i:first-child{background:#ff5f57}.mbar i:nth-child(2){background:#febc2e}.mbar i:nth-child(3){background:#28c840}
.mbar span{margin-left:10px;font-size:12px;color:var(--muted);font-family:ui-monospace,monospace}
.mbody{display:grid;grid-template-columns:54px 1fr;min-height:330px}.mbody aside{border-right:1px solid var(--line);display:flex;flex-direction:column;align-items:center;gap:14px;padding:14px 0}
.mbody aside b{width:32px;height:32px;border-radius:10px;background:var(--acc);color:var(--on);display:grid;place-items:center;font-size:12px}.mbody aside span{width:22px;height:6px;border-radius:9px;background:var(--line2)}.mbody aside .on{background:var(--acc)}
.mmain{padding:16px;display:flex;flex-direction:column;gap:12px;min-width:0}
.mnow{display:flex;gap:12px;align-items:center;padding:12px;border-radius:14px;background:var(--card);border:1px solid var(--line)}.mnow small{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}.mnow b{display:block;font-size:14px}.mnow i{font-size:12px;color:var(--muted);font-style:normal}
.live{width:10px;height:10px;border-radius:50%;background:#22c55e;flex:none;animation:ping 1.8s infinite}
.mtiles{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.mt{padding:10px;border-radius:12px;background:var(--card);border:1px solid var(--line)}.mt b{display:block;font-size:22px;color:var(--acc)}.mt i{font-size:10px;color:var(--muted);font-style:normal}
.mproj small{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}.mrow{display:flex;align-items:center;gap:10px;margin-top:7px}.mrow em{font-size:11px;font-style:normal;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bar{flex:none;width:44%;height:8px;border-radius:9px;background:var(--line);position:relative;overflow:hidden}.bar:after{content:'';position:absolute;inset:0;width:var(--w);border-radius:9px;background:var(--acc);transform-origin:left;animation:grow 2.2s cubic-bezier(.2,.8,.2,1) both}@keyframes grow{from{transform:scaleX(0)}}
.mchips{overflow:hidden;mask:linear-gradient(90deg,transparent,#000 12%,#000 88%,transparent)}.mci{display:inline-flex;gap:6px;white-space:nowrap;animation:mq 22s linear infinite}.mci span{font-size:11px;padding:4px 9px;border-radius:99px;border:1px solid var(--line2)}
@keyframes mq{to{transform:translateX(-50%)}}
.float{position:absolute;padding:9px 14px;border-radius:14px;background:var(--glass);border:1px solid var(--line2);backdrop-filter:blur(14px);font-size:13px;font-weight:600;box-shadow:0 20px 50px -20px var(--shadow);animation:hov 5s ease-in-out infinite}
.f1{top:-18px;right:6%;color:var(--acc)}.f2{bottom:-14px;left:-4%;animation-delay:-2.5s}
.orbit{height:480px;display:grid;place-items:center}.ring{position:absolute;border-radius:50%;border:1px dashed var(--line2);animation:spin 40s linear infinite}.r1{width:250px;height:250px}.r2{width:440px;height:440px;animation-duration:70s;animation-direction:reverse}
@keyframes spin{to{rotate:360deg}}.orb{position:absolute;left:50%;top:50%;transform:rotate(var(--a)) translateY(calc(var(--r) * -1)) rotate(calc(var(--a) * -1))}.o1{--r:125px}.o2{--r:220px}
.orb em{display:block;translate:-50% -50%;font-style:normal;font-size:13px;font-weight:600;padding:7px 12px;border-radius:99px;background:var(--panel);border:1px solid var(--line2);white-space:nowrap;animation:spin 40s linear infinite reverse}.r2 .orb em{animation:spin 70s linear infinite}
.core{width:120px;height:120px;border-radius:34px;background:var(--acc);color:var(--on);display:grid;place-items:center;font-size:40px;font-weight:800;box-shadow:0 0 80px -10px var(--acc);animation:pulse 3.5s ease-in-out infinite}@keyframes pulse{50%{scale:1.06}}
.cmd{border-radius:20px;background:var(--panel);border:1px solid var(--line2);box-shadow:0 40px 120px -30px var(--shadow);overflow:hidden;animation:hov 7s ease-in-out infinite}
.cq{display:flex;gap:12px;align-items:center;padding:18px;border-bottom:1px solid var(--line);font-size:17px}.cq span{font-size:12px;padding:3px 7px;border-radius:7px;border:1px solid var(--line2);color:var(--muted)}.cq b{font-weight:500}.cq b:after{content:'';display:inline-block;width:2px;height:1em;background:var(--acc);margin-left:3px;vertical-align:-.15em;animation:sgb 1s steps(2) infinite}
.cl{padding:8px}.ck{display:flex;align-items:center;gap:12px;padding:11px 12px;border-radius:12px;font-size:14px;transition:background .2s}.ck .kk{font-size:11px;min-width:64px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.ck kbd{margin-left:auto;font-size:11px;color:var(--muted);opacity:0}
.ck.hot{background:var(--card)}.ck.hot kbd{opacity:1}.ck.hot .kk{color:var(--acc)}
.spot{width:100%;max-width:900px;margin-top:50px}.spot .mock{transform:rotateX(18deg) scale(.94);animation:none}.spot .stage{perspective:1600px}
.logos{max-width:1120px;margin:30px auto 0;padding:0 24px;text-align:center}.logos p{font-size:12px;letter-spacing:.2em;text-transform:uppercase;color:var(--muted)}
.lgm{overflow:hidden;mask:linear-gradient(90deg,transparent,#000 15%,#000 85%,transparent)}.lgi{display:inline-flex;gap:56px;white-space:nowrap;animation:mq 34s linear infinite;padding:14px 0}.lgi span{font-size:24px;font-weight:800;letter-spacing:-.02em;opacity:.55;transition:opacity .3s}.lgi span:hover{opacity:1}
.metrics{max-width:1120px;margin:70px auto 0;padding:0 24px;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1px;background:var(--line);border-radius:26px;overflow:hidden;border:1px solid var(--line)}
.met{background:var(--bg);padding:30px;text-align:center}.met b{display:block;font-size:clamp(40px,5vw,58px);font-weight:800;letter-spacing:-.04em;color:var(--acc)}.met span{color:var(--muted);font-size:14px}
.sec{max-width:1120px;margin:0 auto;padding:110px 24px 0}.sec.narrow{max-width:820px}
.eyebrow{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.2em;text-transform:uppercase;color:var(--acc);margin-bottom:12px}
.sec h2,.ctaband h2{font-family:var(--hfont),var(--font),sans-serif;font-size:clamp(32px,4.6vw,58px);line-height:1.04;letter-spacing:-.035em;margin:0 0 40px;max-width:820px}
.feats{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}
.feat{position:relative;padding:28px;border-radius:24px;background:var(--card);border:1px solid var(--line);overflow:hidden;--mx:50%;--my:50%}
.feat:before{content:'';position:absolute;inset:0;background:radial-gradient(360px circle at var(--mx) var(--my),var(--accsoft),transparent 45%);opacity:0;transition:opacity .3s}.feat:hover:before{opacity:1}
.feat>*{position:relative}.gl{width:46px;height:46px;border-radius:14px;display:grid;place-items:center;background:var(--accsoft);color:var(--acc);font-size:20px;margin-bottom:18px}
.feat h3{margin:0 0 8px;font-size:21px}.feat p{color:var(--muted);line-height:1.6;margin:0}
.tag,.chip{display:inline-block;font-size:12px;padding:5px 10px;border-radius:99px;border:1px solid var(--line2);color:var(--muted)}
.case{display:grid;grid-template-columns:1fr 1.1fr;gap:50px;align-items:center;margin-bottom:90px}.case.rev .ctext{order:2}
.case h3{font-size:clamp(26px,3vw,38px);letter-spacing:-.03em;margin:0 0 12px}.case p{color:var(--muted);line-height:1.7;font-size:17px}
.ticks{list-style:none;padding:0;margin:18px 0 24px}.ticks li{padding:7px 0 7px 30px;position:relative;line-height:1.5}.ticks li:before{content:'✓';position:absolute;left:0;top:6px;width:20px;height:20px;border-radius:50%;background:var(--accsoft);color:var(--acc);font-size:11px;display:grid;place-items:center;font-weight:800}
.screen{border-radius:22px;background:var(--panel);border:1px solid var(--line2);overflow:hidden;box-shadow:0 30px 90px -30px var(--shadow);transition:transform .5s}.case:hover .screen{transform:translateY(-8px) rotate(-.6deg)}
.scr{position:relative;min-height:270px;padding:26px;background:radial-gradient(120% 90% at 100% 0%,var(--accsoft),transparent 60%)}
.big{font-size:150px;font-weight:800;line-height:.8;letter-spacing:-.06em;color:transparent;-webkit-text-stroke:1.5px var(--line2)}
.stk{position:absolute;left:26px;right:26px;bottom:24px;display:flex;flex-wrap:wrap;gap:8px}.stk span{padding:8px 13px;border-radius:12px;background:var(--glass);border:1px solid var(--line2);backdrop-filter:blur(10px);font-size:13px;font-weight:600;opacity:0;translate:0 14px;transition:.6s cubic-bezier(.2,.8,.2,1);transition-delay:var(--d)}
.case.in .stk span,.rv.in .stk span{opacity:1;translate:0 0}
.jr{position:relative;padding-left:40px}.jline{position:absolute;left:11px;top:6px;bottom:0;width:2px;background:var(--line)}.jline:after{content:'';position:absolute;inset:0;background:var(--acc);transform-origin:top;transform:scaleY(var(--jp,0));box-shadow:0 0 18px var(--acc)}
.step{position:relative;padding:0 0 46px}.node{position:absolute;left:-36px;top:6px;width:16px;height:16px;border-radius:50%;background:var(--bg);border:3px solid var(--acc);box-shadow:0 0 0 6px var(--accsoft)}
.step h3{margin:4px 0;font-size:24px;letter-spacing:-.02em}.when{font-size:13px;font-weight:700;color:var(--acc)}.at{color:var(--muted)}.step ul{color:var(--muted);line-height:1.65}
.creds{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}.cred{padding:22px;border-radius:20px;border:1px solid var(--line);background:var(--card)}.cred span{font-size:22px}.cred b{display:block;margin:10px 0 4px}.cred i{font-style:normal;color:var(--muted);font-size:14px}
.faq details{border-bottom:1px solid var(--line);padding:6px 0}.faq summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;padding:16px 0;font-size:19px;font-weight:600}
.faq summary::-webkit-details-marker{display:none}.faq summary span{width:30px;height:30px;border-radius:50%;border:1px solid var(--line2);display:grid;place-items:center;transition:rotate .3s}.faq details[open] summary span{rotate:45deg;background:var(--acc);color:var(--on);border-color:var(--acc)}
.faq p{color:var(--muted);line-height:1.7;margin:0 0 16px}
.ctaband{position:relative;overflow:hidden;max-width:1120px;margin:120px auto 0;padding:100px 24px;border-radius:36px;text-align:center;background:var(--panel);border:1px solid var(--line2)}
.ctaband h2{margin:0 auto 14px}.ctaband p{color:var(--muted)}.ctaband a{color:inherit}.ctaband .btn{margin-top:22px}
.glowbg{position:absolute;inset:-40%;background:conic-gradient(from 0deg,transparent,var(--accsoft),transparent 30%);animation:spin 12s linear infinite;z-index:-0;pointer-events:none}.ctaband>*{position:relative}
.dock{position:fixed;left:50%;bottom:18px;translate:-50% 120px;z-index:40;display:flex;align-items:center;gap:12px;padding:8px 8px 8px 18px;border-radius:999px;background:var(--glass);border:1px solid var(--line2);backdrop-filter:blur(18px);box-shadow:0 20px 60px -20px var(--shadow);transition:translate .5s cubic-bezier(.2,.8,.2,1);font-size:14px}
.dock.show{translate:-50% 0}.dock .dotp{width:8px;height:8px;border-radius:50%;background:#22c55e}
.made{text-align:center;color:var(--muted);font-size:12px;padding:60px 20px 90px;opacity:.7}
@media(max-width:900px){.hero{grid-template-columns:1fr;padding-top:60px}.case,.case.rev{grid-template-columns:1fr;gap:24px}.case.rev .ctext{order:0}nav.top .ln{display:none}.orbit{height:380px;scale:.8}.f2{left:2%}}
"""

LANDING_JS = """(()=>{const R=matchMedia('(prefers-reduced-motion: reduce)').matches;
document.querySelectorAll('.hero h1 .w').forEach((w,i)=>w.style.animationDelay=(0.12+i*0.09)+'s');
document.querySelectorAll('.feat').forEach(c=>c.addEventListener('pointermove',e=>{const r=c.getBoundingClientRect();c.style.setProperty('--mx',e.clientX-r.left+'px');c.style.setProperty('--my',e.clientY-r.top+'px')}));
if(!R)document.querySelectorAll('.mag').forEach(b=>{b.addEventListener('pointermove',e=>{const r=b.getBoundingClientRect();b.style.transform=`translate(${(e.clientX-r.left-r.width/2)*.25}px,${(e.clientY-r.top-r.height/2)*.35}px)`});b.addEventListener('pointerleave',()=>b.style.transform='')});
const io=new IntersectionObserver(es=>es.forEach(x=>{if(x.isIntersecting){x.target.classList.add('in');io.unobserve(x.target)}}),{threshold:.2});document.querySelectorAll('.case').forEach(c=>io.observe(c));
const jr=document.querySelector('.jr'),dock=document.querySelector('.dock'),sm=document.querySelector('.spot .mock');
const onS=()=>{const vh=innerHeight;if(jr){const r=jr.getBoundingClientRect();const p=Math.max(0,Math.min(1,(vh*.7-r.top)/r.height));jr.style.setProperty('--jp',p)}
 if(dock)dock.classList.toggle('show',scrollY>vh*.8&&(innerHeight+scrollY)<document.documentElement.scrollHeight-200);
 if(sm){const r=sm.getBoundingClientRect();const p=Math.max(0,Math.min(1,1-(r.top-vh*.15)/(vh*.7)));sm.style.transform=`rotateX(${18*(1-p)}deg) scale(${.94+.06*p})`}};
addEventListener('scroll',onS,{passive:true});onS();
const ck=[...document.querySelectorAll('.ck')],cq=document.getElementById('cq');if(ck.length&&!R){let i=0;setInterval(()=>{ck.forEach(x=>x.classList.remove('hot'));const c=ck[i%ck.length];c.classList.add('hot');
 if(cq){const t=c.textContent.replace('↵','').replace(c.querySelector('.kk').textContent,'').trim();let j=0;const ty=()=>{cq.textContent=t.slice(0,j++);if(j<=t.length)setTimeout(ty,38)};ty()}i++},2200)}
})();"""


def _theme_css(t: dict) -> str:
    return (":root{" + ";".join(f"--{k}:{v}" for k, v in t.items()) + "}")


def build_landing(d: dict, theme: dict, hero: str, fonts: str, center: bool = False) -> str:
    links = [("skills", "Skills", d["skills"]), ("work", "Work", d["projects"]), ("journey", "Journey", d["experience"]),
             ("faq", "FAQ", True), ("contact", "Contact", True)]
    nav = "".join(f"<a href='#{i}'>{n}</a>" for i, n, ok in links if ok)
    hire = f"<a class='btn primary sm' href='mailto:{h(d['email'])}'>Hire {h(d['first'])}</a>" if d["email"] else "<a class='btn primary sm' href='#contact'>Contact</a>"
    pill = (f"<span class='pill'><b>OPEN</b><span class='dotp'></span>Available for new roles{' · ' + h(d['location']) if d['location'] else ''}</span>"
            if d["open_to_work"] else f"<span class='pill'><b>{h(d['initials'])}</b>{h(d['role'])}</span>")
    proof = "".join(f"<div><b data-count='{h(n)}' data-suffix='{s}'>{h(n)}{s}</b><span>{h(lbl)}</span></div>" for n, s, lbl in _counters(d)[:3])
    lede = d["summary"][:260] + ("…" if len(d["summary"]) > 260 else "") if d["summary"] else ""
    left = (f"<div>{pill}<h1>{_headline(d)}</h1><div class='who'>I'm <b>{h(d['name'])}</b>{' · ' + h(d['experience_text']) if d['experience_text'] else ''}</div>"
            + (f"<p class='lede'>{h(lede)}</p>" if lede else "")
            + "<div class='ctas'>" + (f"<a class='btn primary mag' href='mailto:{h(d['email'])}'>Get in touch →</a>" if d["email"] else "<a class='btn primary mag' href='#contact'>Get in touch →</a>")
            + ("<a class='btn ghost' href='#work'>See my work</a>" if d["projects"] else "") + f"</div><div class='proof'>{proof}</div></div>")
    visual = HEROES[hero](d)
    hero_html = f"<header class='hero{' center' if center else ''}'>{left}{visual}</header>"
    dock = (f"<div class='dock'><span class='dotp'></span><b>{h(d['name'])}</b><span style='opacity:.6'>{h(d['role'])}</span>{hire}</div>")
    body = (f"<div class='bgfx'></div><div class='grid-bg'></div><nav class='top'><a class='logo' href='#'><i>{h(d['initials'])}</i>{h(d['name'])}</a>"
            f"<span class='ln'>{nav}</span>{hire}</nav>{hero_html}{_logos(d)}"
            + (f"<div class='metrics'>{_metric_html(d)}</div>" if _counters(d) else "")
            + f"{_features(d)}{_cases(d)}{_journey(d)}{_creds(d)}{_faq(d)}{_cta(d)}{dock}")
    return page(d, _theme_css(theme) + BASE_CSS, body, fonts, LANDING_JS)


def _dark(acc: str, accsoft: str, bg: str = "#06060a", on: str = "#0a0a0a", bgfx: str = "", panel: str = "#0e0e14") -> dict:
    return {"bg": bg, "fg": "#f4f4f6", "muted": "#9a9aa8", "card": "#ffffff08", "panel": panel, "glass": "#14141c99", "line": "#ffffff12",
            "line2": "#ffffff22", "acc": acc, "accsoft": accsoft, "on": on, "shadow": "#000000cc",
            "bgfx": bgfx or f"radial-gradient(60% 50% at 70% 0%,{accsoft},transparent 70%)", "font": "'Inter'", "hfont": "'Inter'"}


def _light(acc: str, accsoft: str, bg: str = "#ffffff", fg: str = "#0b0b0f", panel: str = "#ffffff") -> dict:
    return {"bg": bg, "fg": fg, "muted": "#5f6070", "card": "#0000000a", "panel": panel, "glass": "#ffffffb3", "line": "#0000000f",
            "line2": "#0000001f", "acc": acc, "accsoft": accsoft, "on": "#ffffff", "shadow": "#1a1a2a55",
            "bgfx": f"radial-gradient(55% 45% at 80% 0%,{accsoft},transparent 70%)", "font": "'Inter'", "hfont": "'Inter'"}


def launch(d):
    return build_landing(d, _dark("#a78bfa", "#7c3aed33"), "mock", "Inter:wght@400;500;600;700;800")


def saas_light(d):
    return build_landing(d, {**_light("#ff5a1f", "#ff5a1f1f"), "hfont": "'Bricolage Grotesque'"}, "mock",
                         "Inter:wght@400;500;600;700;800&family=Bricolage+Grotesque:wght@600;800")


def orbit(d):
    return build_landing(d, {**_dark("#34d399", "#10b98126", bg="#04080a"), "hfont": "'Space Grotesk'"}, "orbit",
                         "Inter:wght@400;600;800&family=Space+Grotesk:wght@500;700")


def command(d):
    return build_landing(d, {**_dark("#fbbf24", "#f59e0b22", bg="#0a0a0a", panel="#111111"), "font": "'Geist'", "hfont": "'Geist'"}, "cmdk",
                         "Geist:wght@400;500;600;800")


def keynote(d):
    return build_landing(d, {**_dark("#ffffff", "#ffffff14", bg="#000000", on="#000000", panel="#0b0b0b",
                                     bgfx="radial-gradient(50% 40% at 50% 0%,#ffffff1c,transparent 70%)"), "hfont": "'Inter Tight'"},
                         "spot", "Inter:wght@400;600;800&family=Inter+Tight:wght@700;800", center=True)


def startup(d):
    return build_landing(d, {**_light("#111111", "#c6f43255", bg="#f4f1ea", panel="#fffdf8"), "acc": "#4d7c0f", "hfont": "'Instrument Serif'"},
                         "spot", "Inter:wght@400;600;800&family=Instrument+Serif", center=True)


def fintech(d):
    return build_landing(d, {**_dark("#22c55e", "#16a34a26", bg="#030b07", panel="#07130d"), "hfont": "'Manrope'", "font": "'Manrope'"}, "mock",
                         "Manrope:wght@400;600;800")


def studio(d):
    return build_landing(d, {**_light("#7c3aed", "#7c3aed1a", bg="#fafaf9"), "hfont": "'Space Grotesk'"}, "orbit",
                         "Inter:wght@400;600;800&family=Space+Grotesk:wght@500;700")


def ember(d):
    return build_landing(d, {**_dark("#fb923c", "#ea580c26", bg="#0c0806", panel="#140d09"), "hfont": "'Sora'", "font": "'Sora'"}, "cmdk",
                         "Sora:wght@400;600;800")


def mono_light(d):
    return build_landing(d, {**_light("#e11d48", "#e11d4814"), "font": "'Geist'", "hfont": "'Geist'"}, "cmdk", "Geist:wght@400;500;600;800")


LANDINGS = {
    "launch": ("Product Launch ★", "Your career pitched like a SaaS launch: 3D app mock-up of your stats, employer marquee, case studies, FAQ, sticky Hire CTA", launch,
               ["#06060a", "#a78bfa", "#ffffff"]),
    "saas_light": ("SaaS Landing ★", "Bright startup sales page: floating dashboard, feature cards with spotlight hover, magnetic buttons", saas_light,
                   ["#ffffff", "#ff5a1f", "#0b0b0f"]),
    "keynote": ("Keynote Reveal ★", "Apple-style: word-by-word headline, the app mock-up flattens as you scroll", keynote, ["#000000", "#ffffff", "#3a3a3a"]),
    "orbit": ("Skill Orbit ★", "Your skills orbit your initials in two rotating rings", orbit, ["#04080a", "#34d399", "#ffffff"]),
    "command": ("Command Palette ★", "A ⌘K search that types through your role, skills and projects", command, ["#0a0a0a", "#fbbf24", "#ffffff"]),
    "fintech": ("Fintech Dashboard ★", "Emerald dashboard mock-up with live counters and growing bars", fintech, ["#030b07", "#22c55e", "#ffffff"]),
    "startup": ("Startup Pitch ★", "Cream & serif pitch-deck landing with a scroll-tilting product shot", startup, ["#f4f1ea", "#4d7c0f", "#111111"]),
    "studio": ("Creative Studio ★", "Clean studio site with a violet skill orbit", studio, ["#fafaf9", "#7c3aed", "#0b0b0f"]),
    "ember": ("Ember ★", "Warm dark landing with the ⌘K palette and glowing CTA", ember, ["#0c0806", "#fb923c", "#ffffff"]),
    "mono_light": ("Mono Crimson ★", "Minimal white product page with one crimson accent and a ⌘K hero", mono_light, ["#ffffff", "#e11d48", "#0b0b0f"]),
}

# ruff: noqa: E501  (inline CSS strings)
"""25 portfolio website templates. Each returns a complete, standalone, responsive HTML page (inline CSS, no JS
required, Google Fonts only) built from `data.build()`. Every value is HTML-escaped."""

from html import escape as h

FONTS = "https://fonts.googleapis.com/css2?family={}&display=swap"


# ------------------------------------------------------------------ shared pieces


def _contact(d: dict, sep: str = " · ") -> str:
    bits = [f"<a href='mailto:{h(d['email'])}'>{h(d['email'])}</a>"] if d["email"] else []
    bits += [h(d["phone"])] if d["phone"] else []
    bits += [f"<a href='{h(u)}' target='_blank' rel='noopener'>{h(lbl)}</a>" for lbl, u in d["links"]]
    return sep.join(bits)


def _chips(items: list[str], cls: str = "chip") -> str:
    return "".join(f"<span class='{cls}'>{h(s)}</span>" for s in items)


def _bul(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{h(b)}</li>" for b in items) + "</ul>" if items else ""


def _exp(d: dict, wrap: str = "job") -> str:
    return "".join(
        f"<article class='{wrap}'><div class='when'>{h(e['dates'])}</div><h3>{h(e['title'])} <span class='at'>@ {h(e['company'])}</span></h3>"
        f"{_bul(e['bullets'])}<div class='tags'>{_chips(e['tech'], 'tag')}</div></article>" for e in d["experience"])


def _proj(d: dict, wrap: str = "proj") -> str:
    out = []
    for p in d["projects"]:
        title = f"<a href='{h(p['url'])}' target='_blank' rel='noopener'>{h(p['name'])} ↗</a>" if p["url"] else h(p["name"])
        out.append(f"<article class='{wrap}'><h3>{title}</h3><p>{h(p['description'])}</p>{_bul(p['highlights'])}"
                   f"<div class='tags'>{_chips(p['tech'], 'tag')}</div></article>")
    return "".join(out)


def _edu(d: dict) -> str:
    rows = [f"<li><b>{h(e['degree'])}</b>{' · ' + h(e['school']) if e['school'] else ''}{' · ' + h(e['years']) if e['years'] else ''}</li>"
            for e in d["education"]]
    rows += [f"<li><b>{h(c['name'])}</b>{' · ' + h(c['issuer']) if c['issuer'] else ''}</li>" for c in d["certifications"]]
    return "<ul class='edu'>" + "".join(rows) + "</ul>" if rows else ""


def _sections(d: dict, h2: str = "h2") -> str:
    parts = []
    if d["summary"]:
        parts.append(f"<section id='about'><{h2}>About</{h2}><p class='lead'>{h(d['summary'])}</p></section>")
    if d["skills"]:
        parts.append(f"<section id='skills'><{h2}>Skills</{h2}><div class='chips'>{_chips(d['skills'])}</div></section>")
    if d["experience"]:
        parts.append(f"<section id='work'><{h2}>Experience</{h2}>{_exp(d)}</section>")
    if d["projects"]:
        parts.append(f"<section id='projects'><{h2}>Projects</{h2}><div class='grid'>{_proj(d)}</div></section>")
    if d["education"] or d["certifications"]:
        parts.append(f"<section id='edu'><{h2}>Education & certifications</{h2}>{_edu(d)}</section>")
    return "".join(parts)


def _badge(d: dict) -> str:
    return "<span class='otw'>● Open to opportunities</span>" if d["open_to_work"] else ""


def _sub(d: dict) -> str:
    return h(d["tagline"] or " · ".join(x for x in (d["role"], d["experience_text"], d["location"]) if x))


def page(d: dict, css: str, body: str, fonts: str = "Inter:wght@300;400;600;800") -> str:
    desc = h((d["summary"] or d["role"])[:160])
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{h(d['name'])} · {h(d['role'])}</title><meta name='description' content='{desc}'>"
            f"<meta property='og:title' content='{h(d['name'])} · {h(d['role'])}'><meta property='og:description' content='{desc}'>"
            f"<link rel='preconnect' href='https://fonts.gstatic.com' crossorigin><link rel='stylesheet' href='{FONTS.format(fonts)}'>"
            "<style>*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0}img{max-width:100%}a{color:inherit}"
            ".tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}ul{padding-left:1.1em}"
            "@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}" + css + "</style></head>"
            f"<body>{body}<footer class='made'>Built with Saige AI · facts from a verified profile</footer></body></html>")


# ------------------------------------------------------------------ the 25 templates


def aurora_glass(d):
    css = ("body{font-family:Inter;color:#f4f4f5;background:#05050a;min-height:100vh;overflow-x:hidden}"
           "body:before{content:'';position:fixed;inset:-20%;background:radial-gradient(40% 40% at 20% 20%,#7c3aed55,transparent),"
           "radial-gradient(35% 35% at 80% 30%,#06b6d455,transparent),radial-gradient(40% 40% at 50% 90%,#f59e0b33,transparent);"
           "filter:blur(40px);animation:drift 18s ease-in-out infinite alternate;z-index:-1}@keyframes drift{to{transform:rotate(12deg) scale(1.1)}}"
           ".wrap{max-width:1000px;margin:0 auto;padding:80px 24px}.hero h1{font-size:clamp(44px,8vw,96px);margin:0;font-weight:800;letter-spacing:-.04em}"
           ".hero p{font-size:20px;color:#c4c4cc}section,.card{background:#ffffff0d;border:1px solid #ffffff1f;backdrop-filter:blur(20px);"
           "border-radius:28px;padding:28px;margin:22px 0}h2{font-weight:300;font-size:28px;margin:0 0 14px}.chip,.tag{display:inline-block;"
           "padding:6px 12px;border-radius:99px;background:#ffffff14;margin:3px;font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fit,"
           "minmax(260px,1fr));gap:16px}.proj{background:#ffffff0a;border-radius:20px;padding:18px}.when{color:#a5b4fc;font-size:13px}"
           ".at{color:#a1a1aa;font-weight:400}.otw{color:#86efac;font-size:14px}.made{text-align:center;color:#71717a;padding:30px;font-size:12px}"
           ".contact a{color:#e0e7ff}")
    return page(d, css, f"<div class='wrap'><header class='hero'>{_badge(d)}<h1>{h(d['name'])}</h1><p>{_sub(d)}</p>"
                        f"<p class='contact'>{_contact(d)}</p></header>{_sections(d)}</div>")


def terminal(d):
    css = ("body{background:#0b0f0c;color:#39ff88;font-family:'JetBrains Mono',monospace;padding:24px;font-size:15px;line-height:1.6}"
           ".win{max-width:960px;margin:0 auto;border:1px solid #1f3a2a;border-radius:12px;overflow:hidden;box-shadow:0 0 60px #39ff8822}"
           ".bar{background:#132018;padding:10px 14px;color:#8fbf9f}.bar i{display:inline-block;width:12px;height:12px;border-radius:50%;"
           "margin-right:6px;background:#ff5f56}.bar i+i{background:#ffbd2e}.bar i+i+i{background:#27c93f}.screen{padding:24px}"
           ".p:before{content:'saige@portfolio:~$ ';color:#5eead4}h1{font-size:34px;margin:4px 0;text-shadow:0 0 12px #39ff88}"
           "h2{color:#facc15;font-size:16px;margin:28px 0 6px}h2:before{content:'## '}.chip,.tag{color:#a7f3d0;margin-right:10px}"
           ".chip:before,.tag:before{content:'['}.chip:after,.tag:after{content:']'}h3{font-size:15px;margin:10px 0 2px;color:#e5ffe9}"
           ".at,.when{color:#6ee7b7}.cursor{display:inline-block;width:10px;height:18px;background:#39ff88;animation:b 1s steps(2) infinite;"
           "vertical-align:middle}@keyframes b{50%{opacity:0}}a{color:#5eead4}.otw{color:#facc15}.made{text-align:center;color:#3f6f52;font-size:12px}"
           ".grid{display:block}")
    return page(d, css, f"<div class='win'><div class='bar'><i></i><i></i><i></i> ~/{h(d['first'].lower())} — zsh</div><div class='screen'>"
                        f"<div class='p'>whoami</div><h1>{h(d['name'])}</h1><div>{_sub(d)}</div><div class='p'>contact --all</div>"
                        f"<div>{_contact(d, ' | ')}</div>{_badge(d)}{_sections(d)}<div class='p'><span class='cursor'></span></div></div></div>",
                "JetBrains+Mono:wght@400;700")


def brutalist(d):
    css = ("body{background:#fffb00;color:#000;font-family:'Space Grotesk';}.wrap{max-width:1100px;margin:0 auto;padding:30px}"
           "h1{font-size:clamp(56px,12vw,150px);line-height:.85;margin:0;text-transform:uppercase;letter-spacing:-.05em}"
           ".role{background:#000;color:#fffb00;display:inline-block;padding:6px 14px;font-size:22px;transform:rotate(-2deg);margin:16px 0}"
           "section{border:4px solid #000;box-shadow:10px 10px 0 #000;background:#fff;padding:24px;margin:36px 0}"
           "h2{font-size:42px;margin:0 0 12px;text-transform:uppercase}.chip,.tag{display:inline-block;border:3px solid #000;padding:4px 10px;"
           "margin:4px;font-weight:700;background:#ff5ef7}.tag{background:#00e5ff;font-size:12px}.job,.proj{border-top:3px dashed #000;padding:14px 0}"
           ".grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:0 24px}.when{font-weight:700}.otw{font-weight:700}"
           "a{font-weight:700}.made{text-align:center;padding:20px;font-weight:700}")
    return page(d, css, f"<div class='wrap'><h1>{h(d['name'])}</h1><div class='role'>{_sub(d)}</div><p>{_contact(d)}</p>{_badge(d)}"
                        f"{_sections(d)}</div>", "Space+Grotesk:wght@400;700")


def ide(d):
    files = [("about.md", d["summary"] and f"<p class='lead'>{h(d['summary'])}</p>"), ("skills.json", d["skills"] and
             "<pre>{\n" + ",\n".join(f'  <span class=k>"{h(s)}"</span>: <span class=v>true</span>' for s in d["skills"][:24]) + "\n}</pre>"),
             ("experience.ts", d["experience"] and _exp(d)), ("projects.tsx", d["projects"] and _proj(d)), ("education.yml", _edu(d))]
    files = [(n, c) for n, c in files if c]
    tabs = "".join(f"<a href='#{n.split('.')[0]}' class='tab'>{n}</a>" for n, _ in files)
    tree = "".join(f"<a href='#{n.split('.')[0]}'>📄 {n}</a>" for n, _ in files)
    body = "".join(f"<section id='{n.split('.')[0]}'><div class='fn'>// {n}</div>{c}</section>" for n, c in files)
    css = ("body{background:#1e1e1e;color:#d4d4d4;font-family:'Fira Code',monospace;font-size:14px}.app{display:grid;grid-template-columns:220px 1fr;"
           "min-height:100vh}.side{background:#252526;padding:14px;border-right:1px solid #333}.side a{display:block;padding:4px 6px;color:#ccc;"
           "text-decoration:none}.side a:hover{background:#2a2d2e}.side h4{font-size:11px;color:#888;letter-spacing:.1em}.tabs{background:#2d2d2d;"
           "display:flex;overflow:auto}.tab{padding:10px 16px;color:#9cdcfe;text-decoration:none;border-right:1px solid #1e1e1e}.main{padding:0}"
           ".code{padding:24px 34px}h1{color:#dcdcaa;font-size:30px;margin:0}.cm{color:#6a9955}section{margin:26px 0}.fn{color:#6a9955}"
           "h3{color:#4ec9b0;font-size:15px}.at{color:#ce9178}.when{color:#b5cea8}.tag,.chip{color:#c586c0;margin-right:8px}.k{color:#9cdcfe}"
           ".v{color:#569cd6}a{color:#4fc1ff}.status{position:fixed;bottom:0;left:0;right:0;background:#007acc;color:#fff;padding:3px 12px;"
           "font-size:12px}.otw{color:#b5cea8}.made{display:none}@media(max-width:760px){.app{grid-template-columns:1fr}.side{display:none}}")
    return page(d, css, f"<div class='app'><nav class='side'><h4>EXPLORER</h4><b>{h(d['first'].upper())}-PORTFOLIO</b>{tree}</nav><div class='main'>"
                        f"<div class='tabs'>{tabs}</div><div class='code'><div class='cm'>/** {_sub(d)} */</div><h1>const {h(d['first'])} = "
                        f"new Engineer();</h1><p>{_contact(d)}</p>{_badge(d)}{body}</div></div></div>"
                        f"<div class='status'>⎇ main · {h(d['role'])} · {h(d['location'])}</div>", "Fira+Code:wght@400;600")


def retro_os(d):
    def win(title, inner):
        return f"<div class='win'><div class='tb'><span>{h(title)}</span><b>_ □ ✕</b></div><div class='in'>{inner}</div></div>"
    wins = [win(f"{d['first']}.exe", f"<h1>{h(d['name'])}</h1><p>{_sub(d)}</p><p>{_contact(d)}</p>{_badge(d)}")]
    if d["summary"]:
        wins.append(win("About Me.txt", f"<p>{h(d['summary'])}</p>"))
    if d["skills"]:
        wins.append(win("Control Panel — Skills", f"<div>{_chips(d['skills'])}</div>"))
    if d["experience"]:
        wins.append(win("Work History.doc", _exp(d)))
    if d["projects"]:
        wins.append(win("My Projects", f"<div class='grid'>{_proj(d)}</div>"))
    if d["education"] or d["certifications"]:
        wins.append(win("Education.ini", _edu(d)))
    css = ("body{background:#008080;font-family:'VT323',monospace;font-size:19px;color:#000;padding:24px 16px 60px}.desk{max-width:980px;margin:0 auto}"
           ".win{background:#c0c0c0;border:2px solid;border-color:#fff #404040 #404040 #fff;margin:0 0 22px;box-shadow:2px 2px 0 #000}"
           ".tb{background:linear-gradient(90deg,#000080,#1084d0);color:#fff;display:flex;justify-content:space-between;padding:3px 8px}"
           ".in{padding:14px;background:#fff;margin:4px;border:2px inset #fff}h1{margin:0;font-size:40px}.chip,.tag{display:inline-block;"
           "border:2px outset #fff;background:#c0c0c0;padding:0 8px;margin:3px}.grid{display:grid;grid-template-columns:repeat(auto-fit,"
           "minmax(250px,1fr));gap:12px}.proj{border:1px dotted #000;padding:8px}.task{position:fixed;bottom:0;left:0;right:0;background:#c0c0c0;"
           "border-top:2px solid #fff;padding:4px 8px}.start{border:2px outset #fff;padding:0 10px;font-weight:bold}.made{display:none}a{color:#000080}")
    return page(d, css, f"<div class='desk'>{''.join(wins)}</div><div class='task'><span class='start'>⊞ Start</span> {h(d['name'])}.exe</div>",
                "VT323")


def bento(d):
    cells = [f"<div class='c big'><div class='kicker'>{_badge(d)}</div><h1>{h(d['name'])}</h1><p>{_sub(d)}</p></div>",
             f"<div class='c dark'><div class='n'>{h(d['years'] or str(len(d['experience'])))}</div><p>{'years of experience' if d['years'] else 'roles'}</p></div>",
             f"<div class='c acc'><div class='n'>{len(d['projects'])}</div><p>projects</p></div>",
             f"<div class='c wide'><h2>Toolbox</h2><div>{_chips(d['skills'][:18])}</div></div>",
             f"<div class='c'><h2>Say hi</h2><p>{_contact(d, '<br>')}</p></div>"]
    if d["summary"]:
        cells.append(f"<div class='c wide'><h2>About</h2><p>{h(d['summary'])}</p></div>")
    cells += [f"<div class='c tall'>{_exp(d)}</div>"] if d["experience"] else []
    cells += [f"<div class='c'>{_proj({**d, 'projects': [p]})}</div>" for p in d["projects"][:6]]
    if d["education"] or d["certifications"]:
        cells.append(f"<div class='c wide'><h2>Education</h2>{_edu(d)}</div>")
    css = ("body{background:#f2f0eb;font-family:'Manrope';color:#151515}.grid{max-width:1150px;margin:40px auto;padding:0 16px;display:grid;"
           "grid-template-columns:repeat(4,1fr);gap:14px}.c{background:#fff;border-radius:26px;padding:24px;box-shadow:0 1px 0 #0001}"
           ".big{grid-column:span 2;grid-row:span 2;background:#151515;color:#fff}.big h1{font-size:54px;margin:10px 0;letter-spacing:-.03em}"
           ".wide{grid-column:span 2}.tall{grid-column:span 2;grid-row:span 2}.dark{background:#ff5b2e;color:#fff}.acc{background:#d7f75b}"
           ".n{font-size:64px;font-weight:800}.chip,.tag{display:inline-block;background:#f2f0eb;border-radius:12px;padding:5px 10px;margin:3px;font-size:13px}"
           ".big .otw{color:#d7f75b}h2{margin:0 0 10px;font-size:18px}.when{color:#888;font-size:12px}.at{color:#888;font-weight:400}"
           ".made{text-align:center;color:#999;padding:20px;font-size:12px}@media(max-width:800px){.grid{grid-template-columns:1fr 1fr}.big,.wide,"
           ".tall{grid-column:span 2}}")
    return page(d, css, f"<main class='grid'>{''.join(cells)}</main>", "Manrope:wght@400;600;800")


def newspaper(d):
    css = ("body{background:#f4efe3;color:#111;font-family:'Libre Baskerville',serif}.paper{max-width:1100px;margin:0 auto;padding:30px}"
           ".mast{text-align:center;border-bottom:4px double #111;padding-bottom:10px}.mast h1{font-family:'UnifrakturMaguntia';font-size:"
           "clamp(48px,9vw,110px);margin:0}.date{display:flex;justify-content:space-between;border-bottom:1px solid #111;font-size:12px;"
           "padding:6px 0;text-transform:uppercase;letter-spacing:.1em}.head{font-size:clamp(28px,5vw,54px);text-align:center;margin:20px 0;"
           "font-weight:700}.cols{columns:3 280px;column-gap:30px;column-rule:1px solid #bbb}section{break-inside:avoid;margin-bottom:20px}"
           "h2{font-size:22px;border-bottom:1px solid #111;text-transform:uppercase}.lead:first-letter{font-size:56px;float:left;line-height:.8;"
           "margin:6px 8px 0 0;font-weight:700}.chip,.tag{font-style:italic}.chip:after{content:' • '}.when{font-size:11px;text-transform:uppercase}"
           ".made{text-align:center;font-size:11px;padding:20px}.grid{display:block}")
    return page(d, css, f"<div class='paper'><div class='mast'><h1>The {h(d['first'])} Times</h1></div><div class='date'><span>{h(d['location'])}</span>"
                        f"<span>Special edition: {h(d['role'])}</span><span>{_contact(d, ' · ')}</span></div>"
                        f"<div class='head'>{h(d['name'])} — {_sub(d)}</div>{_badge(d)}<div class='cols'>{_sections(d)}</div></div>",
                "Libre+Baskerville:wght@400;700&family=UnifrakturMaguntia")


def neon_city(d):
    css = ("body{background:#09001a;color:#e0e0ff;font-family:'Orbitron';min-height:100vh;background-image:linear-gradient(#ff00e012 1px,transparent 1px),"
           "linear-gradient(90deg,#00f0ff12 1px,transparent 1px);background-size:44px 44px}.wrap{max-width:1000px;margin:0 auto;padding:70px 24px}"
           "h1{font-size:clamp(40px,8vw,90px);margin:0;color:#fff;text-shadow:0 0 10px #ff00e0,0 0 40px #ff00e0,0 0 80px #ff00e0;"
           "animation:flick 4s infinite}@keyframes flick{93%{opacity:1}94%{opacity:.4}95%{opacity:1}}.sub{color:#00f0ff;text-shadow:0 0 10px #00f0ff}"
           "section{border:1px solid #ff00e066;box-shadow:0 0 24px #ff00e033 inset,0 0 24px #00f0ff22;padding:24px;margin:28px 0;border-radius:4px}"
           "h2{color:#00f0ff;letter-spacing:.2em;font-size:18px}.chip,.tag{display:inline-block;border:1px solid #00f0ff;color:#00f0ff;padding:4px 10px;"
           "margin:4px;font-size:12px;box-shadow:0 0 10px #00f0ff55}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}"
           "p,li{font-family:Inter;line-height:1.6}.when{color:#ff00e0}.at{color:#a5a5ff}a{color:#00f0ff}.otw{color:#39ff14}.made{text-align:center;"
           "padding:20px;color:#6b5b9a;font-size:11px}")
    return page(d, css, f"<div class='wrap'>{_badge(d)}<h1>{h(d['name'])}</h1><p class='sub'>{_sub(d)}</p><p>{_contact(d)}</p>{_sections(d)}</div>",
                "Orbitron:wght@500;800&family=Inter")


def rpg_sheet(d):
    stats = "".join(f"<div class='stat'><span>{h(s)}</span><i style='width:{max(40, 100 - i * 4)}%'></i></div>" for i, s in enumerate(d["skills"][:12]))
    quests = "".join(f"<div class='quest'><b>⚔ {h(e['title'])}</b> — {h(e['company'])}<div class='when'>{h(e['dates'])}</div>{_bul(e['bullets'][:3])}</div>"
                     for e in d["experience"])
    loot = "".join(f"<div class='loot'>🏆 <b>{h(p['name'])}</b><p>{h(p['description'] or (p['highlights'] or [''])[0])}</p>"
                   f"<div class='tags'>{_chips(p['tech'], 'tag')}</div></div>" for p in d["projects"])
    css = ("body{background:#1a1423;color:#f5e6c8;font-family:'Press Start 2P';font-size:11px;line-height:1.9;padding:20px}.sheet{max-width:1000px;"
           "margin:0 auto;border:6px double #e0b84a;padding:24px;background:#2b2138}.top{display:flex;gap:20px;align-items:center}.av{width:110px;"
           "height:110px;background:#e0b84a;color:#1a1423;display:grid;place-items:center;font-size:36px;border:4px solid #fff}h1{font-size:22px;"
           "margin:0 0 8px;color:#ffd866}.cls{color:#7ee787}.lvl{color:#ff7b72}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:22px;margin-top:20px}"
           ".box{border:3px solid #e0b84a;padding:14px}h2{font-size:13px;color:#ffd866;margin:0 0 10px}.stat{margin:6px 0}.stat i{display:block;height:"
           "8px;background:linear-gradient(90deg,#7ee787,#e0b84a);margin-top:3px}.quest,.loot{border-bottom:2px dashed #5a4a6a;padding:8px 0}"
           ".tag{display:inline-block;background:#5a4a6a;padding:2px 6px;margin:2px;font-size:9px}p,li{font-family:Inter;font-size:13px;line-height:1.5}"
           ".when{color:#a99bc0}a{color:#7ee787}.made{text-align:center;font-size:9px;padding:14px}@media(max-width:760px){.grid2{grid-template-columns:1fr}}")
    return page(d, css, f"<div class='sheet'><div class='top'><div class='av'>{h(d['initials'])}</div><div><h1>{h(d['name'])}</h1>"
                        f"<div class='cls'>CLASS: {h(d['role'])}</div><div class='lvl'>LEVEL {h(d['years'] or '1')} · {h(d['location'])}</div>"
                        f"<div>{_contact(d)}</div></div></div>"
                        + (f"<div class='box' style='margin-top:18px'><h2>BACKSTORY</h2><p>{h(d['summary'])}</p></div>" if d['summary'] else "")
                        + f"<div class='grid2'><div class='box'><h2>STATS</h2>{stats}</div><div class='box'><h2>QUESTS COMPLETED</h2>{quests}</div></div>"
                        + (f"<div class='box' style='margin-top:20px'><h2>LEGENDARY LOOT</h2>{loot}</div>" if loot else "")
                        + (f"<div class='box' style='margin-top:20px'><h2>GUILD TRAINING</h2>{_edu(d)}</div>" if d['education'] else "") + "</div>",
                "Press+Start+2P&family=Inter")


def playlist(d):
    tracks = "".join(f"<div class='tr'><span class='no'>{i + 1}</span><div><b>{h(p['name'])}</b><small>{h(', '.join(p['tech'][:4]))}</small></div>"
                     f"<span class='d'>{h((p['description'] or (p['highlights'] or [''])[0])[:90])}</span>"
                     + (f"<a href='{h(p['url'])}' target='_blank' rel='noopener'>▶</a>" if p["url"] else "<span>♪</span>") + "</div>"
                     for i, p in enumerate(d["projects"]))
    albums = "".join(f"<div class='alb'><div class='cover'>{h(e['company'][:2].upper())}</div><b>{h(e['title'])}</b><small>{h(e['company'])} · "
                     f"{h(e['dates'])}</small></div>" for e in d["experience"])
    css = ("body{background:#121212;color:#fff;font-family:'Figtree'}.hero{background:linear-gradient(#1db95488,#121212);padding:70px 32px 30px;"
           "display:flex;gap:26px;align-items:flex-end}.art{width:200px;height:200px;background:#1db954;display:grid;place-items:center;font-size:70px;"
           "font-weight:800;box-shadow:0 20px 60px #000a}.hero h1{font-size:clamp(40px,7vw,86px);margin:0;font-weight:800}.k{font-size:12px;"
           "text-transform:uppercase}.body{padding:24px 32px;max-width:1100px}.tr{display:grid;grid-template-columns:30px 1.2fr 2fr 30px;gap:14px;"
           "padding:12px;border-radius:8px;align-items:center}.tr:hover{background:#ffffff14}.tr small{display:block;color:#b3b3b3}.no,.d{color:#b3b3b3}"
           ".tr a{color:#1db954;text-decoration:none;font-size:20px}.albs{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:18px}"
           ".alb{background:#181818;padding:14px;border-radius:10px}.cover{aspect-ratio:1;background:#282828;display:grid;place-items:center;font-size:40px;"
           "font-weight:800;color:#1db954;margin-bottom:10px;border-radius:6px}.alb small{display:block;color:#b3b3b3}h2{font-size:24px}"
           ".chip{display:inline-block;background:#282828;border-radius:99px;padding:6px 12px;margin:3px;font-size:13px}.otw{color:#1db954}"
           ".made{text-align:center;color:#555;padding:20px;font-size:12px}@media(max-width:700px){.hero{flex-direction:column;align-items:flex-start}"
           ".tr{grid-template-columns:24px 1fr 24px}.d{display:none}}")
    return page(d, css, f"<div class='hero'><div class='art'>{h(d['initials'])}</div><div><div class='k'>Portfolio · {h(d['role'])}</div>"
                        f"<h1>{h(d['name'])}</h1><div>{_sub(d)}</div><div>{_contact(d)}</div>{_badge(d)}</div></div><div class='body'>"
                        + (f"<p>{h(d['summary'])}</p>" if d['summary'] else "") + (f"<h2>Top tracks (projects)</h2>{tracks}" if tracks else "")
                        + (f"<h2>Albums (experience)</h2><div class='albs'>{albums}</div>" if albums else "")
                        + f"<h2>Genres (skills)</h2><div>{_chips(d['skills'])}</div>" + (f"<h2>Liner notes</h2>{_edu(d)}" if d['education'] else "")
                        + "</div>", "Figtree:wght@400;700;800")


def chat(d):
    msgs = [("them", "Hey! Who are you? 👋"), ("me", f"I'm {d['name']}, {d['role']}" + (f" based in {d['location']}" if d["location"] else "") + ".")]
    if d["summary"]:
        msgs += [("them", "Tell me a bit more?"), ("me", d["summary"])]
    if d["skills"]:
        msgs += [("them", "What's in your toolbox?"), ("me", ", ".join(d["skills"][:16]))]
    for e in d["experience"][:4]:
        msgs += [("them", f"What did you do at {e['company']}?"), ("me", f"{e['title']} ({e['dates']}). " + " ".join(e["bullets"][:2]))]
    for p in d["projects"][:4]:
        msgs += [("them", f"Show me {p['name']}!"), ("me", p["description"] or "; ".join(p["highlights"][:2]) or ", ".join(p["tech"]))]
    if d["email"] or d["links"]:
        msgs += [("them", "How do I reach you?"), ("me", "RAW")]
    bubbles = "".join(f"<div class='m {w}'>{_contact(d, '<br>') if t == 'RAW' else h(t)}</div>" for w, t in msgs)
    css = ("body{background:#e5ddd5;font-family:'Inter';margin:0}.phone{max-width:560px;margin:0 auto;min-height:100vh;background:#efeae2;"
           "display:flex;flex-direction:column}.top{background:#075e54;color:#fff;padding:14px 18px;display:flex;gap:12px;align-items:center;"
           "position:sticky;top:0}.av{width:42px;height:42px;border-radius:50%;background:#25d366;display:grid;place-items:center;font-weight:700}"
           ".top small{display:block;opacity:.8}.thread{padding:18px;display:flex;flex-direction:column;gap:8px}.m{max-width:80%;padding:9px 13px;"
           "border-radius:12px;font-size:15px;line-height:1.45;box-shadow:0 1px 0 #0001;animation:pop .4s both}.them{background:#fff;align-self:"
           "flex-start}.me{background:#d9fdd3;align-self:flex-end}@keyframes pop{from{transform:scale(.9);opacity:0}}.made{text-align:center;"
           "font-size:11px;color:#777;padding:14px}a{color:#075e54}")
    status = "online · open to opportunities" if d["open_to_work"] else "online"
    return page(d, css, f"<div class='phone'><div class='top'><div class='av'>{h(d['initials'])}</div><div><b>{h(d['name'])}</b><small>{status}</small>"
                        f"</div></div><div class='thread'>{bubbles}</div></div>")


def blueprint(d):
    css = ("body{background:#0d3b66;color:#e8f1ff;font-family:'IBM Plex Mono';background-image:linear-gradient(#ffffff14 1px,transparent 1px),"
           "linear-gradient(90deg,#ffffff14 1px,transparent 1px),linear-gradient(#ffffff08 1px,transparent 1px),linear-gradient(90deg,#ffffff08 1px,"
           "transparent 1px);background-size:100px 100px,100px 100px,20px 20px,20px 20px}.wrap{max-width:1050px;margin:0 auto;padding:50px 24px}"
           ".title{border:2px solid #e8f1ff;padding:20px;position:relative}.title:after{content:'DWG NO. ' attr(data-n);position:absolute;right:10px;"
           "bottom:6px;font-size:11px}h1{font-size:clamp(34px,6vw,64px);margin:0;letter-spacing:.06em;text-transform:uppercase}section{border:1px dashed"
           " #e8f1ffaa;padding:20px;margin:24px 0;position:relative}h2{position:absolute;top:-12px;left:14px;background:#0d3b66;padding:0 8px;"
           "margin:0;font-size:13px;letter-spacing:.2em}.chip,.tag{display:inline-block;border:1px solid #9ec5ff;padding:2px 8px;margin:3px;"
           "font-size:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.proj{border:1px solid #9ec5ff55;"
           "padding:12px}.when{color:#9ec5ff;font-size:12px}a{color:#ffe08a}.otw{color:#ffe08a}.made{text-align:center;font-size:11px;padding:20px}")
    return page(d, css, f"<div class='wrap'><div class='title' data-n='{h(d['initials'])}-001'><h1>{h(d['name'])}</h1><p>SPEC: {_sub(d)}</p>"
                        f"<p>{_contact(d, ' / ')}</p>{_badge(d)}</div>{_sections(d)}</div>", "IBM+Plex+Mono:wght@400;600")


def periodic(d):
    cats = ["#ff6b6b", "#ffd93d", "#6bcB77", "#4d96ff", "#c77dff", "#ff9f1c"]
    els = "".join(f"<div class='el' style='background:{cats[i % len(cats)]}'><small>{i + 1}</small><b>{h(s[:2].title())}</b><span>{h(s)}</span></div>"
                  for i, s in enumerate(d["skills"][:36]))
    css = ("body{background:#101418;color:#eef;font-family:'Sora'}.wrap{max-width:1150px;margin:0 auto;padding:50px 20px}h1{font-size:clamp(36px,6vw,"
           "70px);margin:0}.table{display:grid;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px;margin:26px 0}.el{aspect-ratio:1;"
           "border-radius:10px;color:#111;padding:8px;display:flex;flex-direction:column;justify-content:space-between;transition:transform .2s}"
           ".el:hover{transform:scale(1.08) rotate(-2deg)}.el b{font-size:30px}.el span{font-size:10px;font-weight:600;line-height:1.1}.el small{"
           "font-size:10px}section{background:#1a2027;border-radius:18px;padding:22px;margin:18px 0}h2{margin:0 0 10px}.chips{display:none}"
           ".tag{display:inline-block;background:#2a323c;border-radius:8px;padding:3px 8px;margin:2px;font-size:12px}.grid{display:grid;"
           "grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.when{color:#8aa}.at{color:#9ab;font-weight:400}a{color:#ffd93d}"
           ".otw{color:#6bcB77}.made{text-align:center;color:#556;padding:20px;font-size:12px}")
    return page(d, css, f"<div class='wrap'>{_badge(d)}<h1>The Periodic Table of {h(d['first'])}</h1><p>{_sub(d)}</p><p>{_contact(d)}</p>"
                        f"<div class='table'>{els}</div>{_sections(d)}</div>", "Sora:wght@400;600;800")


def metro(d):
    stops = "".join(f"<div class='stop'><i></i><div><div class='when'>{h(e['dates'])}</div><h3>{h(e['title'])}</h3><div class='at'>{h(e['company'])}</div>"
                    f"{_bul(e['bullets'][:3])}</div></div>" for e in d["experience"])
    stops += "".join(f"<div class='stop edu'><i></i><div><h3>{h(e['degree'])}</h3><div class='at'>{h(e['school'])} {h(e['years'])}</div></div></div>"
                     for e in d["education"])
    css = ("body{background:#fafafa;color:#1b1b1b;font-family:'Barlow'}.wrap{max-width:900px;margin:0 auto;padding:50px 24px}.sign{background:#1b1b1b;"
           "color:#fff;border-radius:14px;padding:22px;display:flex;gap:18px;align-items:center}.line{width:62px;height:62px;border-radius:50%;"
           "background:#e4002b;display:grid;place-items:center;font-size:24px;font-weight:800}h1{margin:0;font-size:clamp(30px,5vw,52px)}"
           ".route{position:relative;margin:40px 0 0 20px;border-left:10px solid #e4002b;padding-left:30px}.stop{position:relative;padding:0 0 30px}"
           ".stop i{position:absolute;left:-49px;top:2px;width:28px;height:28px;border-radius:50%;background:#fff;border:7px solid #1b1b1b}"
           ".edu i{border-color:#0072ce}h3{margin:2px 0;font-size:20px}.when{font-weight:700;color:#e4002b}.at{color:#666}section{background:#fff;"
           "border-radius:14px;padding:20px;margin:22px 0;box-shadow:0 1px 3px #0001}.chip,.tag{display:inline-block;background:#1b1b1b;color:#fff;"
           "border-radius:6px;padding:3px 9px;margin:3px;font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));"
           "gap:14px}#work,#edu{display:none}a{color:#0072ce}.otw{color:#00a650;font-weight:700}.made{text-align:center;color:#999;font-size:12px}")
    return page(d, css, f"<div class='wrap'><div class='sign'><div class='line'>{h(d['initials'][:1])}</div><div><h1>{h(d['name'])} Line</h1>"
                        f"<div>{_sub(d)}</div></div></div><p>{_contact(d)}</p>{_badge(d)}<div class='route'>{stops}"
                        f"<div class='stop'><i></i><h3>Next stop: your team?</h3></div></div>{_sections(d)}</div>", "Barlow:wght@400;700;800")


def receipt(d):
    lines = "".join(f"<div class='row'><span>{h(s)}</span><span>✓</span></div>" for s in d["skills"][:20])
    jobs = "".join(f"<div class='row'><span>{h(e['title'])} @ {h(e['company'])}</span><span>{h(e['dates'].split('–')[0].strip())}</span></div>"
                   for e in d["experience"])
    projs = "".join(f"<div class='row'><span>{h(p['name'])}</span><span>1x</span></div>" for p in d["projects"])
    css = ("body{background:#d9d4c7;font-family:'Courier Prime',monospace;padding:40px 12px}.r{max-width:420px;margin:0 auto;background:#fffef8;"
           "padding:28px 24px;box-shadow:0 10px 30px #0003;position:relative}.r:after{content:'';position:absolute;left:0;right:0;bottom:-14px;"
           "height:14px;background:radial-gradient(circle at 7px -2px,transparent 8px,#fffef8 8px) repeat-x;background-size:14px 14px}"
           "h1{text-align:center;font-size:22px;margin:0}.c{text-align:center}.hr{border-top:2px dashed #333;margin:14px 0}.row{display:flex;"
           "justify-content:space-between;gap:10px;font-size:14px;margin:4px 0}.row span:first-child{overflow:hidden}h2{font-size:15px;margin:8px 0}"
           ".tot{font-size:18px;font-weight:700}.bar{height:46px;background:repeating-linear-gradient(90deg,#000 0 2px,transparent 2px 4px,#000 4px 7px,"
           "transparent 7px 9px);margin-top:16px}.made{text-align:center;font-size:11px;margin-top:30px}a{color:#000}p{font-size:13px}")
    return page(d, css, f"<div class='r'><h1>*** {h(d['name'].upper())} ***</h1><div class='c'>{h(d['role'])}<br>{h(d['location'])}</div>"
                        f"<div class='hr'></div>" + (f"<p>{h(d['summary'])}</p><div class='hr'></div>" if d['summary'] else "")
                        + f"<h2>SKILLS</h2>{lines}<div class='hr'></div><h2>EXPERIENCE</h2>{jobs}"
                        + (f"<div class='hr'></div><h2>PROJECTS</h2>{projs}" if projs else "")
                        + f"<div class='hr'></div><div class='row tot'><span>TOTAL VALUE</span><span>PRICELESS</span></div>"
                        f"<div class='c' style='margin-top:12px'>{_contact(d, '<br>')}</div><div class='bar'></div>"
                        "<div class='c'>THANK YOU FOR VISITING</div></div>", "Courier+Prime:wght@400;700")


def boarding_pass(d):
    css = ("body{background:#0f172a;font-family:'Outfit';color:#0f172a;padding:40px 14px}.bp{max-width:900px;margin:0 auto;background:#fff;"
           "border-radius:22px;display:grid;grid-template-columns:2.2fr 1fr;overflow:hidden}.main{padding:28px;border-right:3px dashed #cbd5e1}"
           ".stub{padding:28px;background:#f8fafc}.air{color:#2563eb;font-weight:800;letter-spacing:.2em;font-size:13px}h1{font-size:clamp(28px,5vw,"
           "48px);margin:8px 0}.route{display:flex;align-items:center;gap:18px;font-size:40px;font-weight:800;margin:14px 0}.route small{display:block;"
           "font-size:12px;color:#64748b;font-weight:400}.plane{flex:1;border-top:2px dotted #94a3b8;position:relative}.plane:after{content:'✈';"
           "position:absolute;left:45%;top:-26px;font-size:28px;color:#2563eb}.f{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:"
           "12px}.f small{display:block;color:#64748b;font-size:11px;text-transform:uppercase}.more{max-width:900px;margin:22px auto 0;color:#e2e8f0}"
           ".more section{background:#1e293b;border-radius:18px;padding:22px;margin:16px 0}.chip,.tag{display:inline-block;background:#334155;"
           "border-radius:99px;padding:4px 10px;margin:3px;font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));"
           "gap:14px}.when{color:#93c5fd}.at{color:#94a3b8;font-weight:400}.bar{height:60px;background:repeating-linear-gradient(90deg,#0f172a 0 3px,"
           "transparent 3px 6px);margin-top:20px}a{color:#2563eb}.more a{color:#93c5fd}.otw{color:#16a34a;font-weight:700}.made{text-align:center;"
           "color:#64748b;font-size:12px}@media(max-width:700px){.bp{grid-template-columns:1fr}.main{border-right:0;border-bottom:3px dashed #cbd5e1}}")
    frm = (d["experience"][-1]["company"][:3] if d["experience"] else "NOW").upper()
    return page(d, css, f"<div class='bp'><div class='main'><div class='air'>SAIGE AIRWAYS · CAREER CLASS</div><h1>{h(d['name'])}</h1>"
                        f"<div class='route'><div>{h(frm)}<small>Where I started</small></div><div class='plane'></div><div>YOU<small>Your team</small></div></div>"
                        f"<div class='f'><div><small>Role</small>{h(d['role'])}</div><div><small>Experience</small>{h(d['years'] or '—')} yrs</div>"
                        f"<div><small>Base</small>{h(d['location'] or 'Anywhere')}</div></div>{_badge(d)}</div><div class='stub'>"
                        f"<b>PASSENGER</b><p>{h(d['name'])}</p><b>CONTACT</b><p>{_contact(d, '<br>')}</p><div class='bar'></div></div></div>"
                        f"<div class='more'>{_sections(d)}</div>", "Outfit:wght@400;600;800")


def polaroid(d):
    shots = "".join(f"<figure class='pol' style='transform:rotate({(-1) ** i * (2 + i % 3)}deg)'><div class='ph'>{h(p['name'][:1])}</div>"
                    f"<figcaption><b>{h(p['name'])}</b><br>{h((p['description'] or (p['highlights'] or [''])[0])[:110])}</figcaption></figure>"
                    for i, p in enumerate(d["projects"]))
    css = ("body{background:#c9b79c url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='6' height='6'%3E%3Crect width='6' height='6' "
           "fill='%23c9b79c'/%3E%3Ccircle cx='1' cy='1' r='1' fill='%23b8a587'/%3E%3C/svg%3E\");font-family:'Caveat';color:#2b2118}.wrap{max-width:1050px;"
           "margin:0 auto;padding:40px 18px}h1{font-size:clamp(48px,9vw,96px);margin:0;transform:rotate(-2deg)}.sub{font-size:26px}.board{display:grid;"
           "grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:30px;margin:30px 0}.pol{background:#fff;padding:12px 12px 20px;margin:0;"
           "box-shadow:0 8px 20px #0003}.ph{aspect-ratio:1;background:linear-gradient(135deg,#f6d365,#fda085);display:grid;place-items:center;"
           "font-size:80px;color:#fff}figcaption{font-size:20px;margin-top:8px;line-height:1.1}section{background:#fffdf5;padding:20px;margin:24px 0;"
           "box-shadow:0 6px 16px #0002;transform:rotate(.4deg);font-family:Inter;font-size:15px}h2{font-family:'Caveat';font-size:34px;margin:0}"
           ".chip,.tag{display:inline-block;background:#ffe58a;padding:3px 9px;margin:3px;transform:rotate(-1deg)}#projects{display:none}"
           ".when{color:#8a6d4b}.at{color:#8a6d4b;font-weight:400}a{color:#b5451b}.otw{font-size:22px;color:#2e7d32}.made{text-align:center;"
           "font-family:Inter;font-size:12px}")
    return page(d, css, f"<div class='wrap'><h1>{h(d['name'])}</h1><div class='sub'>{_sub(d)}</div><p style='font-family:Inter'>{_contact(d)}</p>"
                        f"{_badge(d)}<div class='board'>{shots}</div>{_sections(d)}</div>", "Caveat:wght@500;700&family=Inter")


def comic(d):
    css = ("body{background:#fef3c7;font-family:'Bangers';color:#111;letter-spacing:.02em}.wrap{max-width:1100px;margin:0 auto;padding:30px}"
           ".hero{background:#ef4444;color:#fff;border:6px solid #111;padding:30px;position:relative;box-shadow:12px 12px 0 #111;"
           "background-image:radial-gradient(#fff3 2px,transparent 2px);background-size:14px 14px}h1{font-size:clamp(50px,10vw,120px);margin:0;"
           "-webkit-text-stroke:3px #111;text-shadow:6px 6px 0 #111}.pow{position:absolute;right:20px;top:-26px;background:#facc15;color:#111;"
           "padding:12px 22px;font-size:30px;transform:rotate(10deg);border:4px solid #111;clip-path:polygon(0 15%,15% 0,30% 12%,50% 0,65% 14%,85% 0,"
           "100% 18%,92% 50%,100% 82%,82% 100%,62% 88%,45% 100%,30% 86%,12% 100%,0 80%,8% 50%)}.panels{display:grid;grid-template-columns:repeat(auto-fit,"
           "minmax(320px,1fr));gap:20px;margin-top:30px}section{background:#fff;border:5px solid #111;padding:20px;box-shadow:8px 8px 0 #111;margin:0}"
           "h2{background:#3b82f6;color:#fff;display:inline-block;padding:4px 14px;border:3px solid #111;font-size:26px;margin:0 0 12px;"
           "transform:rotate(-2deg)}p,li{font-family:'Comic Neue',Inter;font-size:16px;letter-spacing:0}.chip,.tag{display:inline-block;background:#facc15;"
           "border:3px solid #111;padding:2px 10px;margin:4px;font-size:18px}.grid{display:block}.when{color:#ef4444}.at{color:#555}a{color:#1d4ed8}"
           ".otw{font-size:22px}.made{text-align:center;padding:20px;font-size:16px}")
    secs = _sections(d).replace("<section", "<section class='p'")
    return page(d, css, f"<div class='wrap'><div class='hero'><div class='pow'>HIRE ME!</div><h1>{h(d['name'])}</h1><p style='font-size:28px'>"
                        f"{_sub(d)}</p><p style='font-family:Inter;font-size:15px'>{_contact(d)}</p></div>{_badge(d)}<div class='panels'>{secs}</div></div>",
                "Bangers&family=Comic+Neue:wght@400;700&family=Inter")


def space(d):
    css = ("body{background:#000;color:#e6e9ff;font-family:'Exo 2';min-height:100vh;background-image:radial-gradient(1px 1px at 20px 30px,#fff,transparent),"
           "radial-gradient(1px 1px at 120px 80px,#fff8,transparent),radial-gradient(2px 2px at 220px 150px,#bcd,transparent),radial-gradient(1px 1px at"
           " 300px 40px,#fff,transparent),radial-gradient(1px 1px at 380px 200px,#fff9,transparent);background-size:420px 260px;animation:tw 60s linear "
           "infinite}@keyframes tw{to{background-position:0 -2600px}}.wrap{max-width:980px;margin:0 auto;padding:80px 24px}.planet{width:140px;height:"
           "140px;border-radius:50%;background:radial-gradient(circle at 35% 35%,#8be9fd,#6272a4 60%,#282a36);box-shadow:0 0 80px #8be9fd66;margin-bottom:"
           "20px;position:relative}.planet:after{content:'';position:absolute;inset:50px -40px;border:3px solid #ffb86c99;border-radius:50%;"
           "transform:rotate(-20deg)}h1{font-size:clamp(40px,7vw,84px);margin:0;font-weight:800}section{background:#0b0f2acc;border:1px solid #2a3170;"
           "border-radius:22px;padding:24px;margin:24px 0}h2{color:#8be9fd;font-weight:300;letter-spacing:.15em;text-transform:uppercase;font-size:16px}"
           ".chip,.tag{display:inline-block;border:1px solid #6272a4;border-radius:99px;padding:4px 11px;margin:3px;font-size:13px}.grid{display:grid;"
           "grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.proj{background:#141a44;border-radius:16px;padding:16px}.when{color:#ffb86c}"
           ".at{color:#99a;font-weight:400}a{color:#8be9fd}.otw{color:#50fa7b}.made{text-align:center;color:#556;padding:20px;font-size:12px}")
    return page(d, css, f"<div class='wrap'><div class='planet'></div>{_badge(d)}<h1>{h(d['name'])}</h1><p>{_sub(d)}</p><p>{_contact(d)}</p>"
                        f"{_sections(d)}</div>", "Exo+2:wght@300;600;800")


def kanban(d):
    def col(title, cards, color):
        return f"<div class='col'><div class='ch' style='border-color:{color}'>{h(title)} <span>{len(cards)}</span></div>{''.join(cards)}</div>"
    done = [f"<div class='card'><b>{h(e['title'])}</b><small>{h(e['company'])} · {h(e['dates'])}</small>{_bul(e['bullets'][:2])}</div>"
            for e in d["experience"]]
    shipped = [f"<div class='card'><b>{h(p['name'])}</b><p>{h((p['description'] or (p['highlights'] or [''])[0])[:120])}</p>"
               f"<div class='tags'>{_chips(p['tech'][:4], 'tag')}</div></div>" for p in d["projects"]]
    skills = [f"<div class='card mini'>{h(s)}</div>" for s in d["skills"][:14]]
    nxt = [f"<div class='card hot'><b>Joining your team</b><small>{_contact(d, ' · ')}</small></div>"]
    css = ("body{background:#f4f5f7;font-family:'Inter';color:#172b4d}.top{padding:26px 28px;background:#0052cc;color:#fff}.top h1{margin:0;font-size:32px}"
           ".board{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(270px,1fr);gap:16px;padding:24px;overflow-x:auto}.col{background:#ebecf0;"
           "border-radius:10px;padding:10px}.ch{font-weight:700;font-size:13px;text-transform:uppercase;padding:6px 6px 10px;border-top:4px solid}"
           ".ch span{background:#dfe1e6;border-radius:99px;padding:0 8px;margin-left:4px}.card{background:#fff;border-radius:8px;padding:12px;margin:8px 0;"
           "box-shadow:0 1px 1px #091e4240;font-size:14px}.card small{display:block;color:#5e6c84}.card p{margin:6px 0}.mini{padding:8px 12px}"
           ".hot{background:#e3fcef}.tag{display:inline-block;background:#dfe1e6;border-radius:4px;padding:1px 6px;margin:2px;font-size:11px}"
           ".about{padding:0 28px;max-width:900px}.made{text-align:center;color:#999;font-size:12px;padding:16px}a{color:#0052cc}.top a{color:#fff}")
    return page(d, css, f"<div class='top'><h1>{h(d['name'])}'s board</h1><div>{_sub(d)}</div></div>"
                        + (f"<p class='about'>{h(d['summary'])}</p>" if d['summary'] else "")
                        + f"<div class='board'>{col('Skills', skills, '#6554c0')}{col('Done (experience)', done, '#00875a')}"
                        f"{col('Shipped (projects)', shipped, '#ff991f')}{col('Up next', nxt, '#0052cc')}</div>")


def museum(d):
    css = ("body{background:#f5f1ea;font-family:'Cormorant Garamond',serif;color:#1d1b18}.hall{max-width:1150px;margin:0 auto;padding:60px 24px}"
           ".plaque{text-align:center;margin-bottom:40px}h1{font-size:clamp(48px,8vw,100px);font-weight:300;margin:0;letter-spacing:.04em}.sub{font-family:"
           "Inter;letter-spacing:.3em;text-transform:uppercase;font-size:12px}.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));"
           "gap:40px}.frame{background:#fff;border:14px solid #2b2620;box-shadow:inset 0 0 0 10px #e9e2d3,0 18px 40px #0003;padding:34px 26px;"
           "text-align:center}.frame h3{font-size:30px;font-weight:500;margin:0}.label{font-family:Inter;font-size:12px;color:#7a7266;margin-top:14px}"
           "section{margin:50px 0}h2{font-weight:300;font-size:40px;text-align:center}.chip,.tag{display:inline-block;font-family:Inter;font-size:12px;"
           "border-bottom:1px solid #b9ad97;margin:6px 10px}.chips{text-align:center}.job{text-align:center;margin:26px 0}.when{font-family:Inter;font-size:12px;"
           "letter-spacing:.2em;text-transform:uppercase;color:#8d7f66}ul{list-style:none;padding:0;font-size:19px}#projects{display:none}a{color:#7a4f1d}"
           ".otw{font-family:Inter;font-size:12px;color:#5b7a3c}.made{text-align:center;font-family:Inter;font-size:11px;color:#9a917f}")
    frames = "".join(f"<div class='frame'><h3>{h(p['name'])}</h3><p>{h(p['description'] or (p['highlights'] or [''])[0])}</p>"
                     f"<div class='label'>{h(', '.join(p['tech'][:4]))}" + (f" · <a href='{h(p['url'])}'>view</a>" if p['url'] else "") + "</div></div>"
                     for p in d["projects"])
    return page(d, css, f"<div class='hall'><div class='plaque'><div class='sub'>A retrospective</div><h1>{h(d['name'])}</h1><div class='sub'>{_sub(d)}</div>"
                        f"<p style='font-family:Inter;font-size:14px'>{_contact(d)}</p>{_badge(d)}</div><div class='gallery'>{frames}</div>{_sections(d)}</div>",
                "Cormorant+Garamond:wght@300;500&family=Inter")


def split_sticky(d):
    css = ("body{font-family:'DM Sans';color:#e7e5e4;background:#0c0a09}.lay{display:grid;grid-template-columns:minmax(300px,38%) 1fr;max-width:1300px;"
           "margin:0 auto}.left{position:sticky;top:0;height:100vh;padding:70px 40px;display:flex;flex-direction:column;justify-content:space-between}"
           "h1{font-size:clamp(40px,5vw,64px);margin:0;line-height:1}.role{color:#fb923c;font-size:20px;margin:12px 0}.nav a{display:block;color:#a8a29e;"
           "text-decoration:none;padding:6px 0;letter-spacing:.15em;font-size:12px;text-transform:uppercase}.nav a:hover{color:#fff;padding-left:12px;"
           "transition:.2s}.right{padding:70px 40px}section{margin-bottom:70px}h2{font-size:13px;letter-spacing:.2em;text-transform:uppercase;color:#a8a29e}"
           ".job,.proj{padding:18px;border-radius:14px;margin:0 -18px 8px}.job:hover,.proj:hover{background:#1c1917}.chip,.tag{display:inline-block;"
           "background:#fb923c22;color:#fdba74;border-radius:99px;padding:4px 11px;margin:3px;font-size:13px}.when{color:#78716c;font-size:13px}"
           ".at{color:#fb923c;font-weight:400}.grid{display:block}a{color:#fdba74}.otw{color:#4ade80}.made{text-align:center;color:#57534e;font-size:12px;"
           "padding:20px}@media(max-width:860px){.lay{grid-template-columns:1fr}.left{position:static;height:auto}}")
    nav = "".join(f"<a href='#{i}'>{n}</a>" for i, n in (("about", "About"), ("skills", "Skills"), ("work", "Experience"), ("projects", "Projects"),
                                                        ("edu", "Education")))
    return page(d, css, f"<div class='lay'><aside class='left'><div><h1>{h(d['name'])}</h1><div class='role'>{h(d['role'])}</div><p>{_sub(d)}</p>"
                        f"{_badge(d)}<nav class='nav'>{nav}</nav></div><div>{_contact(d, '<br>')}</div></aside><main class='right'>{_sections(d)}</main></div>",
                "DM+Sans:wght@400;500;700")


def magazine(d):
    css = ("body{background:#fff;color:#0a0a0a;font-family:'Playfair Display',serif}.cover{min-height:92vh;background:#e11d48;color:#fff;padding:40px;"
           "display:flex;flex-direction:column;justify-content:space-between;position:relative;overflow:hidden}.mast{font-size:clamp(60px,14vw,190px);"
           "font-weight:900;line-height:.8;letter-spacing:-.04em}.issue{font-family:Inter;font-size:12px;letter-spacing:.3em;text-transform:uppercase}"
           ".big{font-size:clamp(32px,5vw,60px);font-style:italic;max-width:800px}.blurbs{font-family:Inter;font-weight:700;text-transform:uppercase;"
           "font-size:14px;line-height:1.8}.in{max-width:1000px;margin:0 auto;padding:60px 24px;columns:2 380px;column-gap:50px}section{break-inside:avoid;"
           "margin-bottom:30px}h2{font-size:38px;font-weight:900;margin:0 0 10px;border-top:6px solid #e11d48;padding-top:8px}p,li{font-family:Inter;"
           "line-height:1.7}.lead:first-letter{font-size:70px;float:left;line-height:.8;margin:8px 10px 0 0;color:#e11d48;font-family:'Playfair Display'}"
           ".chip,.tag{display:inline-block;font-family:Inter;font-size:12px;text-transform:uppercase;letter-spacing:.1em;border:1px solid #0a0a0a;"
           "padding:3px 9px;margin:3px}.grid{display:block}.when{font-family:Inter;color:#e11d48;font-size:12px}.at{font-weight:400;font-style:italic}"
           "a{color:#e11d48}.cover a{color:#fff}.otw{font-family:Inter}.made{text-align:center;font-family:Inter;font-size:11px;padding:20px}")
    blurbs = "<br>".join(h(x) for x in [f"Inside: {len(d['projects'])} projects", f"{d['experience_text']}" if d["experience_text"] else "",
                                        f"Plus: {', '.join(d['skills'][:3])}"] if x)
    return page(d, css, f"<div class='cover'><div class='issue'>{h(d['role'])} issue · {h(d['location'])}</div><div><div class='mast'>"
                        f"{h(d['first'].upper())}</div><div class='big'>{h(d['tagline'] or d['name'])}</div></div><div class='blurbs'>{blurbs}"
                        f"<br><span style='font-weight:400;text-transform:none'>{_contact(d)}</span></div></div><div class='in'>{_sections(d)}</div>",
                "Playfair+Display:ital,wght@0,400;0,900;1,400&family=Inter:wght@400;700")


def minimal_swiss(d):
    css = ("body{font-family:'Inter';color:#111;background:#fff}.wrap{max-width:1100px;margin:0 auto;padding:80px 32px;display:grid;grid-template-columns:"
           "1fr 3fr;gap:40px}h1{grid-column:1/-1;font-size:clamp(48px,9vw,128px);font-weight:800;letter-spacing:-.06em;margin:0;line-height:.9}"
           ".meta{font-size:14px;line-height:1.7;color:#555}.meta a{color:#111}section{display:contents}h2{font-size:14px;font-weight:600;margin:0;"
           "color:#e30613;text-transform:uppercase;letter-spacing:.1em}section>:not(h2){grid-column:2}.chip,.tag{display:inline-block;font-size:14px;"
           "margin-right:14px}.job,.proj{border-top:1px solid #111;padding:16px 0}.grid{display:block}.when{font-size:13px;color:#777}"
           ".at{font-weight:400;color:#777}.otw{color:#e30613}.made{text-align:center;color:#aaa;font-size:12px;padding:30px}"
           "@media(max-width:700px){.wrap{grid-template-columns:1fr}section>:not(h2){grid-column:1}}")
    return page(d, css, f"<div class='wrap'><h1>{h(d['name'])}</h1><div class='meta'>{_badge(d)}<br>{_sub(d)}</div><div class='meta'>{_contact(d, '<br>')}</div>"
                        f"{_sections(d)}</div>", "Inter:wght@400;600;800")


def holo_card(d):
    css = ("body{background:#0a0a0f;color:#f5f5f7;font-family:'Space Grotesk';min-height:100vh}.wrap{max-width:1000px;margin:0 auto;padding:60px 20px}"
           ".id{border-radius:28px;padding:34px;background:linear-gradient(115deg,#ff6ec7,#7873f5,#4ade80,#facc15,#ff6ec7);background-size:300% 300%;"
           "animation:holo 8s ease infinite;color:#0a0a0f;box-shadow:0 30px 80px #7873f555;display:grid;grid-template-columns:auto 1fr;gap:26px;"
           "align-items:center}@keyframes holo{50%{background-position:100% 50%}}.chipc{width:120px;height:120px;border-radius:24px;background:#0a0a0f;"
           "color:#fff;display:grid;place-items:center;font-size:44px;font-weight:700}h1{font-size:clamp(34px,6vw,64px);margin:0}.id a{color:#0a0a0f;"
           "font-weight:700}section{border:1px solid #2a2a35;border-radius:24px;padding:24px;margin:22px 0;background:#12121a}h2{margin:0 0 12px;"
           "background:linear-gradient(90deg,#ff6ec7,#7873f5);-webkit-background-clip:text;color:transparent;font-size:24px}.chip,.tag{display:inline-block;"
           "border:1px solid #3a3a48;border-radius:10px;padding:5px 11px;margin:3px;font-size:13px}.grid{display:grid;grid-template-columns:repeat(auto-fit,"
           "minmax(260px,1fr));gap:14px}.proj{background:#1a1a24;border-radius:18px;padding:16px}.when{color:#a5a3ff}.at{color:#9a9aa8;font-weight:400}"
           "a{color:#c4b5fd}.otw{font-weight:700}.made{text-align:center;color:#555;font-size:12px;padding:20px}@media(max-width:600px){.id{"
           "grid-template-columns:1fr}}")
    return page(d, css, f"<div class='wrap'><div class='id'><div class='chipc'>{h(d['initials'])}</div><div>{_badge(d)}<h1>{h(d['name'])}</h1>"
                        f"<div>{_sub(d)}</div><div>{_contact(d)}</div></div></div>{_sections(d)}</div>", "Space+Grotesk:wght@400;700")


def zen(d):
    css = ("body{background:#f7f3ec;color:#2f2a24;font-family:'Noto Serif JP',serif}.wrap{max-width:760px;margin:0 auto;padding:110px 28px}"
           ".enso{width:120px;height:120px;border-radius:50%;border:10px solid #2f2a24;border-right-color:transparent;transform:rotate(-30deg);"
           "margin-bottom:40px;opacity:.85}h1{font-weight:300;font-size:clamp(36px,6vw,64px);margin:0;letter-spacing:.08em}.sub{color:#8a7f72;"
           "letter-spacing:.2em;font-size:13px;text-transform:uppercase;margin:16px 0 50px;font-family:Inter}section{margin:70px 0}h2{font-weight:300;"
           "font-size:14px;letter-spacing:.4em;text-transform:uppercase;color:#a0522d;font-family:Inter}p,li{line-height:2;font-size:17px}"
           ".chip,.tag{display:inline-block;margin:0 16px 8px 0;font-size:15px;color:#5b5147}.job,.proj{margin:30px 0}.grid{display:block}"
           ".when{font-family:Inter;font-size:12px;color:#a59a8c;letter-spacing:.1em}.at{font-weight:300;color:#8a7f72}a{color:#a0522d}.otw{font-family:"
           "Inter;font-size:12px;color:#6b8e23}.made{text-align:center;color:#b5aa9b;font-size:11px;padding:30px;font-family:Inter}")
    return page(d, css, f"<div class='wrap'><div class='enso'></div><h1>{h(d['name'])}</h1><div class='sub'>{_sub(d)}</div><p>{_contact(d)}</p>"
                        f"{_badge(d)}{_sections(d)}</div>", "Noto+Serif+JP:wght@300;500&family=Inter")


TEMPLATES = {
    "aurora_glass": ("Aurora Glass", "Floating glass panels over a slowly drifting aurora", aurora_glass, ["#05050a", "#7c3aed", "#06b6d4"]),
    "terminal": ("Hacker Terminal", "Your career as a live zsh session with a blinking cursor", terminal, ["#0b0f0c", "#39ff88", "#facc15"]),
    "brutalist": ("Neo-Brutalist", "Loud yellow, hard shadows, zero apologies", brutalist, ["#fffb00", "#000000", "#ff5ef7"]),
    "ide": ("Code Editor", "A VS Code workspace: about.md, skills.json, projects.tsx", ide, ["#1e1e1e", "#007acc", "#dcdcaa"]),
    "retro_os": ("Retro OS 95", "Draggable-looking windows, a Start button and pixel fonts", retro_os, ["#008080", "#c0c0c0", "#000080"]),
    "bento": ("Bento Grid", "Apple-keynote bento boxes with big numbers", bento, ["#f2f0eb", "#151515", "#ff5b2e"]),
    "newspaper": ("Front Page", "A broadsheet newspaper with you as the headline", newspaper, ["#f4efe3", "#111111", "#bbbbbb"]),
    "neon_city": ("Neon City", "Cyberpunk grid, flickering pink neon", neon_city, ["#09001a", "#ff00e0", "#00f0ff"]),
    "rpg_sheet": ("RPG Character Sheet", "Class, level, stat bars, quests and legendary loot", rpg_sheet, ["#2b2138", "#e0b84a", "#7ee787"]),
    "playlist": ("Career Playlist", "Projects as top tracks, jobs as albums", playlist, ["#121212", "#1db954", "#282828"]),
    "chat": ("Chat Interview", "A messaging thread where a recruiter interviews you", chat, ["#efeae2", "#075e54", "#d9fdd3"]),
    "blueprint": ("Blueprint", "Engineering drawing with dimension lines and a title block", blueprint, ["#0d3b66", "#e8f1ff", "#ffe08a"]),
    "periodic": ("Periodic Table", "Every skill becomes a chemical element", periodic, ["#101418", "#ff6b6b", "#4d96ff"]),
    "metro": ("Metro Map", "Your career as a subway line, stop by stop", metro, ["#fafafa", "#e4002b", "#1b1b1b"]),
    "receipt": ("The Receipt", "A printed till receipt. Total value: priceless", receipt, ["#fffef8", "#333333", "#d9d4c7"]),
    "boarding_pass": ("Boarding Pass", "Career Class ticket from where you started to their team", boarding_pass, ["#0f172a", "#2563eb", "#ffffff"]),
    "polaroid": ("Polaroid Wall", "Projects pinned as tilted instant photos", polaroid, ["#c9b79c", "#ffffff", "#fda085"]),
    "comic": ("Comic Book", "POW! Halftone panels and speech-bubble headings", comic, ["#fef3c7", "#ef4444", "#3b82f6"]),
    "space": ("Deep Space", "Starfield drift with a ringed planet", space, ["#000000", "#8be9fd", "#ffb86c"]),
    "kanban": ("Kanban Board", "Done, Shipped, Up next: joining your team", kanban, ["#f4f5f7", "#0052cc", "#00875a"]),
    "museum": ("Museum Gallery", "Projects hung in gilded frames, a retrospective", museum, ["#f5f1ea", "#2b2620", "#8d7f66"]),
    "split_sticky": ("Split Sticky", "Classic dev portfolio: sticky intro, scrolling story", split_sticky, ["#0c0a09", "#fb923c", "#e7e5e4"]),
    "magazine": ("Magazine Cover", "Your name as the masthead of a glossy cover", magazine, ["#e11d48", "#ffffff", "#0a0a0a"]),
    "minimal_swiss": ("Swiss Minimal", "Huge type, strict grid, one red accent", minimal_swiss, ["#ffffff", "#111111", "#e30613"]),
    "holo_card": ("Holo ID Card", "An iridescent holographic ID that shimmers", holo_card, ["#0a0a0f", "#ff6ec7", "#7873f5"]),
    "zen": ("Zen Garden", "Calm paper, an ensō brush circle and lots of air", zen, ["#f7f3ec", "#2f2a24", "#a0522d"]),
}
DEFAULT = "aurora_glass"


def render(template_id: str, d: dict) -> str:
    fn = TEMPLATES.get(template_id, TEMPLATES[DEFAULT])[2]
    return fn(d)

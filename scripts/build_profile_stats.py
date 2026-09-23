#!/usr/bin/env python3
"""Build the live SVGs on Janhavi's GitHub profile.

Runs daily in GitHub Actions. Reads the public contribution calendar and repo
languages, then writes:
  dist/dashboard.svg  - an EV instrument cluster for GitHub activity
  dist/ride.svg       - a scooter that rides along the contribution grid
Standard library only.
"""
import datetime as dt
import json
import math
import os
import re
import urllib.request

USER = os.environ.get("GH_USER", "janhaviwararkar")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "dist")

BG, SURF, SURF2, RULE = "#0B111A", "#111925", "#172131", "#243044"
INK, MUTED, AMBER, BLUE, GREEN = "#E6EAF1", "#93A0B5", "#F0B03E", "#63A0FF", "#2FB36B"
SANS = "'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, 'Liberation Mono', monospace"
RM = "@media (prefers-reduced-motion: reduce){ *{animation:none !important} }"
LEVEL = ["#161E2B", "#5A4318", "#8C6A22", "#C98F2A", "#F0B03E"]
LANG_COLORS = [AMBER, BLUE, GREEN, "#E5484D", "#B07CFF", "#5CC8C8", MUTED]


def get(url, api=False):
    req = urllib.request.Request(url, headers={"User-Agent": "profile-stats"})
    if api:
        req.add_header("Accept", "application/vnd.github+json")
        if TOKEN:
            req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


# ------------------------------------------------------------------ data
def calendar():
    html = get(f"https://github.com/users/{USER}/contributions")
    cells = {}
    for m in re.finditer(r'<td[^>]*?data-date="([\d-]+)"[^>]*?id="contribution-day-component-(\d+)-(\d+)"[^>]*?data-level="(\d)"', html):
        date, row, col, lvl = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4))
        cells[f"contribution-day-component-{row}-{col}"] = {"date": date, "row": row, "col": col, "level": lvl, "count": 0}
    for m in re.finditer(r'for="(contribution-day-component-\d+-\d+)"[^>]*>\s*(\d+|No) contribution', html):
        if m.group(1) in cells and m.group(2) != "No":
            cells[m.group(1)]["count"] = int(m.group(2))
    total = re.search(r'([\d,]+)\s+contributions?\s+in the last year', html)
    total = int(total.group(1).replace(",", "")) if total else sum(c["count"] for c in cells.values())
    days = sorted(cells.values(), key=lambda c: c["date"])
    return days, total


def streaks(days):
    active = [d["count"] > 0 or d["level"] > 0 for d in days]
    longest = run = 0
    for a in active:
        run = run + 1 if a else 0
        longest = max(longest, run)
    cur, i = 0, len(active) - 1
    if i >= 0 and not active[i]:
        i -= 1  # today not done yet: count from yesterday
    while i >= 0 and active[i]:
        cur += 1
        i -= 1
    last30 = sum(active[-30:])
    return cur, longest, sum(active), last30


def languages():
    try:
        repos = json.loads(get(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner", api=True))
    except Exception:
        return 0, []
    totals = {}
    for r in repos:
        if r.get("fork"):
            continue
        try:
            langs = json.loads(get(r["languages_url"], api=True))
        except Exception:
            langs = {}
        for k, v in langs.items():
            totals[k] = totals.get(k, 0) + v
    s = sum(totals.values()) or 1
    top = sorted(totals.items(), key=lambda kv: -kv[1])[:6]
    return len([r for r in repos if not r.get("fork")]), [(k, v / s) for k, v in top]


# ------------------------------------------------------------------ dashboard
def nice_max(v):
    for m in (50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000):
        if v <= m * 0.9:
            return m
    return int(math.ceil(v / 1000.0) * 1000)


def dashboard(total, cur, longest, active, last30, repos, langs):
    W, H = 1000, 320
    # speedometer
    cx, cy, r = 170, 172, 104
    mx = nice_max(total)
    a0, a1 = -225, 45  # degrees, 270 deg sweep
    def pt(a, rr):
        t = math.radians(a)
        return cx + rr * math.cos(t), cy + rr * math.sin(t)
    ticks = ""
    for i in range(11):
        a = a0 + (a1 - a0) * i / 10
        x0, y0 = pt(a, r - (14 if i % 5 == 0 else 8))
        x1, y1 = pt(a, r)
        ticks += f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="{MUTED if i % 5 else INK}" stroke-width="{2.4 if i % 5 == 0 else 1.4}"/>'
        if i % 5 == 0:
            lx, ly = pt(a, r - 30)
            ticks += f'<text x="{lx:.1f}" y="{ly + 4:.1f}" text-anchor="middle" class="tick">{int(mx * i / 10)}</text>'
    frac = min(1.0, total / mx)
    ang = a0 + (a1 - a0) * frac
    sx, sy = pt(a0, r + 12)
    ex, ey = pt(a1, r + 12)
    arc_bg = f'M{sx:.1f},{sy:.1f} A{r + 12},{r + 12} 0 1 1 {ex:.1f},{ey:.1f}'
    arc_len = 2 * math.pi * (r + 12) * 0.75
    # needle rotates around (cx,cy); base drawn pointing right (0deg)
    needle = f'<g class="needle" style="--a:{ang:.1f}deg"><path d="M{cx - 14},{cy} L{cx + r - 18},{cy - 2} L{cx + r - 18},{cy + 2} Z" fill="{AMBER}"/></g>'

    # readouts
    rows = [("CURRENT STREAK", f"{cur}", "days"), ("LONGEST STREAK", f"{longest}", "days"),
            ("ACTIVE DAYS", f"{active}", "last 12 months"), ("PUBLIC REPOS", f"{repos}", "owned")]
    ro = ""
    for i, (k, v, u) in enumerate(rows):
        x = 360 + (i % 2) * 175
        y = 86 + (i // 2) * 92
        ro += (f'<g class="fade" style="animation-delay:{0.2 + i * 0.15:.2f}s">'
               f'<text x="{x}" y="{y}" class="k">{k}</text>'
               f'<text x="{x}" y="{y + 42}" class="v">{v}</text>'
               f'<text x="{x + 8 + 22 * len(v)}" y="{y + 42}" class="u">{u}</text></g>')

    # battery = active days in the last 30
    pct = round(100 * last30 / 30)
    segs = ""
    bx, by = 740, 94
    lit = round(10 * last30 / 30)
    for i in range(10):
        on = i < lit
        segs += (f'<rect x="{bx + 10 + i * 20}" y="{by + 10}" width="15" height="54" rx="3" '
                 f'fill="{GREEN if on else SURF2}" class="{"seg" if on else ""}" style="animation-delay:{0.5 + i * 0.12:.2f}s"/>')
    battery = (f'<text x="{bx}" y="{by - 12}" class="k">30-DAY CHARGE</text>'
               f'<rect x="{bx}" y="{by}" width="212" height="74" rx="10" fill="none" stroke="{INK}" stroke-width="2.5"/>'
               f'<rect x="{bx + 212}" y="{by + 24}" width="10" height="26" rx="3" fill="{INK}"/>'
               f'{segs}<text x="{bx}" y="{by + 112}" class="v" style="font-size:30px">{pct}%</text>'
               f'<text x="{bx + 18 + 17 * len(str(pct))}" y="{by + 112}" class="u">{last30} of 30 days with commits</text>')

    # languages strip
    lx, ly, lw = 360, 262, 600
    strip, legend, x = "", "", lx
    for i, (name, share) in enumerate(langs):
        w = max(2, lw * share)
        col = LANG_COLORS[i % len(LANG_COLORS)]
        strip += f'<rect x="{x:.1f}" y="{ly}" width="{w:.1f}" height="10" fill="{col}"/>'
        legend += f'<circle cx="{lx + i * 100 + 5}" cy="{ly + 30}" r="4.5" fill="{col}"/><text x="{lx + i * 100 + 15}" y="{ly + 34}" class="leg">{name} {share * 100:.0f}%</text>'
        x += w
    if not langs:
        legend = f'<text x="{lx}" y="{ly + 34}" class="leg">languages appear here as code is pushed</text>'
    today = dt.date.today().strftime("%d %b %Y")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<style>
.k{{font-family:{MONO};font-size:11px;letter-spacing:1.8px;fill:{MUTED}}}
.v{{font-family:{SANS};font-weight:800;font-size:40px;fill:{INK}}}
.u{{font-family:{MONO};font-size:11px;fill:{MUTED}}}
.tick{{font-family:{MONO};font-size:10px;fill:{MUTED}}}
.big{{font-family:{SANS};font-weight:800;font-size:34px;fill:{INK}}}
.leg{{font-family:{MONO};font-size:11px;fill:{INK}}}
.foot{{font-family:{MONO};font-size:10px;fill:{MUTED}}}
.needle{{transform-origin:{cx}px {cy}px;animation:sweep 2.4s cubic-bezier(.2,.8,.2,1) forwards, idle 3s ease-in-out 2.4s infinite alternate;transform:rotate(-225deg)}}
@keyframes sweep{{from{{transform:rotate(-225deg)}}to{{transform:rotate(var(--a))}}}}
@keyframes idle{{from{{transform:rotate(var(--a))}}to{{transform:rotate(calc(var(--a) - 2.5deg))}}}}
.arc{{stroke-dasharray:{arc_len:.1f};stroke-dashoffset:{arc_len:.1f};animation:arc 2.4s cubic-bezier(.2,.8,.2,1) forwards}}
@keyframes arc{{to{{stroke-dashoffset:{arc_len * (1 - frac):.1f}}}}}
.seg{{opacity:.15;animation:seg .4s ease-out forwards, glow 2.6s ease-in-out 2s infinite alternate}}
@keyframes seg{{to{{opacity:1}}}} @keyframes glow{{from{{opacity:1}}to{{opacity:.55}}}}
.fade{{opacity:0;animation:fade .7s ease-out forwards}} @keyframes fade{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
{RM}
</style>
<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>
<text x="24" y="30" class="k" style="fill:{AMBER}">ACTIVITY CLUSTER · updated {today}</text>
<path d="{arc_bg}" fill="none" stroke="{SURF2}" stroke-width="8" stroke-linecap="round"/>
<path d="{arc_bg}" fill="none" stroke="{AMBER}" stroke-width="8" stroke-linecap="round" class="arc"/>
{ticks}
{needle}
<circle cx="{cx}" cy="{cy}" r="11" fill="{SURF2}" stroke="{AMBER}" stroke-width="3"/>
<text x="{cx}" y="{cy + 58}" text-anchor="middle" class="big">{total}</text>
<text x="{cx}" y="{cy + 90}" text-anchor="middle" class="u">contributions</text>
<text x="{cx}" y="{cy + 104}" text-anchor="middle" class="u">last 12 months</text>
<line x1="330" y1="62" x2="330" y2="{H - 24}" stroke="{RULE}"/>
{ro}
<line x1="715" y1="62" x2="715" y2="225" stroke="{RULE}"/>
{battery}
<text x="{lx}" y="{ly - 10}" class="k">LANGUAGES IN MY REPOS</text>
<rect x="{lx}" y="{ly}" width="{lw}" height="10" rx="5" fill="{SURF2}"/>
<clipPath id="ls"><rect x="{lx}" y="{ly}" width="{lw}" height="10" rx="5"/></clipPath>
<g clip-path="url(#ls)">{strip}</g>
{legend}
</svg>'''


# ------------------------------------------------------------------ ride
def ride(days, total):
    cols = max(d["col"] for d in days) + 1 if days else 53
    cell, gap = 11, 3
    ox, oy = 24, 48
    gw = cols * (cell + gap)
    W = ox * 2 + gw
    track = oy + 7 * (cell + gap) + 30
    H = track + 30
    T = 12.0  # seconds per lap
    travel = gw + 120
    rects = ""
    for d in days:
        x = ox + d["col"] * (cell + gap)
        y = oy + d["row"] * (cell + gap)
        # the moment the scooter's nose reaches this column
        t = T * (x - ox + 60) / travel
        cls = f"c{d['level']}"
        rects += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2.5" class="{cls}" style="animation-delay:{t - T:.2f}s"><title>{d["date"]}: {d["count"]}</title></rect>'
    scooter = f'''<g class="ride">
  <g transform="translate(0,{track - 26})">
    <circle cx="12" cy="20" r="7" fill="none" stroke="{INK}" stroke-width="2.4"/>
    <circle cx="50" cy="20" r="7" fill="none" stroke="{INK}" stroke-width="2.4"/>
    <g class="spin"><path d="M12,14v12M6,20h12" stroke="{MUTED}" stroke-width="1.2"/></g>
    <g class="spin2"><path d="M50,14v12M44,20h12" stroke="{MUTED}" stroke-width="1.2"/></g>
    <path d="M12,20 L20,10 L40,10 L50,20 M40,10 L46,-6 L52,-6" fill="none" stroke="{MUTED}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
    <rect x="8" y="4" width="22" height="5" rx="2.5" fill="{INK}"/>
    <rect x="22" y="12" width="16" height="6" rx="1.5" fill="{SURF2}" stroke="{AMBER}" stroke-width="1"/>
    <rect x="23.5" y="13.5" width="13" height="3" rx="1" fill="{GREEN}" class="charge"/>
    <circle cx="55" cy="-3" r="2.2" fill="{AMBER}"/>
    <path d="M58,-3 L78,-9 L78,3 Z" fill="{AMBER}" opacity=".18"/>
  </g>
</g>'''
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<style>
.k{{font-family:{MONO};font-size:11px;letter-spacing:1.6px;fill:{MUTED}}}
{"".join(f".c{i}{{fill:{LEVEL[i]};animation:lit{i} {T}s linear infinite}}" for i in range(5))}
@keyframes lit0{{0%{{fill:{LEVEL[0]}}}2%{{fill:#2A3B55}}10%,100%{{fill:{LEVEL[0]}}}}}
{"".join(f"@keyframes lit{i}{{0%{{fill:#FFE3A3}}6%{{fill:{LEVEL[i]}}}70%{{fill:{LEVEL[i]};opacity:1}}90%,100%{{opacity:.35}}}}" for i in range(1, 5))}
.ride{{animation:ride {T}s linear infinite}}
@keyframes ride{{from{{transform:translateX({ox - 70}px)}}to{{transform:translateX({ox - 70 + travel}px)}}}}
.spin{{transform-origin:12px 20px;animation:spin .5s linear infinite}} .spin2{{transform-origin:50px 20px;animation:spin .5s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.charge{{transform-origin:23.5px 15px;animation:charge {T}s linear infinite}}
@keyframes charge{{from{{transform:scaleX(.1)}}to{{transform:scaleX(1)}}}}
{RM}
</style>
<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>
<text x="{ox}" y="30" class="k" style="fill:{AMBER}">COMMIT RIDE</text>
<text x="{W - ox}" y="30" text-anchor="end" class="k">{total} contributions · last 12 months</text>
{rects}
<line x1="{ox}" y1="{track}" x2="{W - ox}" y2="{track}" stroke="{RULE}" stroke-width="2" stroke-dasharray="6 6"/>
{scooter}
</svg>'''


def main():
    os.makedirs(OUT, exist_ok=True)
    days, total = calendar()
    cur, longest, active, last30 = streaks(days)
    repos, langs = languages()
    with open(os.path.join(OUT, "dashboard.svg"), "w", encoding="utf-8") as f:
        f.write(dashboard(total, cur, longest, active, last30, repos, langs))
    with open(os.path.join(OUT, "ride.svg"), "w", encoding="utf-8") as f:
        f.write(ride(days, total))
    print(f"days={len(days)} total={total} streak={cur}/{longest} active={active} last30={last30} repos={repos} langs={langs}")


if __name__ == "__main__":
    main()

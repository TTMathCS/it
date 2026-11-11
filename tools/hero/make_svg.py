#!/usr/bin/env python3
"""Writes docs/images/it-hero.svg (1600x900): the banner on the home page.

A data pipeline in the medallion style the Databricks course teaches: data from Mars (rovers, orbiters, a weather
station) lands raw in Bronze, is cleaned in Silver and made ready in Gold; under it a SQL query on a small table of
Mars rovers and the rows it really returns. The rows are computed here with SQLite, so the picture shows a correct
answer, not a drawing of one. Landing years: NASA and CNSA mission pages (Sojourner 1997, Spirit and Opportunity 2004,
Curiosity 2012, Perseverance and Zhurong 2021).

Render with: node tools/hero/render.js
"""
import pathlib, sqlite3

W, H = 1600, 900
SANS = "IBM Plex Sans, sans-serif"
MONO = "IBM Plex Mono, monospace"
INK = "#f4e6d4"
RUST = "#eea66f"
o = []
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
o.append('<defs>'
         '<radialGradient id="sky" cx="60%" cy="30%" r="85%"><stop offset="0" stop-color="#3a1c12"/>'
         '<stop offset="0.6" stop-color="#1a0d09"/><stop offset="1" stop-color="#07080c"/></radialGradient>'
         '<marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
         f'<path d="M0,0 L10,5 L0,10 z" fill="{RUST}"/></marker>'
         '</defs>')
o.append(f'<rect width="{W}" height="{H}" fill="url(#sky)"/>')
for x in range(40, W, 80):   # a faint grid, like squared paper
    o.append(f'<line x1="{x}" y1="0" x2="{x}" y2="{H}" stroke="{INK}" stroke-opacity="0.045"/>')
for y in range(30, H, 80):
    o.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{INK}" stroke-opacity="0.045"/>')


def text(x, y, s, size=22, fill=INK, font=SANS, weight=400, anchor="start", op=1):
    o.append(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
             f'text-anchor="{anchor}" fill="{fill}" fill-opacity="{op}">{s}</text>')


def arrow(x1, y1, x2, y2):
    o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{RUST}" stroke-width="4" '
             f'stroke-linecap="round" marker-end="url(#arr)"/>')


# --- the pipeline -------------------------------------------------------------------------------------------------
text(110, 92, "MEDALLION PIPELINE", 22, RUST, MONO, 600)
sources = ["Rover telemetry", "Orbiter images", "Weather station"]
for i, s in enumerate(sources):
    y = 130 + i * 86
    o.append(f'<rect x="110" y="{y}" width="250" height="62" rx="12" fill="#140b08" fill-opacity="0.9" '
             f'stroke="{INK}" stroke-opacity="0.35" stroke-width="2"/>')
    text(235, y + 39, s, 22, INK, SANS, 600, "middle")
    arrow(366, y + 31, 476, 215 + i * 40)


def cylinder(cx, top, w, h, colour, title, sub):
    rx, ry = w / 2, 22
    o.append(f'<path d="M{cx - rx},{top} v{h} a{rx},{ry} 0 0 0 {w},0 v{-h}" fill="{colour}" fill-opacity="0.22" '
             f'stroke="{colour}" stroke-width="3"/>')
    o.append(f'<ellipse cx="{cx}" cy="{top}" rx="{rx}" ry="{ry}" fill="{colour}" fill-opacity="0.45" '
             f'stroke="{colour}" stroke-width="3"/>')
    for k in (1, 2):   # the bands of a database drum
        yy = top + h * k / 3
        o.append(f'<path d="M{cx - rx},{yy} a{rx},{ry} 0 0 0 {w},0" fill="none" stroke="{colour}" '
                 f'stroke-opacity="0.5" stroke-width="2"/>')
    text(cx, top + h + 70, title, 30, colour, SANS, 700, "middle")
    text(cx, top + h + 102, sub, 20, INK, MONO, 400, "middle", 0.75)


layers = [(590, "#c98a55", "Bronze", "raw, as it came"),
          (930, "#d4d7dc", "Silver", "cleaned, joined"),
          (1270, "#f0c35a", "Gold", "ready to query")]
for i, (cx, col, t, sub) in enumerate(layers):
    cylinder(cx, 180, 200, 150, col, t, sub)
    if i:
        arrow(layers[i - 1][0] + 112, 255, cx - 118, 255)

# --- the query and its real result --------------------------------------------------------------------------------
rows = [("Sojourner", "NASA", 1997), ("Spirit", "NASA", 2004), ("Opportunity", "NASA", 2004),
        ("Curiosity", "NASA", 2012), ("Perseverance", "NASA", 2021), ("Zhurong", "CNSA", 2021)]
db = sqlite3.connect(":memory:")
db.execute("CREATE TABLE rovers (name TEXT, agency TEXT, landed INTEGER)")
db.executemany("INSERT INTO rovers VALUES (?, ?, ?)", rows)
QUERY = "SELECT name, agency, landed FROM rovers WHERE landed >= 2004 ORDER BY landed, name"
result = db.execute(QUERY).fetchall()

o.append(f'<rect x="110" y="540" width="700" height="300" rx="16" fill="#120a07" fill-opacity="0.92" '
         f'stroke="{INK}" stroke-opacity="0.25" stroke-width="2"/>')
for i, c in enumerate(("#e2685a", "#e8b84a", "#7cbf6a")):
    o.append(f'<circle cx="{142 + i * 26}" cy="570" r="7" fill="{c}" fill-opacity="0.8"/>')
text(790, 576, "gold.rovers", 18, INK, MONO, 400, "end", 0.5)
KW = "#9cc9ea"
lines = [[("SELECT ", KW), ("name, agency, landed", INK)],
         [("FROM ", KW), ("rovers", INK)],
         [("WHERE ", KW), ("landed &gt;= ", INK), ("2004", RUST)],
         [("ORDER BY ", KW), ("landed, name;", INK)]]
for i, parts in enumerate(lines):
    spans = "".join(f'<tspan fill="{c}">{s}</tspan>' for s, c in parts)
    o.append(f'<text x="150" y="{640 + i * 50}" font-family="{MONO}" font-size="30" xml:space="preserve">{spans}</text>')

tx, ty, cw = 880, 540, [230, 140, 120]
tw = sum(cw) + 60
rh = 44
o.append(f'<rect x="{tx}" y="{ty}" width="{tw}" height="{rh * (len(result) + 1) + 24}" rx="16" fill="#120a07" '
         f'fill-opacity="0.92" stroke="{INK}" stroke-opacity="0.25" stroke-width="2"/>')
heads = ["name", "agency", "landed"]
x = tx + 30
for j, hd in enumerate(heads):
    text(x, ty + 42, hd, 22, RUST, MONO, 600)
    x += cw[j]
o.append(f'<line x1="{tx + 20}" y1="{ty + 56}" x2="{tx + tw - 20}" y2="{ty + 56}" stroke="{RUST}" stroke-opacity="0.6" stroke-width="2"/>')
for i, r in enumerate(result):
    x = tx + 30
    y = ty + 56 + rh * (i + 1) - 10
    for j, v in enumerate(r):
        text(x, y, v, 22, INK, MONO, 400, "start", 0.9)
        x += cw[j]
text(tx + 4, ty + rh * (len(result) + 1) + 60, f"{len(result)} rows", 20, INK, MONO, 400, "start", 0.55)

o.append("</svg>")
out = pathlib.Path(__file__).resolve().parents[2] / "docs" / "images" / "it-hero.svg"
out.write_text("\n".join(o) + "\n")
print(out, result)

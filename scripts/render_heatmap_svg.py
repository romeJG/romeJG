#!/usr/bin/env python3
"""
Render data/contributions.json (produced by fetch_contributions.py) as an
ALL-TIME GitHub-style contribution heatmap SVG: one classic 53-week x 7-day
calendar block PER YEAR, stacked oldest -> newest, each row of boxes revealed
once with a diagonal line-after-line slide-down (CSS keyframes, plays on load
then freezes -- no looping "glow"), a Less->More legend, and a real stats
footer covering the whole account history.

Run by .github/workflows/update-profile-art.yml after fetch_contributions.py.
"""
import datetime
import json
import os

HERE = os.path.dirname(__file__)
IN_PATH = os.path.join(HERE, "..", "data", "contributions.json")
OUT_PATH = os.path.join(HERE, "..", "contrib-heatmap.svg")

# GitHub-ish green ramp: empty -> brightest. Level 5 is a brighter neon top end.
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

CELL = 12
GAP = 3
STEP = CELL + GAP
PAD = 22
LEFT_LABEL_W = 34
TOP_LABEL_H = 20
TITLEBAR_H = 30
YEAR_GAP = 12  # vertical space between one year's block and the next

BG = "#0a0e14"
BG2 = "#0d1420"
FRAME = "#1f6feb"
MUTED = "#7d8590"
TEXT = "#e6edf3"
ACCENT = "#22d3ee"
GREEN = "#39d353"
GOLD = "#f2cc60"

# reveal timing (one-shot)
COL_T = 0.014   # per-column delay contribution (left -> right sweep)
ROW_T = 0.035   # per-row delay contribution (top -> bottom cascade)
BLOCK_T = 0.12  # extra stagger per year block (oldest starts first)
CELL_DUR = 0.42


def level_for(count):
    if count == 0:
        return 0
    if count <= 5:
        return 1
    if count <= 15:
        return 2
    if count <= 30:
        return 3
    if count <= 50:
        return 4
    return 5


def build_grid(days):
    """53-ish-column x 7-row grid for a single year's worth of days."""
    first = datetime.date.fromisoformat(days[0]["date"])
    lead_pad = (first.weekday() + 1) % 7  # sunday=0
    grid = []
    col = [None] * lead_pad
    for d in days:
        date = datetime.date.fromisoformat(d["date"])
        weekday = (date.weekday() + 1) % 7
        while len(col) < weekday:
            col.append(None)
        col.append((d["date"], d["count"], level_for(d["count"])))
        if len(col) == 7:
            grid.append(col)
            col = []
    if col:
        while len(col) < 7:
            col.append(None)
        grid.append(col)
    return grid


def year_blocks(days):
    by_year = {}
    for d in days:
        by_year.setdefault(d["date"][:4], []).append(d)
    return [(int(y), build_grid(by_year[y])) for y in sorted(by_year)]


def render(data):
    blocks = year_blocks(data["days"])
    max_cols = max(len(grid) for _, grid in blocks)
    art_w = max_cols * STEP

    canvas_w = PAD + LEFT_LABEL_W + art_w + PAD
    blocks_h = sum(TOP_LABEL_H + 7 * STEP for _, _ in blocks) + YEAR_GAP * (len(blocks) - 1)
    stats_h = 88
    canvas_h = TITLEBAR_H + blocks_h + stats_h + PAD

    css = f"""
@keyframes cell {{
  0%   {{ opacity: 0; transform: translateY(-6px); }}
  100% {{ opacity: 1; transform: translateY(0); }}
}}
.c {{ opacity: 0; animation: cell {CELL_DUR:.2f}s cubic-bezier(.2,.8,.2,1) both; }}
""".strip()

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" height="{canvas_h}" '
        f'viewBox="0 0 {canvas_w} {canvas_h}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        f'<style>{css}</style>',
        '<defs>'
        f'<linearGradient id="hbg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient>'
        '</defs>',
        f'<rect width="{canvas_w}" height="{canvas_h}" rx="12" fill="url(#hbg)"/>',
        f'<rect x="0.5" y="0.5" width="{canvas_w-1}" height="{canvas_h-1}" rx="12" '
        f'fill="none" stroke="{FRAME}" stroke-width="1" stroke-opacity="0.55"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{canvas_w}" y2="{TITLEBAR_H}" stroke="{FRAME}" stroke-opacity="0.35"/>',
    ]
    for i, dotcol in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dotcol}"/>')
    parts.append(f'<text x="{canvas_w/2}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" font-size="12" '
                 f'text-anchor="middle">romeJG@github: ~/contributions --graph --all-time</text>')

    grid_left = PAD + LEFT_LABEL_W
    block_top = TITLEBAR_H

    for bi, (year, grid) in enumerate(blocks):
        grid_top = block_top + TOP_LABEL_H

        seen_months = set()
        for ci, column in enumerate(grid):
            for cell in column:
                if cell is None:
                    continue
                date = datetime.date.fromisoformat(cell[0])
                if date.month not in seen_months and date.day <= 7:
                    seen_months.add(date.month)
                    x = grid_left + ci * STEP
                    parts.append(f'<text x="{x}" y="{block_top + 14}" fill="{MUTED}" font-size="10">'
                                 f'{date.strftime("%b")}</text>')
                break

        parts.append(f'<text x="{PAD}" y="{block_top + 14}" fill="{ACCENT}" font-size="11" '
                     f'font-weight="700">{year}</text>')

        for wi, wname in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
            y = grid_top + wi * STEP + CELL * 0.78
            parts.append(f'<text x="{PAD + LEFT_LABEL_W - 4}" y="{y:.1f}" fill="{MUTED}" '
                         f'font-size="9" text-anchor="end">{wname}</text>')

        for ci, column in enumerate(grid):
            gx = grid_left + ci * STEP
            for ri, cell in enumerate(column):
                if cell is None:
                    continue
                date_s, count, lvl = cell
                gy = grid_top + ri * STEP
                delay = bi * BLOCK_T + ci * COL_T + ri * ROW_T
                plural = "s" if count != 1 else ""
                parts.append(
                    f'<rect class="c" x="{gx}" y="{gy}" width="{CELL}" height="{CELL}" rx="2.5" '
                    f'fill="{PALETTE[lvl]}" style="animation-delay:{delay:.3f}s">'
                    f'<title>{date_s}: {count} contribution{plural}</title></rect>'
                )

        block_top = grid_top + 7 * STEP + YEAR_GAP

    art_bottom = block_top - YEAR_GAP

    # legend: Less [][][][][] More (bottom-right of the last grid)
    leg_y = art_bottom + 6
    leg_x = canvas_w - PAD - (len(PALETTE) * (CELL - 1) + 70)
    parts.append(f'<text x="{leg_x}" y="{leg_y + CELL*0.8:.1f}" fill="{MUTED}" font-size="10" text-anchor="end">Less</text>')
    lx = leg_x + 8
    for lvl, color in enumerate(PALETTE):
        parts.append(f'<rect x="{lx}" y="{leg_y}" width="{CELL-1}" height="{CELL-1}" rx="2.2" fill="{color}"/>')
        lx += CELL
    parts.append(f'<text x="{lx + 4}" y="{leg_y + CELL*0.8:.1f}" fill="{MUTED}" font-size="10">More</text>')

    sep_y = leg_y + CELL + 14
    parts.append(f'<line x1="0" y1="{sep_y}" x2="{canvas_w}" y2="{sep_y}" stroke="{FRAME}" stroke-opacity="0.25"/>')

    cs = data["current_streak"]["length"]
    ls = data["longest_streak"]["length"]
    total = data["total_contributions"]
    best = data["best_day"]
    rng = data["range"]

    ly = sep_y + 24
    # left column: big highlighted numbers; right column: context in muted
    parts.append(f'<text x="{PAD}" y="{ly}" font-size="13" fill="{GREEN}">'
                 f'<tspan font-weight="700">{total:,}</tspan>'
                 f'<tspan fill="{MUTED}"> contributions all time</tspan></text>')
    parts.append(f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{MUTED}" text-anchor="end">'
                 f'{rng["start"]} &#8594; {rng["end"]}</text>')
    ly += 24
    parts.append(f'<text x="{PAD}" y="{ly}" font-size="13" fill="{MUTED}">current streak '
                 f'<tspan fill="{ACCENT}" font-weight="700">{cs} days</tspan>'
                 f'<tspan fill="{MUTED}">   &#183;   longest </tspan>'
                 f'<tspan fill="{ACCENT}" font-weight="700">{ls} days</tspan></text>')
    parts.append(f'<text x="{canvas_w - PAD}" y="{ly}" font-size="12" fill="{MUTED}" text-anchor="end">'
                 f'best day <tspan fill="{GOLD}" font-weight="700">{best["count"]}</tspan> on {best["date"]}</text>')

    parts.append("</svg>")
    return "".join(parts)


if __name__ == "__main__":
    data = json.load(open(IN_PATH))
    svg = render(data)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"wrote {OUT_PATH} ({len(svg)} bytes)")

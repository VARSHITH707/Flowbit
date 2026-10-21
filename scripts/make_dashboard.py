"""Build docs/DASHBOARD.md and its charts (docs/img/*.svg) from docs/metrics.json. Re-run after adding numbers.

  .\\.venv\\Scripts\\python.exe scripts\\make_dashboard.py

Charts are static SVG (GitHub cannot run scripts), so every chart has a data table next to it, every bar is
labelled with its value, and each bar has a hover tooltip (<title>). Light and dark mode follow the viewer.
"""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, IMG = ROOT / "docs", ROOT / "docs" / "img"
STYLE = """<style>
.s{fill:#fcfcfb}.t1{fill:#0b0b0b}.t2{fill:#52514e}.g{stroke:#e4e3df}.a{fill:#2a78d6}.b{fill:#85837d}
@media (prefers-color-scheme:dark){.s{fill:#1a1a19}.t1{fill:#f0efec}.t2{fill:#c3c2b7}.g{stroke:#3a3936}.a{fill:#3987e5}.b{fill:#6b6a66}}
text{font-family:Segoe UI,Helvetica,Arial,sans-serif}
</style>"""
W, LABEL_W, ROW, BAR, PAD = 760, 230, 34, 14, 18


def _bar(x: float, y: float, w: float, cls: str, tip: str) -> str:
    """Horizontal bar: square at the baseline, 4 px rounded data end."""
    w = max(w, 2)
    r = min(4, w / 2, BAR / 2)
    d = (f"M{x:.1f},{y:.1f} h{w - r:.1f} a{r},{r} 0 0 1 {r},{r} v{BAR - 2 * r:.1f} "
         f"a{r},{r} 0 0 1 -{r},{r} h-{w - r:.1f} z")
    return f'<path class="{cls}" d="{d}"><title>{escape(tip)}</title></path>'


def _fmt(v: float, unit: str) -> str:
    return (f"{v:g}" if isinstance(v, (int, float)) else str(v)) + unit


def hbar_svg(title: str, rows: list[dict], unit: str, legend: list[tuple[str, str]] | None = None) -> str:
    """rows: {label, bars: [(value, class, tooltip)]}. One shared axis starting at 0."""
    vmax = max(v for r in rows for v, _, _ in r["bars"]) or 1
    plot_w = W - LABEL_W - PAD - 90
    per = max(len(r["bars"]) for r in rows)
    row_h = ROW + (per - 1) * (BAR + 4)
    top = 44 + (22 if legend else 0)
    h = top + len(rows) * row_h + PAD
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" '
           f'aria-label="{escape(title)}">', STYLE, f'<rect class="s" width="{W}" height="{h}" rx="10"/>',
           f'<text class="t1" x="{PAD}" y="28" font-size="15" font-weight="600">{escape(title)}</text>']
    if legend:
        x = PAD
        for name, cls in legend:
            out.append(f'<rect class="{cls}" x="{x}" y="42" width="12" height="12" rx="2"/>'
                       f'<text class="t2" x="{x + 18}" y="52" font-size="12">{escape(name)}</text>')
            x += 26 + 7 * len(name)
    x0 = LABEL_W
    out.append(f'<line class="g" x1="{x0}" y1="{top - 6}" x2="{x0}" y2="{h - PAD + 4}" stroke-width="1"/>')
    for i, r in enumerate(rows):
        y = top + i * row_h
        out.append(f'<text class="t1" x="{x0 - 10}" y="{y + BAR - 2}" font-size="13" text-anchor="end">'
                   f'{escape(r["label"])}</text>')
        for j, (v, cls, tip) in enumerate(r["bars"]):
            by = y + j * (BAR + 4)
            bw = plot_w * v / vmax
            out.append(_bar(x0, by, bw, cls, tip))
            out.append(f'<text class="t2" x="{x0 + max(bw, 2) + 6}" y="{by + BAR - 3}" font-size="12">'
                       f'{escape(_fmt(v, unit))}</text>')
    out.append("</svg>")
    return "\n".join(out)


def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def build(m: dict) -> str:
    IMG.mkdir(parents=True, exist_ok=True)
    md = ["# VoiceType dashboard", "",
          f"Measured on one machine: {m['machine']}. Every number comes from a script or document in this repo "
          "(source column). Regenerate with `scripts/make_dashboard.py` after editing `docs/metrics.json`.", "",
          "## At a glance", "", table(["", "What it means", "Source"],
                                      [[f"**{t['value']}**", t["label"], f"`{t['source']}`"] for t in m["tiles"]]), ""]

    s = m["speedups"]
    svg = hbar_svg(s["title"], [{"label": r["label"], "bars": [
        (r["before"], "b", f"before: {r['before']} s"), (r["after"], "a", f"after: {r['after']} s ({r['version']})")]}
        for r in s["rows"]], s["unit"], legend=[("before the fix", "b"), ("after the fix", "a")])
    (IMG / "speedups.svg").write_text(svg, encoding="utf-8")
    md += ["## How much faster it got", "", "![Speed fixes](img/speedups.svg)", "",
           table(["Step", "Before", "After", "Faster by", "Version"],
                 [[r["label"], f"{r['before']} s", f"{r['after']} s", f"{r['before'] / r['after']:.1f}x", r["version"]]
                  for r in s["rows"]]), ""]

    for key, img, heading in (("speech_models", "speech_models.svg", "Which speech model, and why"),
                              ("cleanup_models", "cleanup_models.svg", "Which cleanup AI, and why")):
        c = m[key]
        svg = hbar_svg(c["title"], [{"label": r["label"] + ("  (chosen)" if r["label"] == c["chosen"] else ""),
                                     "bars": [(r["value"], "a" if r["label"] == c["chosen"] else "b",
                                               f"{r['label']}: {_fmt(r['value'], c['unit'])}, {r['extra']}")]}
                                    for r in c["rows"]], c["unit"])
        (IMG / img).write_text(svg, encoding="utf-8")
        md += [f"## {heading}", "", f"![{heading}](img/{img})", "",
               table(["Model", "Result", "Also", "Chosen"],
                     [[r["label"], _fmt(r["value"], c["unit"]), r["extra"], "yes" if r["label"] == c["chosen"] else ""]
                      for r in c["rows"]]), ""]

    v = m["versions"]
    svg = hbar_svg("Automated tests passing, by version (higher is better)",
                   [{"label": f"{x['version']}  ({x['date']})", "bars": [(x["tests"], "a", f"{x['version']}: {x['tests']} tests")]}
                    for x in v], "")
    (IMG / "tests.svg").write_text(svg, encoding="utf-8")
    md += ["## Versions", "", "![Tests by version](img/tests.svg)", "",
           table(["Version", "Date", "Tests", "What changed"], [[x["version"], x["date"], x["tests"], x["what"]] for x in v]),
           "", "Full details: [VERSION_HISTORY.md](../VERSION_HISTORY.md).", ""]

    f = m.get("finetune")
    md += ["## Fine-tuning on your own voice", ""]
    if f and not any(r["base"] or r["tuned"] for r in f["rows"]):  # all zero: a chart of empty bars says nothing
        md += [table(["Test set", "Clips", "Base", "Fine-tuned"],
                     [[r["label"], r["clips"], f"{r['base']}%", f"{r['tuned']}%"] for r in f["rows"]]), "", f["note"], ""]
    elif f:
        svg = hbar_svg("Word error rate: base model vs fine-tuned (%, lower is better)",
                       [{"label": r["label"], "bars": [(r["base"], "b", f"base: {r['base']}%"),
                                                       (r["tuned"], "a", f"fine-tuned: {r['tuned']}%")]}
                        for r in f["rows"]], "%", legend=[("large-v3-turbo (base)", "b"), ("fine-tuned", "a")])
        (IMG / "finetune.svg").write_text(svg, encoding="utf-8")
        md += ["![Fine-tuning result](img/finetune.svg)", "",
               table(["Test set", "Clips", "Base", "Fine-tuned"],
                     [[r["label"], r["clips"], f"{r['base']}%", f"{r['tuned']}%"] for r in f["rows"]]), "",
               f["note"], ""]
    else:
        md += ["Not measured yet: waiting for voice recordings (`scripts/record_voice.py`).", ""]
    return "\n".join(md)


if __name__ == "__main__":
    metrics = json.loads((DOCS / "metrics.json").read_text(encoding="utf-8"))
    (DOCS / "DASHBOARD.md").write_text(build(metrics), encoding="utf-8")
    print("wrote docs/DASHBOARD.md and", ", ".join(p.name for p in sorted(IMG.glob("*.svg"))))

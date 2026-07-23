"""Self-updating slide deck of the interactive HTML visualizations.

Two ways to use it:

  1. Auto-add from a viz script (one line at the end, after writing the html):
         import slideshow
         slideshow.add(OUT_HTML, "Margin heatmap",
                       "Actual points vs the closing prop line, with minutes.")
     Re-running that script refreshes its slide and rebuilds the deck.

  2. Seed/rebuild the curated narrative deck:
         python3 slideshow.py

The manifest (slideshow/slides.json) is the source of truth and preserves the
ORDER in which slides were added -> that order IS the progression. Open the deck
at slideshow/index.html (arrow keys / buttons / dropdown to navigate).
"""
import os
import json
import html
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DECK_DIR = ROOT / "slideshow"
MANIFEST = DECK_DIR / "slides.json"


def _load():
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return []


def _save(slides):
    DECK_DIR.mkdir(exist_ok=True)
    MANIFEST.write_text(json.dumps(slides, indent=2))


def add(html_path, title=None, caption="", rebuild=True):
    """Register (or refresh) a slide for `html_path`; keeps insertion order."""
    p = Path(html_path).resolve()
    rel = os.path.relpath(p, ROOT)
    slides = _load()
    entry = {"path": rel,
             "title": title or p.stem.replace("_", " ").title(),
             "caption": caption}
    for i, s in enumerate(slides):
        if s["path"] == rel:
            slides[i] = {**s, **entry}      # refresh in place, keep position
            break
    else:
        slides.append(entry)                # new slide -> end of the progression
    _save(slides)
    if rebuild:
        build(slides)
    return rel


def build(slides=None):
    """Write slideshow/index.html from the manifest."""
    slides = slides if slides is not None else _load()
    DECK_DIR.mkdir(exist_ok=True)
    data = []
    for s in slides:
        target = ROOT / s["path"]
        src = urllib.parse.quote(os.path.relpath(target, DECK_DIR))
        data.append({"src": src, "title": s["title"], "caption": s.get("caption", ""),
                     "file": Path(s["path"]).name, "exists": target.exists()})
    (DECK_DIR / "index.html").write_text(_TEMPLATE.replace("__SLIDES__", json.dumps(data)))
    print(f"built {DECK_DIR / 'index.html'} ({len(data)} slides)")


# curated narrative order for `python3 slideshow.py` (canonical copy of each viz)
_NARRATIVE = [
    ("OddsAPI/Key Figures/unders_scatter.html", "1 · Every Under closing price",
     "Starting point: one dot per player-game Under; flagged players highlighted."),
    ("OddsAPI/Key Figures/movement_scatter.html", "2 · Line move vs price move",
     "Normalized line movement against price movement — the market-behavior features."),
    ("OddsAPI/Key Figures/line_vs_ratio_scatter.html", "3 · Line move vs O/U ratio",
     "Line movement against the closing Over/Under price ratio."),
    ("OddsAPI/Key Figures/ou_ratio_startclose_scatter.html", "4 · Opening vs closing O/U ratio",
     "How the Over/Under price ratio shifted from open to close."),
    ("OddsAPI/Key Figures/scores_heatmap.html", "5 · Suspicion score (z1 + z2)",
     "Equal-weighted z-scores: line-move + price-move-on-pinned-lines."),
    ("OddsAPI/Key Figures/scores_heatmap_z1only.html", "6 · Suspicion score (z1 only)",
     "Line-movement signal alone — the component that survives significance testing."),
    ("nba_api/margin_heatmap.html", "7 · Outcome: points vs line + minutes",
     "Did the player actually go under? Margin (line − points) with minutes played."),
    ("nba_api/outcome_score_heatmap.html", "8 · Outcome suspicion (margin + low minutes)",
     "Big under AND few minutes → Porter's games rise to the top."),
    ("nba_api/advanced_heatmap.html", "9 · Advanced box-score metrics",
     "netRating, TS%, usage%, PIE, pace — residual + minutes for context."),
    ("nba_api/per36_heatmap.html", "10 · Per-36 normalized",
     "Counting stats normalized by minutes; rate metrics shown alongside."),
]


def seed_narrative():
    for path, title, caption in _NARRATIVE:
        if (ROOT / path).exists():
            add(path, title, caption, rebuild=False)
        else:
            print(f"  (skip, not found: {path})")
    build()


_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Game Integrity — visualization progression</title>
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; font-family: -apple-system, system-ui, sans-serif; }
  body { display: flex; flex-direction: column; background: #0f172a; color: #e2e8f0; }
  header { display: flex; align-items: center; gap: 1rem; padding: .6rem 1rem;
           background: #1e293b; border-bottom: 1px solid #334155; }
  header h1 { font-size: 1rem; margin: 0; font-weight: 600; color: #f8fafc; }
  #counter { font-variant-numeric: tabular-nums; color: #94a3b8; font-size: .85rem; }
  select { margin-left: auto; max-width: 42vw; padding: .35rem .5rem; border-radius: 6px;
           background: #0f172a; color: #e2e8f0; border: 1px solid #475569; font-size: .85rem; }
  #cap { padding: .5rem 1rem; background: #1e293b; border-bottom: 1px solid #334155;
         font-size: .9rem; color: #cbd5e1; min-height: 1.2rem; }
  #cap b { color: #f8fafc; }
  main { flex: 1; position: relative; background: #fff; }
  iframe { width: 100%; height: 100%; border: 0; background: #fff; }
  .miss { display: flex; height: 100%; align-items: center; justify-content: center;
          color: #64748b; font-size: 1rem; }
  footer { display: flex; align-items: center; gap: .5rem; padding: .5rem 1rem;
           background: #1e293b; border-top: 1px solid #334155; }
  button { padding: .4rem .9rem; border-radius: 6px; border: 1px solid #475569;
           background: #334155; color: #e2e8f0; cursor: pointer; font-size: .85rem; }
  button:hover { background: #475569; }
  button:disabled { opacity: .4; cursor: default; }
  #dots { display: flex; gap: 6px; margin: 0 auto; flex-wrap: wrap; }
  .dot { width: 9px; height: 9px; border-radius: 50%; background: #475569; cursor: pointer; }
  .dot.on { background: #38bdf8; }
  a.open { color: #38bdf8; text-decoration: none; font-size: .8rem; }
</style></head>
<body>
  <header>
    <h1>Game Integrity — visualization progression</h1>
    <span id="counter"></span>
    <select id="jump"></select>
  </header>
  <div id="cap"></div>
  <main id="stage"></main>
  <footer>
    <button id="prev">&larr; Prev</button>
    <div id="dots"></div>
    <button id="next">Next &rarr;</button>
    <a class="open" id="openTab" target="_blank" rel="noopener">open in new tab &nearr;</a>
  </footer>
<script>
  const SLIDES = __SLIDES__;
  let i = 0;
  const stage = document.getElementById('stage'), cap = document.getElementById('cap'),
        counter = document.getElementById('counter'), jump = document.getElementById('jump'),
        dots = document.getElementById('dots'), openTab = document.getElementById('openTab');
  SLIDES.forEach((s, k) => {
    const o = document.createElement('option'); o.value = k; o.textContent = (k+1) + '. ' + s.title;
    jump.appendChild(o);
    const d = document.createElement('div'); d.className = 'dot'; d.title = s.title;
    d.onclick = () => show(k); dots.appendChild(d);
  });
  function show(k) {
    i = (k + SLIDES.length) % SLIDES.length;
    const s = SLIDES[i];
    stage.innerHTML = s.exists
      ? '<iframe src="' + s.src + '"></iframe>'
      : '<div class="miss">missing file: ' + s.file + ' — regenerate it, then rebuild the deck</div>';
    cap.innerHTML = '<b>' + s.title + '</b> — ' + (s.caption || '');
    counter.textContent = (i+1) + ' / ' + SLIDES.length;
    jump.value = i;
    openTab.href = s.src;
    [...dots.children].forEach((d, k2) => d.classList.toggle('on', k2 === i));
    document.getElementById('prev').disabled = SLIDES.length < 2;
    document.getElementById('next').disabled = SLIDES.length < 2;
  }
  document.getElementById('prev').onclick = () => show(i - 1);
  document.getElementById('next').onclick = () => show(i + 1);
  jump.onchange = e => show(+e.target.value);
  document.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') show(i - 1);
    if (e.key === 'ArrowRight') show(i + 1);
  });
  if (SLIDES.length) show(0);
  else stage.innerHTML = '<div class="miss">No slides yet. Run: python3 slideshow.py</div>';
</script>
</body></html>
"""


if __name__ == "__main__":
    seed_narrative()

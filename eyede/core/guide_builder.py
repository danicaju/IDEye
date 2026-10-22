"""Self-contained HTML renderer for IDEye's interactive Game Manual."""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List

_ACCENTS = ("#fb7185", "#22d3ee", "#fbbf24", "#a78bfa", "#34d399")


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _icon(kind: str) -> str:
    """Small inline SVG illustrations; no external files or fonts."""
    common = 'viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"'
    icons = {
        "face": '<circle cx="48" cy="48" r="30"/><path d="M34 41h.1M62 41h.1M35 62c8 6 18 6 26 0"/>',
        "calibration": '<path d="M16 16h18M16 16v18M80 16H62M80 16v18M16 80h18M16 80V62M80 80H62M80 80V62"/><circle cx="48" cy="48" r="8"/><circle cx="48" cy="48" r="2" fill="currentColor"/>',
        "mouth": '<circle cx="48" cy="48" r="30"/><path d="M32 40h.1M64 40h.1"/><ellipse cx="48" cy="62" rx="13" ry="8" fill="currentColor" fill-opacity=".18"/>',
        "rest": '<path d="M18 48c7-10 16-15 30-15s23 5 30 15c-7 10-16 15-30 15S25 58 18 48Z"/><circle cx="48" cy="48" r="7"/><path d="M70 22h12M76 16v12"/>',
        "jaw": '<path d="M24 34c0 24 10 34 24 34s24-10 24-34"/><path d="M38 58h20M48 68v8M40 76h16"/>',
        "wink": '<circle cx="48" cy="48" r="30"/><path d="M32 40h.1M60 40c3 3 6 3 9 0M38 62c7 4 13 4 20 0"/>',
        "wink-left": '<circle cx="48" cy="48" r="30"/><path d="M27 40c3 3 6 3 9 0M64 40h.1M38 62c7 4 13 4 20 0"/>',
        "code": '<path d="m36 30-18 18 18 18M60 30l18 18-18 18M54 24 42 72"/>',
        "writing": '<path d="M24 72l6-20 34-34 14 14-34 34-20 6Z"/><path d="m58 24 14 14M24 72l14-6"/>',
        "terminal": '<rect x="14" y="20" width="68" height="56" rx="8"/><path d="m30 40 10 8-10 8M50 60h16"/>',
        "data": '<ellipse cx="48" cy="26" rx="28" ry="10"/><path d="M20 26v22c0 6 12 10 28 10s28-4 28-10V26M20 48v22c0 6 12 10 28 10s28-4 28-10V48"/>',
        "navigation": '<circle cx="48" cy="48" r="30"/><path d="m60 30-10 28-16 8 10-28 16-8Z"/>',
        "mouse": '<rect x="30" y="14" width="36" height="68" rx="18"/><path d="M48 18v20M30 38h36"/>',
        "gamepad": '<path d="M24 38h48c10 0 14 10 12 20l-3 12c-2 8-8 10-14 4L56 64H40l-11 10c-6 6-12 4-14-4L12 58c-2-10 2-20 12-20Z"/><path d="M30 52h12M36 46v12M62 50h.1M70 58h.1"/>',
        "cursor": '<path d="m30 18 42 32-20 4-8 20-14-56Z"/>',
        "click": '<circle cx="48" cy="48" r="24"/><circle cx="48" cy="48" r="7" fill="currentColor"/><path d="M48 12v12M48 72v12M12 48h12M72 48h12"/>',
        "release": '<rect x="18" y="34" width="60" height="32" rx="8"/><path d="M30 50h36M38 42v16M58 42v16"/>',
        "grid": '<rect x="16" y="16" width="64" height="64" rx="6"/><path d="M37 16v64M59 16v64M16 37h64M16 59h64"/>',
        "monitor": '<rect x="14" y="18" width="68" height="44" rx="6"/><path d="M34 78h28M48 62v16"/>',
        "clipboard": '<rect x="24" y="18" width="48" height="64" rx="8"/><path d="M36 18h24v10H36zM36 42h24M36 54h24M36 66h16"/>',
        "telemetry": '<path d="M16 72V48M32 72V36M48 72V54M64 72V28M80 72V42"/><path d="M14 80h70"/>',
        "eye": '<path d="M16 48c8-12 18-18 32-18s24 6 32 18c-8 12-18 18-32 18S24 60 16 48Z"/><circle cx="48" cy="48" r="8"/>',
    }
    body = icons.get(kind, icons["grid"])
    return f'<svg class="icon" {common} aria-hidden="true">{body}</svg>'


def _cards(cards: List[Dict[str, Any]], accent: str) -> str:
    blocks = []
    for card in cards:
        blocks.append(
            f'''
            <article class="card" style="--accent:{accent}">
              <div class="badge">{_esc(card.get("badge", "★"))}</div>
              <div class="card-icon">{_icon(str(card.get("icon", "grid")))}</div>
              <h3>{_esc(card.get("title", ""))}</h3>
              <p>{_esc(card.get("text", ""))}</p>
              <span class="chip">{_esc(card.get("chip", ""))}</span>
            </article>'''
        )
    return "\n".join(blocks)


def _gesture_strip(gestures: List[Dict[str, Any]], thresholds: Dict[str, Any]) -> str:
    cards = []
    for gesture in gestures:
        cards.append(
            f'''
            <article class="gesture-card">
              <div class="gesture-icon">{_icon(str(gesture.get("icon", "face")))}</div>
              <div>
                <h4>{_esc(gesture.get("name", ""))}</h4>
                <strong>{_esc(gesture.get("action", ""))}</strong>
                <p>{_esc(gesture.get("description", ""))}</p>
              </div>
            </article>'''
        )
    return f'''
    <div class="threshold-row">
      <span>MAR <b>{_esc(thresholds.get("mar_threshold", 0.45))}</b></span>
      <span>EAR cierre <b>{_esc(thresholds.get("ear_close", 0.16))}</b></span>
      <span>Guiño <b>{_esc(thresholds.get("wink_ms", 150))}–{_esc(thresholds.get("wink_max_ms", 450))} ms</b></span>
    </div>
    <div class="gesture-strip">{"".join(cards)}</div>'''


def _shortcut_grid(shortcuts: List[Dict[str, Any]]) -> str:
    cards = []
    for shortcut in shortcuts:
        cards.append(
            f'''
            <div class="shortcut">
              <kbd>{_esc(shortcut.get("key", ""))}</kbd>
              <div><b>{_esc(shortcut.get("label", ""))}</b><span>{_esc(shortcut.get("description", ""))}</span></div>
            </div>'''
        )
    return f'<div class="shortcut-grid">{"".join(cards)}</div>'


def _simulator(simulator: Dict[str, Any]) -> str:
    modes = []
    for index, (mode_id, mode) in enumerate(simulator.items()):
        active = " active" if index == 0 else ""
        modes.append(
            f'<button class="sim-mode{active}" data-mode="{_esc(mode_id)}">{_esc(mode.get("name", mode_id))}</button>'
        )
    return f'''
    <section class="simulator" aria-label="Simulador interactivo 3x3">
      <div class="sim-heading">
        <div><span class="mini-kicker">SIMULADOR EN VIVO</span><h3>Prueba las 9 casillas</h3></div>
        <div class="sim-modes">{"".join(modes)}</div>
      </div>
      <div class="sim-body">
        <div id="simGrid" class="sim-grid" aria-live="polite"></div>
        <aside id="simInfo" class="sim-info">
          <span class="mini-kicker">CASILLA</span>
          <h4>Elige una celda</h4>
          <p>Haz clic en cualquier casilla para ver qué hace en el modo activo.</p>
        </aside>
      </div>
    </section>'''


def build_interactive_guide_html(catalog: Dict[str, Any]) -> str:
    """Renders the complete offline guide from a catalog dictionary."""
    pages = catalog.get("pages", [])
    simulator = catalog.get("simulator", {})
    data_json = json.dumps(catalog, ensure_ascii=False).replace("</", "<\\/")

    tabs = []
    sections = []
    for index, page in enumerate(pages):
        page_id = str(page.get("id", f"page-{index + 1}"))
        active = " active" if index == 0 else ""
        accent = str(page.get("ribbon", _ACCENTS[index % len(_ACCENTS)]))
        tabs.append(
            f'<button class="tab{active}" data-page-target="{index}">{_esc(page.get("tab", f"Página {index + 1}"))}</button>'
        )
        extra = ""
        if page_id == "gestures":
            extra = _gesture_strip(catalog.get("gestures", []), catalog.get("gesture_thresholds", {}))
        if page_id == "modes":
            extra = _simulator(simulator) + _shortcut_grid(catalog.get("shortcuts", []))
        if page_id == "custom":
            extra = _shortcut_grid(catalog.get("shortcuts", []))
        sections.append(
            f'''
            <section class="page{active}" data-page="{index}" id="{_esc(page_id)}">
              <div class="ribbon" style="--ribbon:{accent}">
                <span class="kicker">{_esc(page.get("kicker", ""))}</span>
                <h2>{_esc(page.get("title", ""))}</h2>
              </div>
              <p class="intro">{_esc(page.get("intro", ""))}</p>
              <div class="card-grid">{_cards(page.get("cards", []), accent)}</div>
              {extra}
            </section>'''
        )

    pager = "\n".join(
        f'<button class="page-dot{" active" if index == 0 else ""}" data-page-target="{index}">{index + 1}</button>'
        for index in range(len(pages))
    )
    return f'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#070b16">
<title>IDEye — Manual Interactivo</title>
<style>
:root {{
  --bg:#070b16; --paper:#0f172a; --paper-2:#111c33; --line:#26364f;
  --text:#e2e8f0; --muted:#94a3b8; --cyan:#22d3ee; --yellow:#fbbf24;
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:smooth; }}
body {{
  margin:0; color:var(--text); font-family:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  background:
    radial-gradient(900px 500px at 8% 4%, rgba(34,211,238,.14), transparent 65%),
    radial-gradient(800px 500px at 92% 12%, rgba(251,113,133,.12), transparent 62%),
    linear-gradient(145deg,#070b16 0%,#0b1222 55%,#0b1525 100%);
  min-height:100vh;
}}
button {{ font:inherit; cursor:pointer; }}
.app {{ width:min(1240px,calc(100% - 32px)); margin:0 auto; padding:22px 0 40px; }}
.hero {{ display:flex; align-items:flex-end; justify-content:space-between; gap:20px; padding:18px 22px; border:1px solid var(--line); border-radius:22px; background:linear-gradient(135deg,rgba(15,23,42,.96),rgba(17,28,51,.9)); box-shadow:0 18px 60px rgba(0,0,0,.35); }}
.brand {{ display:flex; align-items:center; gap:14px; }}
.logo {{ width:54px; height:54px; display:grid; place-items:center; border-radius:16px; background:linear-gradient(135deg,var(--cyan),#6366f1); color:#06111f; box-shadow:0 0 0 4px rgba(34,211,238,.14); }}
.logo .icon {{ width:32px; height:32px; }}
.brand h1 {{ margin:0; font-size:clamp(20px,3vw,32px); letter-spacing:-.03em; }}
.brand p {{ margin:2px 0 0; color:var(--muted); font-size:13px; }}
.hero-actions {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
.btn {{ border:1px solid rgba(34,211,238,.45); background:rgba(34,211,238,.12); color:#cffafe; border-radius:999px; padding:10px 16px; font-weight:700; box-shadow:3px 3px 0 rgba(0,0,0,.45); }}
.btn:hover {{ background:rgba(34,211,238,.22); transform:translateY(-1px); }}
.tabs {{ display:flex; flex-wrap:wrap; gap:8px; margin:18px 0 12px; }}
.tab {{ border:1px solid var(--line); background:rgba(15,23,42,.86); color:var(--muted); border-radius:999px; padding:9px 13px; font-size:13px; font-weight:700; }}
.tab:hover {{ color:#fff; border-color:#475569; }}
.tab.active {{ color:#06111f; background:var(--cyan); border-color:var(--cyan); box-shadow:3px 3px 0 rgba(0,0,0,.5); }}
.page {{ display:none; animation:pop .28s ease both; }}
.page.active {{ display:block; }}
@keyframes pop {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:none; }} }}
.ribbon {{ display:inline-block; max-width:100%; margin:12px 0 8px 4px; padding:13px 22px 14px; border-radius:12px; background:var(--ribbon); color:#0b1020; transform:rotate(-1.4deg); box-shadow:5px 5px 0 rgba(0,0,0,.6); border:2px solid rgba(255,255,255,.35); }}
.kicker, .mini-kicker {{ display:block; font-size:11px; letter-spacing:.16em; font-weight:900; opacity:.78; }}
.ribbon h2 {{ margin:2px 0 0; font-size:clamp(24px,4.4vw,44px); line-height:1.02; letter-spacing:-.04em; }}
.intro {{ max-width:850px; color:#cbd5e1; font-size:16px; line-height:1.65; margin:16px 0 18px; }}
.card-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(235px,1fr)); gap:14px; }}
.card {{ position:relative; overflow:hidden; min-height:230px; border:1px solid var(--line); border-radius:18px; padding:20px 18px 18px; background:linear-gradient(160deg,var(--paper),var(--paper-2)); box-shadow:0 10px 30px rgba(0,0,0,.22); transition:transform .18s ease,border-color .18s ease; }}
.card:hover {{ transform:translateY(-4px) rotate(.25deg); border-color:var(--accent); }}
.card::after {{ content:""; position:absolute; inset:auto -30px -50px auto; width:120px; height:120px; border-radius:50%; background:var(--accent); opacity:.08; }}
.card-icon {{ color:var(--accent); margin-bottom:8px; }}
.icon {{ width:58px; height:58px; display:block; }}
.badge {{ position:absolute; top:14px; right:14px; min-width:38px; height:38px; padding:0 7px; display:grid; place-items:center; border-radius:50%; background:var(--accent); color:#07101e; font-weight:900; font-size:12px; box-shadow:0 0 0 4px rgba(255,255,255,.06); }}
.card h3 {{ margin:8px 0 8px; font-size:19px; letter-spacing:-.02em; }}
.card p {{ margin:0 0 14px; color:#b6c2d6; font-size:14px; line-height:1.55; }}
.chip {{ display:inline-block; border:1px solid rgba(148,163,184,.3); background:rgba(148,163,184,.1); color:#dbeafe; border-radius:999px; padding:4px 9px; font-size:11px; font-weight:800; }}
.threshold-row {{ display:flex; flex-wrap:wrap; gap:8px; margin:12px 0; }}
.threshold-row span {{ border:1px solid var(--line); background:rgba(15,23,42,.9); border-radius:9px; padding:7px 11px; color:var(--muted); font-size:12px; }}
.threshold-row b {{ color:var(--yellow); }}
.gesture-strip {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; margin-top:12px; }}
.gesture-card {{ display:flex; gap:14px; border:1px solid var(--line); border-radius:16px; padding:14px; background:rgba(15,23,42,.82); }}
.gesture-icon {{ color:var(--cyan); flex:0 0 48px; }}
.gesture-icon .icon {{ width:48px; height:48px; }}
.gesture-card h4 {{ margin:0 0 4px; }}
.gesture-card strong {{ display:block; color:var(--yellow); font-size:12px; }}
.gesture-card p {{ margin:4px 0 0; color:var(--muted); font-size:13px; line-height:1.45; }}
.simulator {{ margin-top:20px; border:1px solid rgba(34,211,238,.35); border-radius:20px; padding:18px; background:rgba(8,15,30,.86); box-shadow:0 0 40px rgba(34,211,238,.08) inset; }}
.sim-heading {{ display:flex; justify-content:space-between; align-items:flex-start; gap:14px; flex-wrap:wrap; }}
.sim-heading h3 {{ margin:2px 0 0; font-size:24px; }}
.sim-modes {{ display:flex; gap:7px; flex-wrap:wrap; }}
.sim-mode {{ border:1px solid var(--line); border-radius:999px; background:#111c33; color:#cbd5e1; padding:7px 11px; font-size:12px; font-weight:800; }}
.sim-mode.active {{ background:var(--yellow); border-color:var(--yellow); color:#1c1200; }}
.sim-body {{ display:grid; grid-template-columns:minmax(0,1.2fr) minmax(220px,.8fr); gap:16px; margin-top:14px; }}
.sim-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }}
.sim-cell {{ min-height:82px; border:1px solid #31435e; border-radius:12px; background:linear-gradient(150deg,#15233b,#0f172a); color:#dbeafe; padding:8px; text-align:left; font-weight:800; font-size:12px; line-height:1.25; box-shadow:2px 2px 0 rgba(0,0,0,.35); }}
.sim-cell:hover, .sim-cell.selected {{ border-color:var(--yellow); background:linear-gradient(150deg,#263651,#15233b); transform:translateY(-2px); }}
.sim-cell small {{ display:block; color:#7dd3fc; font-size:10px; font-weight:600; margin-top:4px; }}
.sim-info {{ border:1px solid var(--line); border-radius:14px; padding:15px; background:#0d1729; min-height:130px; }}
.sim-info h4 {{ margin:3px 0 8px; color:var(--yellow); font-size:20px; }}
.sim-info p {{ margin:0; color:#b6c2d6; line-height:1.55; font-size:14px; }}
.shortcut-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:9px; margin-top:18px; }}
.shortcut {{ display:flex; align-items:center; gap:12px; border:1px solid var(--line); background:rgba(15,23,42,.78); border-radius:12px; padding:10px 12px; }}
kbd {{ flex:0 0 auto; border:1px solid #475569; border-bottom-width:3px; border-radius:7px; background:#1e293b; color:#e0f2fe; padding:5px 7px; font-size:11px; font-weight:900; }}
.shortcut b {{ display:block; font-size:13px; }}
.shortcut span {{ display:block; color:var(--muted); font-size:11px; line-height:1.35; }}
.pager {{ display:flex; justify-content:center; align-items:center; gap:8px; padding:24px 0 8px; }}
.page-dot {{ width:38px; height:38px; border-radius:50%; border:1px solid var(--line); background:#0f172a; color:#cbd5e1; font-weight:900; }}
.page-dot.active {{ background:var(--cyan); border-color:var(--cyan); color:#06111f; box-shadow:3px 3px 0 rgba(0,0,0,.5); }}
.page-label {{ color:var(--muted); font-size:12px; margin-left:8px; }}
@media (max-width:760px) {{
  .hero {{ align-items:flex-start; flex-direction:column; }}
  .sim-body {{ grid-template-columns:1fr; }}
  .ribbon {{ transform:rotate(-.8deg); }}
}}
@media print {{
  @page {{ size:A4 landscape; margin:10mm; }}
  body {{ background:#fff !important; color:#111; }}
  .app {{ width:100%; padding:0; }}
  .hero {{ border:0; box-shadow:none; background:#fff; padding:0 0 8px; }}
  .hero-actions, .tabs, .pager, .sim-modes {{ display:none !important; }}
  .page {{ display:block !important; break-after:page; page-break-after:always; color:#111; }}
  .page:last-of-type {{ break-after:auto; page-break-after:auto; }}
  .ribbon {{ box-shadow:3px 3px 0 #999; border-color:#777; }}
  .intro, .card p, .gesture-card p, .sim-info p, .shortcut span {{ color:#333; }}
  .card, .gesture-card, .simulator, .shortcut {{ background:#fff; border-color:#bbb; box-shadow:none; break-inside:avoid; }}
  .card h3, .card p, .sim-info h4, .shortcut b {{ color:#111; }}
  .sim-cell {{ background:#f4f4f4; color:#111; border-color:#999; box-shadow:none; }}
  .sim-cell small {{ color:#333; }}
  .badge, .chip {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
}}
</style>
</head>
<body>
<div class="app">
  <header class="hero">
    <div class="brand">
      <div class="logo">{_icon("eye")}</div>
      <div><h1>IDEye — Manual Interactivo</h1><p>Game Manual Edition · Vistax L2C Engine</p></div>
    </div>
    <div class="hero-actions">
      <button class="btn" onclick="window.print()">🖨️ Guardar como PDF</button>
    </div>
  </header>
  <nav class="tabs" aria-label="Categorías del manual">{''.join(tabs)}</nav>
  <main>{''.join(sections)}</main>
  <footer class="pager">
    <button class="btn" id="prevPage" aria-label="Página anterior">←</button>
    <div id="pageDots" style="display:flex;gap:8px">{pager}</div>
    <button class="btn" id="nextPage" aria-label="Página siguiente">→</button>
    <span class="page-label" id="pageLabel">Página 1</span>
  </footer>
</div>
<script>
const GUIDE = {data_json};
let currentPage = 0;
let currentMode = Object.keys(GUIDE.simulator || {{}})[0] || "coding";

function showPage(index) {{
  const pages = [...document.querySelectorAll(".page")];
  if (!pages.length) return;
  currentPage = Math.max(0, Math.min(pages.length - 1, index));
  pages.forEach((page, i) => page.classList.toggle("active", i === currentPage));
  document.querySelectorAll(".tab").forEach((tab, i) => tab.classList.toggle("active", i === currentPage));
  document.querySelectorAll(".page-dot").forEach((dot, i) => dot.classList.toggle("active", i === currentPage));
  document.getElementById("pageLabel").textContent = `Página ${{currentPage + 1}}`;
  window.scrollTo({{top: 0, behavior: "smooth"}});
}}

function renderSimulator(modeId) {{
  const mode = (GUIDE.simulator || {{}})[modeId];
  if (!mode) return;
  currentMode = modeId;
  document.querySelectorAll(".sim-mode").forEach(btn => btn.classList.toggle("active", btn.dataset.mode === modeId));
  const grid = document.getElementById("simGrid");
  grid.innerHTML = "";
  mode.cells.forEach((cell, index) => {{
    const button = document.createElement("button");
    button.className = "sim-cell";
    button.innerHTML = `<span>${{cell.label}}</span><small>${{cell.hint}}</small>`;
    button.addEventListener("click", () => {{
      document.querySelectorAll(".sim-cell").forEach(c => c.classList.remove("selected"));
      button.classList.add("selected");
      document.getElementById("simInfo").innerHTML = `<span class="mini-kicker">${{mode.name.toUpperCase()}} · CASILLA ${{index + 1}}</span><h4>${{cell.label}}</h4><p>${{cell.hint}}</p>`;
    }});
    grid.appendChild(button);
  }});
}}

document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => showPage(Number(tab.dataset.pageTarget))));
document.querySelectorAll(".page-dot").forEach(dot => dot.addEventListener("click", () => showPage(Number(dot.dataset.pageTarget))));
document.querySelectorAll(".sim-mode").forEach(btn => btn.addEventListener("click", () => renderSimulator(btn.dataset.mode)));
document.getElementById("prevPage").addEventListener("click", () => showPage(currentPage - 1));
document.getElementById("nextPage").addEventListener("click", () => showPage(currentPage + 1));
window.addEventListener("keydown", event => {{
  if (event.key === "ArrowLeft") showPage(currentPage - 1);
  if (event.key === "ArrowRight") showPage(currentPage + 1);
}});
renderSimulator(currentMode);
</script>
</body>
</html>'''

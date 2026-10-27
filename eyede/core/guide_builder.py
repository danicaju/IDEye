"""Self-contained HTML renderer for IDEye's interactive Game Manual."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any, Dict, List

_ACCENTS = ("#fb7185", "#22d3ee", "#fbbf24", "#a78bfa", "#34d399")


def _app_icon_data_uri() -> str:
    """Returns the official app icon as a self-contained data URI."""
    candidates = (
        Path(__file__).resolve().parent.parent / "assets" / "icons" / "app_icon_256.png",
        Path(__file__).resolve().parent.parent / "assets" / "icons" / "app_icon.png",
        Path(__file__).resolve().parent.parent / "assets" / "icons" / "app_icon_rounded.png",
        Path(__file__).resolve().parent.parent.parent / "eyede.ico",
    )
    for path in candidates:
        try:
            if path.is_file():
                encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                mime = "image/png" if path.suffix.lower() == ".png" else "image/x-icon"
                return f"data:{mime};base64,{encoded}"
        except OSError:
            continue
    return ""


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
        "scroll": '<path d="M32 18v60M32 18l-8 8M32 18l8 8M64 78V18M64 78l-8-8M64 78l8-8"/>',
        "health": '<path d="M48 14v68M14 48h68"/><circle cx="48" cy="48" r="30"/><path d="M33 60c8 8 22 8 30 0"/>',
        "brow": '<circle cx="48" cy="50" r="28"/><path d="M25 35c7-7 16-7 23 0M48 35c7-7 16-7 23 0M33 45h.1M63 45h.1M36 62c8 5 16 5 24 0"/>',
    }
    body = icons.get(kind, icons["grid"])
    return f'<svg class="icon" {common} aria-hidden="true">{body}</svg>'


def _ui_icon(name: str, extra_class: str = "") -> str:
    try:
        from eyede.core.guide_catalog import SVG_ICONS
    except ImportError:  # pragma: no cover
        from guide_catalog import SVG_ICONS  # type: ignore
    inner = SVG_ICONS.get(str(name), SVG_ICONS.get("sparkles", ""))
    classes = "ui-icon" + (f" {extra_class}" if extra_class else "")
    return (
        f'<svg class="{classes}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{inner}</svg>'
    )


def _brand_logo() -> str:
    return (
        '<svg class="brand-icon-svg" viewBox="0 0 64 64" width="100%" height="100%" '
        'preserveAspectRatio="xMidYMid meet" fill="none" stroke="currentColor" '
        'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-label="IDEye">'
        '<path d="M20 9c-5 0-7 2.5-7 7v6c0 3.5-2 5-5 5 3 0 5 1.5 5 5v6c0 4.5 2 7 7 7"/>'
        '<path d="M44 9c5 0 7 2.5 7 7v6c0 3.5 2 5 5 5-3 0-5 1.5-5 5v6c0 4.5-2 7-7 7"/>'
        '<path d="M22 32c4.5-7.5 15.5-7.5 20 0-4.5 7.5-15.5 7.5-20 0Z" fill="currentColor" fill-opacity=".1"/>'
        '<circle cx="32" cy="32" r="5.2" fill="currentColor" fill-opacity=".18"/>'
        '<circle cx="32" cy="32" r="1.8" fill="currentColor" stroke="none"/>'
        '<path d="M32 25.5v2M32 36.5v2M25.5 32h2M36.5 32h2"/>'
        '</svg>'
    )


def _cards(cards: List[Dict[str, Any]], accent: str) -> str:
    blocks = []
    for index, card in enumerate(cards):
        blocks.append(
            f'''
            <article class="card card-{index % 2}" style="--accent:{accent}">
<div class="badge sticker">{_ui_icon("star-badge")}<span>{_esc(card.get("badge", "FIX"))}</span></div>
              <div class="card-icon"><div class="illustration" style="--accent:{accent}">{_icon(str(card.get("icon", "grid")))}</div></div>
              <h3 class="brush-title"><span>{_esc(card.get("title", ""))}</span></h3>
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


THEME_JS = """
const themeButton = document.getElementById("themeToggle");
function applyTheme(theme) {
  const selected = theme === "cyber-glass" ? "cyber-glass" : "nintendo-booklet";
  document.body.dataset.theme = selected;
  if (themeButton) {
    const label = document.getElementById("themeLabel");
    if (label) {
      label.textContent = selected === "nintendo-booklet"
        ? "Estilo: Nintendo Booklet / Cyber-Glass"
        : "Estilo: Cyber-Glass / Nintendo Booklet";
    }
  }
}
function toggleTheme() {
  applyTheme(document.body.dataset.theme === "nintendo-booklet" ? "cyber-glass" : "nintendo-booklet");
}
applyTheme("nintendo-booklet");
"""

NINTENDO_CSS = """
/* ======================================================================
   NINTENDO BOOKLET THEME ? Paper Mario magazine spread
   ====================================================================== */
body[data-theme="nintendo-booklet"] {
  color: #172033;
  background-color: #8ed7ff;
  background-image:
    radial-gradient(circle at 12% 18%, rgba(255,255,255,.75) 0 2.5px, transparent 3.5px),
    radial-gradient(circle at 78% 72%, rgba(255,255,255,.55) 0 2px, transparent 3px),
    radial-gradient(circle at 42% 88%, rgba(255,235,130,.55) 0 3px, transparent 4px),
    linear-gradient(180deg, #9be7ff 0%, #c7f4ff 42%, #b8f5b1 100%);
  background-size: 42px 42px, 58px 58px, 76px 76px, 100% 100%;
}
body[data-theme="nintendo-booklet"] .app {
  width: min(1260px, calc(100% - 30px));
  padding-top: 16px;
}
body[data-theme="nintendo-booklet"] .hero {
  border: 4px solid #111;
  border-radius: 12px;
  background: linear-gradient(135deg, #fffdf7, #fff1b8);
  box-shadow: 8px 8px 0 #b91c2c;
  color: #111;
}
body[data-theme="nintendo-booklet"] .brand h1 {
  color: #b91c2c;
  font-family: "Fredoka", "Nunito", "Comic Neue", "Trebuchet MS", sans-serif;
  font-weight: 900;
  text-shadow: 2px 2px 0 #facc15, 4px 4px 0 #111;
}
body[data-theme="nintendo-booklet"] .brand p { color: #334155; font-weight: 700; }
body[data-theme="nintendo-booklet"] .brand-icon-frame {
  background: #fffdf7;
  color: #111;
  border: 2.5px solid #111;
  border-radius: 14px;
  box-shadow: 4px 4px 0 #111;
}
body[data-theme="nintendo-booklet"] .btn {
  border: 3px solid #111;
  background: #facc15;
  color: #111;
  border-radius: 9px;
  box-shadow: 4px 4px 0 #111;
  font-family: "Fredoka", "Nunito", "Comic Neue", "Trebuchet MS", sans-serif;
  font-weight: 900;
}
body[data-theme="nintendo-booklet"] .btn:hover { background: #fde047; transform: translate(-1px,-1px); }
body[data-theme="nintendo-booklet"] .theme-toggle { background: #22c55e; color: #fff; }
body[data-theme="nintendo-booklet"] .tabs { gap: 10px; margin-top: 22px; }
body[data-theme="nintendo-booklet"] .tab {
  border: 3px solid #111;
  background: #fffdf7;
  color: #111;
  border-radius: 8px;
  box-shadow: 3px 3px 0 #111;
  font-family: "Fredoka", "Nunito", "Comic Neue", "Trebuchet MS", sans-serif;
  font-weight: 900;
  transform: rotate(-.6deg);
}
body[data-theme="nintendo-booklet"] .tab:nth-child(even) { transform: rotate(.7deg); }
body[data-theme="nintendo-booklet"] .tab.active {
  background: #b91c2c;
  color: #facc15;
  border-color: #111;
  box-shadow: 4px 4px 0 #111;
}
body[data-theme="nintendo-booklet"] .page.active {
  position: relative;
  padding: 26px 28px 58px;
  border: 6px solid #fff;
  border-radius: 6px;
  outline: 4px solid #111;
  box-shadow: 10px 10px 0 #111;
  background:
    linear-gradient(90deg, transparent 47.8%, rgba(0,0,0,.14) 49.7%, rgba(255,255,255,.65) 50.2%, rgba(0,0,0,.10) 50.7%, transparent 52.2%),
    radial-gradient(circle at 8% 8%, #fff9d9 0 7%, transparent 8%),
    radial-gradient(circle at 92% 94%, #e8f7c9 0 8%, transparent 9%),
    linear-gradient(90deg, #fffdf7 0 49.6%, #fdf6e8 49.6% 50.4%, #fffdf7 50.4% 100%);
}
body[data-theme="nintendo-booklet"] .page-numbers span {
  position: absolute;
  bottom: 12px;
  color: #fff;
  font-family: "Fredoka", "Nunito", "Trebuchet MS", sans-serif;
  font-size: 22px;
  font-weight: 900;
  -webkit-text-stroke: 2px #000;
  text-shadow: 3px 3px 0 #000;
}
body[data-theme="nintendo-booklet"] .page-numbers span:first-child { left: 20px; }
body[data-theme="nintendo-booklet"] .page-numbers span:last-child { right: 20px; }
body[data-theme="nintendo-booklet"] .ribbon {
  position: relative;
  display: inline-block;
  margin: 6px 0 18px 6px;
  padding: 14px 30px 15px 56px;
  border: 5px solid #facc15;
  border-radius: 4px;
  background: #b91c2c;
  color: #facc15;
  transform: rotate(-1.5deg);
  box-shadow: 6px 6px 0 #111;
  clip-path: polygon(0 4%, 97% 0, 100% 88%, 3% 100%);
}
body[data-theme="nintendo-booklet"] .ribbon::before {
  content: "";
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%) rotate(-12deg);
  color: #facc15;
  font-size: 30px;
  text-shadow: 2px 2px 0 #111;
}
body[data-theme="nintendo-booklet"] .ribbon-star {
  position:absolute; left:14px; top:50%; transform:translateY(-50%) rotate(-8deg);
  color:#facc15; width:32px; height:32px; filter:drop-shadow(2px 2px 0 #111);
}
body[data-theme="nintendo-booklet"] .ribbon-star .ui-icon { width:32px; height:32px; stroke-width:2.2; }
body[data-theme="nintendo-booklet"] .kicker {
  color: #fde68a;
  opacity: 1;
  font-size: 10px;
  letter-spacing: .12em;
  text-shadow: 1px 1px 0 #111;
}
body[data-theme="nintendo-booklet"] .ribbon h2 {
  color: #fbbf24;
  font-family: "Fredoka", "Nunito", "Comic Neue", "Trebuchet MS", sans-serif;
  font-size: clamp(26px, 4.5vw, 48px);
  font-weight: 900;
  -webkit-text-stroke: 2px #111;
  text-shadow: 3px 3px 0 #000;
}
body[data-theme="nintendo-booklet"] .intro {
  color: #1e293b;
  font-family: "Fredoka", "Nunito", "Comic Neue", "Trebuchet MS", sans-serif;
  font-size: 16px;
  font-weight: 700;
  max-width: 900px;
}
body[data-theme="nintendo-booklet"] .card-grid {
  grid-template-columns: repeat(auto-fit, minmax(245px, 1fr));
  gap: 30px 22px;
  padding-top: 16px;
}
body[data-theme="nintendo-booklet"] .card {
  overflow: visible;
  min-height: 290px;
  padding: 68px 16px 17px;
  border: 3px solid #111;
  border-radius: 8px;
  background: #fffdf7;
  box-shadow: 7px 7px 0 rgba(0,0,0,.75);
  transform: rotate(-1.2deg);
  transition: transform .18s cubic-bezier(.2,1.6,.4,1), box-shadow .18s ease;
}
body[data-theme="nintendo-booklet"] .card.card-1 { transform: rotate(1.4deg); }
body[data-theme="nintendo-booklet"] .card:hover {
  transform: rotate(0deg) scale(1.03);
  box-shadow: 10px 10px 0 rgba(0,0,0,.8);
  z-index: 4;
}
body[data-theme="nintendo-booklet"] .card::after {
  display: none;
}
body[data-theme="nintendo-booklet"] .card-icon {
  margin: 0 0 12px;
}
body[data-theme="nintendo-booklet"] .illustration {
  height: 142px;
  display: grid;
  place-items: center;
  color: #fff;
  background:
    radial-gradient(circle at 75% 20%, #fff7a8 0 12%, transparent 13%),
    linear-gradient(145deg, var(--accent), #38bdf8 62%, #22c55e 100%);
  border: 5px solid #fff;
  outline: 3px solid #111;
  box-shadow: 4px 4px 0 #111;
  clip-path: polygon(7% 0, 93% 0, 100% 18%, 100% 100%, 0 100%, 0 18%);
}
body[data-theme="nintendo-booklet"] .illustration .icon {
  width: 86px;
  height: 86px;
  filter: drop-shadow(3px 3px 0 #111);
}
body[data-theme="nintendo-booklet"] .sticker {
  display:inline-flex; flex-direction:column; align-items:center; justify-content:center; gap:0;
  top: -20px;
  right: -12px;
  width: 60px;
  height: 60px;
  min-width: 60px;
  border: 4px solid #fff;
  background: #22c55e;
  color: #fff;
  font-family: "Fredoka", "Nunito", "Trebuchet MS", sans-serif;
  font-size: 13px;
  font-weight: 900;
  text-shadow: 1px 1px 0 #111;
  box-shadow: 4px 4px 0 rgba(0,0,0,.5);
  z-index: 5;
}
body[data-theme="nintendo-booklet"] .card:nth-child(even) .sticker { background: #facc15; color: #111; }
body[data-theme="nintendo-booklet"] .sticker .ui-icon { width:16px; height:16px; stroke-width:2.4; }
body[data-theme="nintendo-booklet"] .sticker span { font-size:10px; line-height:1; }
body[data-theme="nintendo-booklet"] .brush-title {
  position: absolute;
  top: -17px;
  left: 10px;
  right: 10px;
  margin: 0;
  padding: 9px 13px;
  background: #e11d48;
  color: #fff;
  font-family: "Fredoka", "Nunito", "Comic Neue", "Trebuchet MS", sans-serif;
  font-size: 17px;
  font-weight: 900;
  line-height: 1.08;
  text-align: left;
  -webkit-text-stroke: 1.5px #000;
  text-shadow: 2px 3px 0 #000;
  transform: rotate(-2.5deg);
  clip-path: polygon(2% 0%, 98% 4%, 100% 92%, 0% 100%);
  box-shadow: 3px 3px 0 #111;
}
body[data-theme="nintendo-booklet"] .brush-title span { display: block; }
body[data-theme="nintendo-booklet"] .card p {
  color: #1e293b;
  font-family: "Fredoka", "Nunito", "Comic Neue", "Trebuchet MS", sans-serif;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.5;
}
body[data-theme="nintendo-booklet"] .chip {
  border: 2px solid #111;
  background: #fef3c7;
  color: #111;
  border-radius: 5px;
  box-shadow: 2px 2px 0 #111;
  font-family: "Fredoka", "Nunito", "Trebuchet MS", sans-serif;
  font-weight: 900;
}
body[data-theme="nintendo-booklet"] .threshold-row span,
body[data-theme="nintendo-booklet"] .gesture-card,
body[data-theme="nintendo-booklet"] .shortcut,
body[data-theme="nintendo-booklet"] .legal-item {
  border: 3px solid #111;
  background: #fffdf7;
  color: #1e293b;
  box-shadow: 4px 4px 0 #111;
  border-radius: 7px;
}
body[data-theme="nintendo-booklet"] .threshold-row b,
body[data-theme="nintendo-booklet"] .gesture-card strong { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .gesture-card p,
body[data-theme="nintendo-booklet"] .shortcut span,
body[data-theme="nintendo-booklet"] .legal-item p { color: #334155; }
body[data-theme="nintendo-booklet"] .gesture-icon,
body[data-theme="nintendo-booklet"] .legal-icon { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .simulator {
  border: 4px solid #111;
  background: #fffdf7;
  box-shadow: 7px 7px 0 #111;
}
body[data-theme="nintendo-booklet"] .sim-mode {
  border: 2px solid #111;
  background: #fef3c7;
  color: #111;
  border-radius: 6px;
  box-shadow: 2px 2px 0 #111;
  font-weight: 900;
}
body[data-theme="nintendo-booklet"] .sim-mode.active { background: #b91c2c; color: #facc15; }
body[data-theme="nintendo-booklet"] .sim-cell {
  border: 2px solid #111;
  background: #fff7d6;
  color: #111;
  box-shadow: 3px 3px 0 #111;
  font-family: "Fredoka", "Nunito", "Trebuchet MS", sans-serif;
}
body[data-theme="nintendo-booklet"] .sim-cell small { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .sim-info {
  border: 3px solid #111;
  background: #fffdf7;
  box-shadow: 4px 4px 0 #111;
}
body[data-theme="nintendo-booklet"] .sim-info h4 { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .sim-info p { color: #1e293b; }
body[data-theme="nintendo-booklet"] .pager .btn,
body[data-theme="nintendo-booklet"] .page-dot {
  border: 3px solid #111;
  background: #fffdf7;
  color: #111;
  box-shadow: 3px 3px 0 #111;
}
body[data-theme="nintendo-booklet"] .page-dot.active { background: #b91c2c; color: #facc15; }
body[data-theme="nintendo-booklet"] .page-label { color: #111; font-weight: 900; }
body[data-theme="nintendo-booklet"] .legal-footer { border-top: 3px dashed #111; }
body[data-theme="nintendo-booklet"] kbd {
  border: 2px solid #111;
  background: #fef3c7;
  color: #111;
  border-bottom-width: 4px;
  box-shadow: 2px 2px 0 #111;
}
"""

def build_interactive_guide_html(catalog: Dict[str, Any]) -> str:
    """Renders the complete offline guide from a catalog dictionary."""
    pages = catalog.get("pages", [])
    simulator = catalog.get("simulator", {})
    data_json = json.dumps(catalog, ensure_ascii=False).replace("</", "<\\/")
    legal_items = catalog.get("legal", [])
    legal_html = "".join(
        f'<div class="legal-item"><span class="legal-icon">{_ui_icon(item.get("icon", "sparkles"))}</span>'
        f'<div><b>{_esc(item.get("title", ""))}</b><p>{_esc(item.get("text", ""))}</p></div></div>'
        for item in legal_items
    )
    app_icon = _app_icon_data_uri()
    logo_markup = _brand_logo()

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
                <span class="ribbon-star">{_ui_icon("star-badge")}</span>
                <span class="kicker">{_esc(page.get("kicker", ""))}</span>
                <h2>{_esc(page.get("title", ""))}</h2>
              </div>
              <p class="intro">{_esc(page.get("intro", ""))}</p>
              <div class="card-grid">{_cards(page.get("cards", []), accent)}</div>
              {extra}
              <div class="page-numbers"><span>{index * 2 + 11}</span><span>{index * 2 + 12}</span></div>
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
<link rel="icon" href="{app_icon}">
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
.logo-img {{ width:100%; height:100%; object-fit:contain; border-radius:16px; display:block; }}
.brand h1 {{ margin:0; font-size:clamp(20px,3vw,32px); letter-spacing:-.03em; }}
.brand p {{ margin:2px 0 0; color:var(--muted); font-size:13px; }}
.hero-actions {{ display:flex; gap:10px; flex-wrap:wrap; justify-content:flex-end; }}
.ui-icon {{ width:18px; height:18px; flex:0 0 18px; display:inline-block; vertical-align:-3px; }}
.btn, .tab {{ display:inline-flex; align-items:center; justify-content:center; gap:8px; }}
.brand-icon-frame {{ width:56px; height:56px; flex-shrink:0; display:inline-flex; align-items:center; justify-content:center; padding:6px; box-sizing:border-box; overflow:hidden; border-radius:14px; background:linear-gradient(135deg,#22d3ee,#6366f1); color:#06111f; border:1.5px solid rgba(255,255,255,.2); }}
.brand-icon-svg {{ width:100%; height:100%; display:block; }}
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
.legal-footer {{ margin:22px 0 8px; border-top:1px solid var(--line); padding-top:14px; }}
.build-stamp {{ margin:10px 0 0; color:var(--muted); font-size:11px; text-align:right; }}
.legal-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:10px; }}
.legal-item {{ display:flex; gap:10px; border:1px solid #2b3b52; border-radius:12px; padding:10px 12px; background:rgba(15,23,42,.72); }}
.legal-icon {{ color:#b91c2c; display:inline-flex; width:22px; height:22px; flex:0 0 22px; }} .legal-icon .ui-icon {{ width:22px; height:22px; }}
.legal-item b {{ display:block; color:#e2e8f0; font-size:12px; margin-bottom:3px; }}
.legal-item p {{ margin:0; color:var(--muted); font-size:11px; line-height:1.45; }}

{NINTENDO_CSS}
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
  .card, .gesture-card, .simulator, .shortcut, .legal-item {{ background:#fff; border-color:#bbb; box-shadow:none; break-inside:avoid; }}
  .legal-item b, .legal-item p {{ color:#222; }}
  .card h3, .card p, .sim-info h4, .shortcut b {{ color:#111; }}
  .sim-cell {{ background:#f4f4f4; color:#111; border-color:#999; box-shadow:none; }}
  .sim-cell small {{ color:#333; }}
  .badge, .chip {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
}}
</style>
</head>
<body data-theme="nintendo-booklet">
<div class="app">
  <header class="hero">
    <div class="brand">
      <div class="brand-icon-frame">{logo_markup}</div>
      <div><h1>IDEye — Manual Interactivo</h1><p>Game Manual Edition · Vistax L2C Engine</p></div>
    </div>
    <div class="hero-actions">
<button class="btn theme-toggle" id="themeToggle" type="button" onclick="toggleTheme()">{_ui_icon("palette")}<span id="themeLabel">Estilo: Nintendo Booklet / Cyber-Glass</span></button>
<button class="btn" onclick="window.print()">{_ui_icon("printer")}<span>Guardar como PDF</span></button>
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
  <section class="legal-footer" aria-label="Privacidad y avisos legales">
    <div class="legal-grid">{legal_html}</div>
    <p class="build-stamp">{_esc(catalog.get("test_summary", ""))}</p>
  </section>
</div>
<script>
const GUIDE = {data_json};
{THEME_JS}
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

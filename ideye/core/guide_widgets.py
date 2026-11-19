"""HTML component helpers (icons, cards, strips, simulator) for the guide."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_ACCENTS = ("#0284c7", "#10b981", "#8b5cf6", "#f59e0b", "#06b6d4", "#ef4444")


def _app_icon_data_uri() -> str:
    candidates = (
        Path(__file__).resolve().parent.parent / "assets" / "icons" / "app_icon_256.png",
        Path(__file__).resolve().parent.parent / "assets" / "icons" / "app_icon.png",
        Path(__file__).resolve().parent.parent / "assets" / "icons" / "app_icon_rounded.png",
        Path(__file__).resolve().parent.parent.parent / "ideye.ico",
    )
    for cand in candidates:
        if cand.is_file():
            try:
                data = cand.read_bytes()
                mime = "image/x-icon" if cand.suffix.lower() == ".ico" else "image/png"
                b64 = base64.b64encode(data).decode("ascii")
                return f"data:{mime};base64,{b64}"
            except OSError:
                pass
    return ""


def _esc(value: Any) -> str:
    return html.escape(str(value) if value is not None else "", quote=True)


def _icon(kind: str) -> str:
    """Inline SVG illustrations for cards and features; 100% self-contained."""
    common = 'class="icon" viewBox="0 0 96 96" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"'
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
        "trophy": '<path d="M24 36h-6a10 10 0 0 1 0-20h6M72 36h6a10 10 0 0 0 0-20h-6M16 88h64M40 58v10c0 4-3 6-6 6h-2v14h32V74h-2c-3 0-6-2-6-6V58M24 16h48v12a24 24 0 0 1-48 0V16Z"/>',
        "crosshair": '<circle cx="48" cy="48" r="36"/><path d="M48 4v20M48 72v20M4 48h20M72 48h20"/>',
        "zap": '<path d="M52 8 16 54h28l-4 34 36-46H48l4-34Z"/>',
        "cpu": '<rect x="16" y="16" width="64" height="64" rx="8"/><rect x="36" y="36" width="24" height="24"/><path d="M36 4v12M60 4v12M36 80v12M60 80v12M80 36h12M80 60h12M4 36h12M4 60h12"/>',
        "volume-2": '<polygon points="44 20 24 36 8 36 8 60 24 60 44 76 44 20"/><path d="M62 34a20 20 0 0 1 0 28M76 20a40 40 0 0 1 0 56"/>',
        "volume-x": '<polygon points="44 20 24 36 8 36 8 60 24 60 44 76 44 20"/><line x1="88" y1="36" x2="64" y2="60"/><line x1="64" y1="36" x2="88" y2="60"/>',
        "shield-lock": '<path d="M48 12 80 24v20c0 20-13.6 34-32 40-18.4-6-32-20-32-40V24l32-12Z"/><rect x="36" y="44" width="24" height="20" rx="4"/><path d="M40 44V36a8 8 0 0 1 16 0v8"/>',
        "heart-pulse": '<path d="M83.2 23.2a22 22 0 0 0-31.2 0L48 27.6l-4-4.4a22 22 0 0 0-31.2 31.2L48 88l35.2-33.6a22 22 0 0 0 0-31.2Z"/><path d="M14 48h16l6-12 12 24 8-16h22"/>',
        "palette": '<path d="M48 12a36 36 0 1 0 0 72h6a7.2 7.2 0 0 0 0-14.4H48a8 8 0 0 1 0-16h16a20 20 0 0 0 0-40h-16Z"/><circle cx="30" cy="36" r="4"/><circle cx="38" cy="24" r="4"/><circle cx="56" cy="24" r="4"/>',
        "wand": '<path d="m16 80 44-44M48 16l4 8M16 48l8 4M72 40l8 4M56 12l4 8M76 72l4 8"/><path d="m56 24 16 16"/>',
        "grid-3x3": '<rect x="12" y="12" width="72" height="72" rx="8"/><path d="M36 12v72M60 12v72M12 36h72M12 60h72"/>',
        "eye-scan": '<path d="M12 32V20a8 8 0 0 1 8-8h12M60 12h12a8 8 0 0 1 8 8v12M80 64v12a8 8 0 0 1-8 8H60M32 84H20a8 8 0 0 1-8-8V64"/><path d="M24 48c8-12 16-18 24-18s16 6 24 18c-8 12-16 18-24 18s-16-6-24-18Z"/><circle cx="48" cy="48" r="9"/>',
        "sparkles": '<path d="m48 12 6.4 17.6L72 36l-17.6 6.4L48 60l-6.4-17.6L24 36l17.6-6.4L48 12ZM76 56l3.2 8.8L88 68l-8.8 3.2L76 80l-3.2-8.8L64 68l8.8-3.2L76 56ZM20 56l2.4 5.6L28 64l-5.6 2.4L20 72l-2.4-5.6L12 64l5.6-2.4L20 56Z"/>',
    }
    body = icons.get(kind, icons["grid"])
    return f'<svg {common} aria-hidden="true">{body}</svg>'


def _ui_icon(name: str, extra_class: str = "", size: int = 18) -> str:
    try:
        from ideye.core.guide_catalog import SVG_ICONS
    except ImportError:  # pragma: no cover
        from guide_catalog import SVG_ICONS  # type: ignore
    inner = SVG_ICONS.get(str(name), SVG_ICONS.get("sparkles", ""))
    classes = "ui-icon" + (f" {extra_class}" if extra_class else "")
    return (
        f'<svg class="{classes}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{inner}</svg>'
    )


def _brand_logo() -> str:
    """Official Minimalist Monochrome B&W brand logo with 64x64 viewBox."""
    return (
        '<svg class="brand-icon-svg" viewBox="0 0 64 64" width="100%" height="100%" '
        'preserveAspectRatio="xMidYMid meet" fill="none" stroke="currentColor" '
        'stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-label="IDEye">'
        '<path d="M20 9c-5 0-7 2.5-7 7v6c0 3.5-2 5-5 5 3 0 5 1.5 5 5v6c0 4.5 2 7 7 7"/>'
        '<path d="M44 9c5 0 7 2.5 7 7v6c0 3.5 2 5 5 5-3 0-5 1.5-5 5v6c0 4.5-2 7-7 7"/>'
        '<path d="M22 32c4.5-7.5 15.5-7.5 20 0-4.5 7.5-15.5 7.5-20 0Z" fill="currentColor" fill-opacity=".12"/>'
        '<circle cx="32" cy="32" r="5.2" fill="currentColor" fill-opacity=".2"/>'
        '<circle cx="32" cy="32" r="1.8" fill="currentColor" stroke="none"/>'
        '<path d="M32 25.5v2M32 36.5v2M25.5 32h2M36.5 32h2"/>'
        '</svg>'
    )


def _cards(cards: List[Dict[str, Any]], accent: str) -> str:
    """Renders sleek, clean cards without comic clutter or cartoon stickers."""
    blocks = []
    accent_clean = accent.strip()
    rgb = "2, 132, 199"
    if accent_clean.startswith("#") and len(accent_clean) == 7:
        try:
            r = int(accent_clean[1:3], 16)
            g = int(accent_clean[3:5], 16)
            b = int(accent_clean[5:7], 16)
            rgb = f"{r}, {g}, {b}"
        except ValueError:
            pass

    for index, card in enumerate(cards):
        icon_svg = _icon(str(card.get("icon", "grid")))
        badge = _esc(card.get("badge", f"{index + 1:02d}"))
        title = _esc(card.get("title", ""))
        text = _esc(card.get("text", ""))
        chip = _esc(card.get("chip", ""))
        blocks.append(
            f'''
            <article class="card card-{index % 2}" style="--accent:{accent_clean}; --accent-rgb:{rgb};">
              <div class="card-top">
                <div class="card-icon-clean illustration">{icon_svg}</div>
                <span class="badge sticker">{badge}</span>
              </div>
              <h3 class="card-title brush-title"><span>{title}</span></h3>
              <p class="card-desc">{text}</p>
              {f'<div class="card-footer"><span class="chip">{chip}</span></div>' if chip else ''}
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
            <div class="shortcut" data-filter="{_esc(shortcut.get('label', '')).lower()} {_esc(shortcut.get('key', '')).lower()}">
              <kbd>{_esc(shortcut.get("key", ""))}</kbd>
              <div><b>{_esc(shortcut.get("label", ""))}</b><span>{_esc(shortcut.get("description", ""))}</span></div>
            </div>'''
        )
    return f'<div class="shortcut-grid">{"".join(cards)}</div>'


def _simulator(simulator: Dict[str, Any], dojo_challenges: Optional[List[Dict[str, Any]]] = None) -> str:
    if dojo_challenges is None:
        dojo_challenges = []
    modes = []
    for index, (mode_id, mode) in enumerate(simulator.items()):
        active = " active" if index == 0 else ""
        modes.append(
            f'<button class="sim-mode{active}" data-mode="{_esc(mode_id)}">{_esc(mode.get("name", mode_id))}</button>'
        )

    challenge_cards = []
    for ch in dojo_challenges:
        ch_id = _esc(ch.get("id", ""))
        challenge_cards.append(
            f'''<div class="dojo-card" id="dojoCard_{ch_id}" data-challenge="{ch_id}">
  <div class="dojo-card-header">
    <span class="dojo-badge">{_esc(ch.get("badge", "FIX"))}</span>
    <span class="dojo-kicker">{_esc(ch.get("kicker", "DESAFÍO"))}</span>
    <span class="dojo-status pending" id="dojoStatus_{ch_id}">PENDIENTE</span>
  </div>
  <h4>{_esc(ch.get("title", ""))}</h4>
  <p>{_esc(ch.get("desc", ""))}</p>
  <div class="dojo-card-footer">
    <button type="button" class="btn dojo-action-btn" onclick="triggerDojoChallenge('{ch_id}')">
      {_ui_icon("play")}<span>{_esc(ch.get("action_label", "Probar"))}</span>
    </button>
    <span class="dojo-hint">{_esc(ch.get("hint", ""))}</span>
  </div>
</div>'''
        )

    return f'''
    <section class="simulator" id="simSection" aria-label="Simulador interactivo 3x3 y Dojo de Entrenamiento">
      <div class="sim-heading">
        <div><span class="mini-kicker">SIMULADOR EN VIVO · DOJO 60 HZ</span><h3>Centro de Mando Interactivo 3x3</h3></div>
        <div class="sim-modes">{"".join(modes)}</div>
      </div>
      <div class="sim-workspace">
        <div class="sim-left-pane">
          <div id="simGrid" class="sim-grid" aria-live="polite"></div>
          <div class="jaw-meter-container" id="jawMeterContainer">
            <div class="jaw-meter-header">
              <span class="mini-kicker">JAW-METER (APERTURA MAR)</span>
              <span class="jaw-value" id="jawValue">MAR: 0.15 (Reposo)</span>
            </div>
            <div class="jaw-track">
              <div class="jaw-fill" id="jawFill" style="width:15%"></div>
            </div>
          </div>
          <div class="sim-controls">
            <button type="button" class="btn sim-btn" id="soundToggle" onclick="SoundFX.toggle()">
              <span id="soundIcon">{_ui_icon("volume-2")}</span>
              <span id="soundLabel">Audio Activo</span>
            </button>
            <button type="button" class="btn sim-btn" id="btnToggleSniper" onclick="toggleSniperLens()">
              {_ui_icon("crosshair")}<span>Lupa Sniper x3.5</span>
            </button>
            <button type="button" class="btn sim-btn" onclick="triggerGazeScrollSim()">
              {_ui_icon("sliders")}<span>Scroll Ocular</span>
            </button>
            <button type="button" class="btn sim-btn" onclick="triggerAgenticPromptSim()">
              {_ui_icon("wand")}<span>Prompt Agéntico</span>
            </button>
          </div>
          <div class="sim-info" id="simInfo">
            <span class="mini-kicker">ENFOQUE ZERO-DWELL</span>
            <h4>Mueve el ratón sobre una casilla</h4>
            <p>El cursor ocular ilumina la casilla sin activar clics accidentales. Abre la boca o pulsa [Espacio] para confirmar.</p>
          </div>
        </div>
        <div class="sim-right-pane">
          <div class="vscode-pane" id="simEditor">
            <div class="vscode-titlebar">
              <div class="vscode-dots"><span></span><span></span><span></span></div>
              <span class="vscode-filename">main.py — IDEye Live Code Injection</span>
            </div>
            <pre class="vscode-code" id="vscCodeContent"><code><span class="c-comment"># IDEye Look-To-Code Engine — Live Injection Buffer</span>
<span class="c-keyword">def</span> <span class="c-func">on_gaze_confirmed</span>(target_block: <span class="c-type">int</span>):
    <span class="c-keyword">if</span> target_block == <span class="c-num">4</span>:
        toggle_reading_mode()  <span class="c-comment"># Reposo</span>
    <span class="c-keyword">else</span>:
        inject_snippet(target_block)</code></pre>
          </div>
        </div>
      </div>
      <div class="dojo-section" id="dojoContainer">
        <div class="dojo-header">
          <div><span class="mini-kicker">DESAFÍOS DOJO</span><h3>Completa los 6 desafíos de control sin manos</h3></div>
          <button type="button" class="btn" id="dojoJumpBtn" onclick="window.scrollTo({{top: document.getElementById('dojoContainer').offsetTop - 80, behavior: 'smooth'}})">
            {_ui_icon("star-badge")}<span>Retos Dojo</span>
          </button>
        </div>
        <div class="celebration-banner" id="dojoCelebration">
          <div class="celebration-badge">{_ui_icon("trophy")}</div>
          <div class="celebration-text">
            <h4>Completaste los 6 desafíos</h4>
            <p>Has completado todos los desafíos: fijación Zero-Dwell, disparo bucal MAR, inyección de código, scroll inercial, lente Sniper y Agentic Launcher.</p>
          </div>
          <button type="button" class="btn celebration-btn" onclick="resetDojoProgress()">{_ui_icon("sparkles")}<span>Reiniciar Retos</span></button>
        </div>
        <div class="dojo-grid">
          {"".join(challenge_cards)}
        </div>
      </div>
    </section>'''

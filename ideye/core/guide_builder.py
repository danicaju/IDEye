"""Self-contained HTML renderer for IDEye's interactive Game Manual (Studio Redesign).

Renders a sleek, high-performance, responsive manual and interactive playground
matching the official Figma design system (Switch Booklet Light vs Cyber-Glass Dark).
"""

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
          <div><span class="mini-kicker">DESAFÍOS DOJO</span><h3>Supera los 6 Micro-Retos de Control Manos Libres</h3></div>
          <button type="button" class="btn" id="dojoJumpBtn" onclick="window.scrollTo({{top: document.getElementById('dojoContainer').offsetTop - 80, behavior: 'smooth'}})">
            {_ui_icon("star-badge")}<span>Retos Dojo</span>
          </button>
        </div>
        <div class="celebration-banner" id="dojoCelebration">
          <div class="celebration-badge">{_ui_icon("trophy")}</div>
          <div class="celebration-text">
            <h4>¡MAESTRO DE IDEYE DESBLOQUEADO!</h4>
            <p>Has completado todos los desafíos: fijación Zero-Dwell, disparo bucal MAR, inyección de código, scroll inercial, lente Sniper y Agentic Launcher.</p>
          </div>
          <button type="button" class="btn celebration-btn" onclick="resetDojoProgress()">{_ui_icon("sparkles")}<span>Reiniciar Retos</span></button>
        </div>
        <div class="dojo-grid">
          {"".join(challenge_cards)}
        </div>
      </div>
    </section>'''


THEME_JS = """
// Procedural Web Audio API Synthesizer (100% self-contained & offline)
const SoundFX = (() => {
  let ctx = null;
  let enabled = true;
  try {
    const saved = localStorage.getItem("ideye_sound_enabled");
    if (saved !== null) enabled = (saved === "true");
  } catch (e) {}

  function getContext() {
    if (!ctx) {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (AudioCtx) ctx = new AudioCtx();
    }
    if (ctx && ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }
    return ctx;
  }

  const unlock = () => {
    getContext();
    window.removeEventListener("pointerdown", unlock);
    window.removeEventListener("keydown", unlock);
  };
  window.addEventListener("pointerdown", unlock);
  window.addEventListener("keydown", unlock);

  function playTone(freq, type, duration, gainVal, rampTo) {
    if (!enabled) return;
    try {
      const c = getContext();
      if (!c) return;
      const osc = c.createOscillator();
      const gain = c.createGain();
      osc.type = type || "sine";
      osc.frequency.setValueAtTime(freq, c.currentTime);
      if (rampTo) {
        osc.frequency.exponentialRampToValueAtTime(rampTo, c.currentTime + duration);
      }
      gain.gain.setValueAtTime(gainVal || 0.15, c.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + duration);
      osc.connect(gain);
      gain.connect(c.destination);
      osc.start();
      osc.stop(c.currentTime + duration);
    } catch (e) {}
  }

  return {
    click: () => playTone(880, "sine", 0.08, 0.18, 440),
    confirm: () => playTone(587.33, "triangle", 0.12, 0.2, 1174.66),
    mode: () => playTone(440, "sine", 0.15, 0.15, 880),
    whoosh: () => playTone(300, "sawtooth", 0.2, 0.1, 150),
    tick: () => playTone(1200, "sine", 0.03, 0.08),
    toggle: () => {
      enabled = !enabled;
      try { localStorage.setItem("ideye_sound_enabled", String(enabled)); } catch (e) {}
      updateSoundUI();
      if (enabled) playTone(660, "sine", 0.1, 0.15, 880);
    },
    isEnabled: () => enabled
  };
})();

const VOL_ON_SVG = '<svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>';
const VOL_OFF_SVG = '<svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><line x1="22" y1="9" x2="16" y2="15"/><line x1="16" y1="9" x2="22" y2="15"/></svg>';
const SUN_SVG = '<svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
const MOON_SVG = '<svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>';

function updateSoundUI() {
  const icon = document.getElementById("soundIcon");
  const label = document.getElementById("soundLabel");
  const en = SoundFX.isEnabled();
  if (icon) icon.innerHTML = en ? VOL_ON_SVG : VOL_OFF_SVG;
  if (label) label.textContent = en ? "Audio Activo" : "Audio Silenciado";
}

const MODE_COLORS = {
  coding: { hex: "#0ea5e9", rgb: "14, 165, 233" },
  writing: { hex: "#10b981", rgb: "16, 185, 129" },
  terminal: { hex: "#8b5cf6", rgb: "139, 92, 246" },
  sniper: { hex: "#f59e0b", rgb: "245, 158, 11" },
  data_math: { hex: "#3b82f6", rgb: "59, 130, 246" },
  gaming: { hex: "#ef4444", rgb: "239, 68, 68" }
};

function applyModeAccent(modeId) {
  const c = MODE_COLORS[modeId] || MODE_COLORS.coding;
  document.documentElement.style.setProperty("--mode-accent", c.hex);
  document.documentElement.style.setProperty("--mode-accent-rgb", c.rgb);
}

function applyTheme(themeName) {
  const normalized = (themeName === "switch" || themeName === "nintendo-booklet") ? "nintendo-booklet" : "cyber-glass";
  document.body.dataset.theme = normalized;
  try { localStorage.setItem("ideye_guide_theme", normalized); } catch (e) {}
  const themeButton = document.getElementById("themeToggle");
  if (themeButton) {
    const isDark = normalized === "cyber-glass";
    themeButton.innerHTML = isDark
      ? `${SUN_SVG}<span class="theme-label">Switch Light</span>`
      : `${MOON_SVG}<span class="theme-label">Cyber-Glass Dark</span>`;
  }
}

function toggleTheme() {
  const current = document.body.dataset.theme || "nintendo-booklet";
  const next = current === "cyber-glass" ? "nintendo-booklet" : "cyber-glass";
  applyTheme(next);
  SoundFX.tick();
}

function filterGuideContent(query) {
  const q = (query || "").trim().toLowerCase();
  document.querySelectorAll(".card").forEach(card => {
    if (!q) {
      card.style.display = "";
      return;
    }
    const match = card.textContent.toLowerCase().includes(q);
    card.style.display = match ? "" : "none";
  });
  document.querySelectorAll(".shortcut").forEach(sc => {
    if (!q) {
      sc.style.display = "";
      return;
    }
    const match = (sc.dataset.filter || sc.textContent).toLowerCase().includes(q);
    sc.style.display = match ? "" : "none";
  });
}
"""

STUDIO_CSS = """
/* ===================================================================
   IDEye Studio Redesign System (Switch Booklet Light vs Cyber-Glass Dark)
   =================================================================== */

:root {
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  --mode-accent: #0ea5e9;
  --mode-accent-rgb: 14, 165, 233;

  /* Switch Booklet Light (Editorial Nintendo Style) */
  --bg-page: #f8fafc;
  --bg-body-grad: radial-gradient(circle at 10% 10%, rgba(14, 165, 233, 0.05) 0%, transparent 40%),
                  radial-gradient(circle at 90% 90%, rgba(16, 185, 129, 0.04) 0%, transparent 40%),
                  #f8fafc;
  --bg-card: #ffffff;
  --bg-card-hover: #fcfdfe;
  --border-color: #e2e8f0;
  --border-subtle: #f1f5f9;
  --text-main: #0f172a;
  --text-muted: #475569;
  --header-bg: rgba(255, 255, 255, 0.88);
  --header-border: rgba(226, 232, 240, 0.95);
  --header-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.06), 0 4px 6px -2px rgba(15, 23, 42, 0.02);
  --nav-pill-bg: rgba(0, 0, 0, 0.04);
  --card-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.05), 0 1px 3px rgba(15, 23, 42, 0.02);
  --card-hover-shadow: 0 16px 32px -4px rgba(15, 23, 42, 0.1), 0 0 20px -2px rgba(var(--accent-rgb, var(--mode-accent-rgb)), 0.18);
  --chip-bg: #f1f5f9;
  --chip-text: #334155;
  --badge-bg: #f1f5f9;
  --badge-text: #475569;
  --hero-glow: radial-gradient(ellipse at 15% 30%, rgba(var(--mode-accent-rgb), 0.1) 0%, transparent 65%),
               radial-gradient(ellipse at 85% 70%, rgba(16, 185, 129, 0.06) 0%, transparent 60%);
}

body[data-theme="nintendo-booklet"],
body[data-theme="switch"] {
  --bg-page: #f8fafc;
  --bg-body-grad: radial-gradient(circle at 10% 10%, rgba(14, 165, 233, 0.05) 0%, transparent 40%),
                  radial-gradient(circle at 90% 90%, rgba(16, 185, 129, 0.04) 0%, transparent 40%),
                  #f8fafc;
  --bg-card: #ffffff;
  --bg-card-hover: #fcfdfe;
  --border-color: #e2e8f0;
  --border-subtle: #f1f5f9;
  --text-main: #0f172a;
  --text-muted: #475569;
  --header-bg: rgba(255, 255, 255, 0.88);
  --header-border: rgba(226, 232, 240, 0.95);
  --header-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.06), 0 4px 6px -2px rgba(15, 23, 42, 0.02);
  --nav-pill-bg: rgba(0, 0, 0, 0.04);
  --card-shadow: 0 4px 16px -2px rgba(15, 23, 42, 0.05), 0 1px 3px rgba(15, 23, 42, 0.02);
  --card-hover-shadow: 0 16px 32px -4px rgba(15, 23, 42, 0.1), 0 0 20px -2px rgba(var(--accent-rgb, var(--mode-accent-rgb)), 0.18);
  --chip-bg: #f1f5f9;
  --chip-text: #334155;
  --badge-bg: #f1f5f9;
  --badge-text: #475569;
  --hero-glow: radial-gradient(ellipse at 15% 30%, rgba(var(--mode-accent-rgb), 0.1) 0%, transparent 65%),
               radial-gradient(ellipse at 85% 70%, rgba(16, 185, 129, 0.06) 0%, transparent 60%);
}

body[data-theme="cyber-glass"] {
  --bg-page: #070b14;
  --bg-body-grad: radial-gradient(circle at 12% 15%, rgba(14, 165, 233, 0.1) 0%, transparent 45%),
                  radial-gradient(circle at 88% 85%, rgba(139, 92, 246, 0.08) 0%, transparent 45%),
                  #070b14;
  --bg-card: rgba(15, 23, 42, 0.72);
  --bg-card-hover: rgba(24, 34, 58, 0.85);
  --border-color: rgba(255, 255, 255, 0.08);
  --border-subtle: rgba(255, 255, 255, 0.04);
  --text-main: #f8fafc;
  --text-muted: #94a3b8;
  --header-bg: rgba(10, 15, 28, 0.82);
  --header-border: rgba(255, 255, 255, 0.12);
  --header-shadow: 0 16px 40px -10px rgba(0, 0, 0, 0.75), inset 0 1px 0 rgba(255, 255, 255, 0.1);
  --nav-pill-bg: rgba(255, 255, 255, 0.04);
  --card-shadow: 0 10px 30px -5px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.07);
  --card-hover-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.7), 0 0 24px -4px rgba(var(--accent-rgb, var(--mode-accent-rgb)), 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.15);
  --chip-bg: rgba(255, 255, 255, 0.05);
  --chip-text: #e2e8f0;
  --badge-bg: rgba(255, 255, 255, 0.06);
  --badge-text: #cbd5e1;
  --hero-glow: radial-gradient(ellipse at 15% 30%, rgba(var(--mode-accent-rgb), 0.2) 0%, transparent 65%),
               radial-gradient(ellipse at 85% 70%, rgba(99, 102, 241, 0.12) 0%, transparent 60%);
}

* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  color: var(--text-main);
  background: var(--bg-body-grad);
  font-family: var(--font-sans);
  min-height: 100vh;
  transition: background 0.25s ease, color 0.25s ease;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}

button { font: inherit; cursor: pointer; }

/* Global SVG Safety Constraint */
svg {
  max-width: 100%;
}

.ui-icon {
  width: 18px;
  height: 18px;
  max-width: 18px;
  max-height: 18px;
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
}

/* Sticky Header */
.sticky-header {
  position: sticky;
  top: 10px;
  z-index: 1000;
  width: min(1380px, calc(100% - 20px));
  margin: 10px auto 20px;
  background: var(--header-bg);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  border: 1px solid var(--header-border);
  border-radius: 16px;
  padding: 6px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: var(--header-shadow);
  gap: 8px;
}

.brand-section {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  color: inherit;
  flex-shrink: 0;
}
.brand-icon-frame {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #09090b;
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
  flex-shrink: 0;
  overflow: hidden;
}
.brand-icon-svg {
  width: 100%;
  height: 100%;
}
.brand-title {
  font-size: 14px;
  font-weight: 800;
  letter-spacing: -0.3px;
  line-height: 1.1;
}
.brand-subtitle {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-muted);
  line-height: 1.1;
}

/* Nav Pills */
.nav-pills {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  background: var(--nav-pill-bg);
  border-radius: 999px;
  border: 1px solid var(--border-subtle);
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
  flex-shrink: 1;
  min-width: 0;
}
.nav-pills::-webkit-scrollbar {
  display: none;
  width: 0;
  height: 0;
}

.tab {
  background: transparent;
  border: 1px solid transparent;
  color: var(--text-muted);
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: -0.1px;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  white-space: nowrap;
  flex-shrink: 0;
}
.tab:hover {
  color: var(--text-main);
  background: var(--bg-card-hover);
}
.tab.active {
  background: var(--mode-accent);
  color: #ffffff !important;
  border-color: transparent;
  box-shadow: 0 2px 8px rgba(var(--mode-accent-rgb), 0.35);
}
.tab-playground {
  background: rgba(var(--mode-accent-rgb), 0.12);
  color: var(--mode-accent);
  border-color: rgba(var(--mode-accent-rgb), 0.25);
  padding: 4px 9px;
}
.tab-playground:hover {
  background: rgba(var(--mode-accent-rgb), 0.2);
  color: var(--mode-accent);
}
.tab-playground.active {
  background: var(--mode-accent) !important;
  color: #ffffff !important;
}
.tab-playground .live-dot {
  display: inline-block;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #10b981;
  margin-right: 4px;
  animation: pulseLive 1.8s infinite;
}
@keyframes pulseLive {
  0% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.5; }
  100% { transform: scale(1); opacity: 1; }
}

/* Header Controls */
.header-controls {
  display: flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
}
.search-box {
  position: relative;
  display: flex;
  align-items: center;
}
.search-box input {
  font-family: inherit;
  font-size: 11px;
  padding: 4px 8px 4px 22px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-main);
  outline: none;
  width: 72px;
  transition: width 0.2s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.2s ease, box-shadow 0.2s ease;
}
.search-box input:focus {
  width: 110px;
  border-color: var(--mode-accent);
  box-shadow: 0 0 0 2px rgba(var(--mode-accent-rgb), 0.2);
}
.search-icon-svg {
  position: absolute;
  left: 6px;
  width: 11px;
  height: 11px;
  color: var(--text-muted);
  pointer-events: none;
}
.btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-main);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  transition: all 0.2s ease;
  white-space: nowrap;
}
.btn:hover {
  background: var(--bg-card-hover);
  border-color: var(--mode-accent);
  transform: translateY(-1px);
}
.btn:active {
  transform: translateY(0);
}

/* Main Container */
.app-container {
  width: min(1380px, calc(100% - 24px));
  margin: 0 auto 50px;
}

/* Page Section */
section.page {
  display: none;
  opacity: 0;
  transition: opacity 0.25s ease;
}
section.page.active {
  display: block;
  opacity: 1;
}

/* Clean Hero Banner */
.page-hero {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 18px;
  padding: 24px 28px;
  margin-bottom: 20px;
  box-shadow: var(--card-shadow);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
  position: relative;
  overflow: hidden;
}
.page-hero::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--hero-glow);
  pointer-events: none;
}
.page-hero-text {
  position: relative;
  z-index: 1;
}
.page-hero-topline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  background: rgba(var(--mode-accent-rgb), 0.1);
  border: 1px solid rgba(var(--mode-accent-rgb), 0.2);
  border-radius: 999px;
  margin-bottom: 8px;
}
.ribbon-star {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--mode-accent);
}
.ribbon-star .ui-icon {
  width: 14px;
  height: 14px;
}
.page-hero-text h2 {
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.5px;
  margin: 4px 0 6px;
  color: var(--text-main);
  line-height: 1.25;
}
.page-hero-text p.intro {
  font-size: 13.5px;
  color: var(--text-muted);
  margin: 0;
  max-width: 640px;
  line-height: 1.55;
}
.kicker {
  font-size: 10px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.7px;
  color: var(--mode-accent);
}
.mini-kicker {
  font-size: 9.5px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--mode-accent);
}

/* Stats Group */
.hero-stats {
  display: flex;
  gap: 10px;
  position: relative;
  z-index: 1;
}
.stat-pill {
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 10px 14px;
  text-align: center;
  min-width: 95px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.stat-val {
  font-size: 16px;
  font-weight: 800;
  color: var(--mode-accent);
  line-height: 1.2;
}
.stat-lbl {
  font-size: 10.5px;
  font-weight: 600;
  color: var(--text-muted);
  margin-top: 2px;
}

/* Double Page Booklet Container */
.double-page-container {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 1px minmax(0, 1fr);
  gap: 20px;
  position: relative;
}
@media (max-width: 960px) {
  .double-page-container {
    grid-template-columns: 1fr;
    gap: 16px;
  }
}

.book-spine {
  width: 1px;
  background: linear-gradient(180deg, transparent 0%, var(--border-color) 20%, var(--border-color) 80%, transparent 100%);
  opacity: 0.6;
}
@media (max-width: 960px) {
  .book-spine {
    display: none;
  }
}

.page-left, .page-right {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

/* Cards Grid */
.cards-subgrid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}
.page#custom .cards-subgrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
@media (max-width: 1100px) {
  .page#custom .cards-subgrid {
    grid-template-columns: 1fr;
  }
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 18px 20px;
  box-shadow: var(--card-shadow);
  transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s ease, border-color 0.22s ease;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2.5px;
  background: linear-gradient(90deg, var(--accent, var(--mode-accent)), transparent 85%);
  opacity: 0.6;
  transition: opacity 0.2s ease;
}
.card:hover {
  transform: translateY(-3px);
  border-color: var(--accent, var(--mode-accent));
  box-shadow: var(--card-hover-shadow);
}
.card:hover::before {
  opacity: 1;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.card-icon-clean {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: rgba(var(--accent-rgb, var(--mode-accent-rgb)), 0.12);
  border: 1px solid rgba(var(--accent-rgb, var(--mode-accent-rgb)), 0.22);
  color: var(--accent, var(--mode-accent));
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: transform 0.2s ease, background 0.2s ease;
}
.card:hover .card-icon-clean {
  transform: scale(1.06);
  background: rgba(var(--accent-rgb, var(--mode-accent-rgb)), 0.18);
}
.card-icon-clean svg {
  width: 22px;
  height: 22px;
}
.badge.sticker {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  letter-spacing: 0.3px;
  background: var(--badge-bg);
  color: var(--badge-text);
  border: 1px solid var(--border-color);
  border-radius: 999px;
  padding: 3px 9px;
}

.card-title {
  font-size: 15.5px;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-main);
  letter-spacing: -0.2px;
  line-height: 1.3;
}
.card-desc {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 12px;
  line-height: 1.55;
  flex: 1;
}
.card-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
}
.chip {
  font-size: 10.5px;
  font-weight: 600;
  background: var(--chip-bg);
  color: var(--chip-text);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 3px 8px;
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.chip::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent, var(--mode-accent));
  box-shadow: 0 0 5px var(--accent, var(--mode-accent));
}

/* Page Extra Section (Full width below cards) */
.page-extra-section {
  margin-top: 20px;
}

/* Page Numbers footer */
.page-numbers {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 18px;
  padding-top: 10px;
  border-top: 1px solid var(--border-subtle);
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  opacity: 0.6;
}

/* Gesture Strip */
.threshold-row {
  display: flex;
  gap: 16px;
  padding: 10px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 12px;
  flex-wrap: wrap;
  align-items: center;
  box-shadow: var(--card-shadow);
}
.threshold-row b { color: var(--mode-accent); font-weight: 700; margin-left: 3px; }
.gesture-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}
@media (max-width: 1024px) {
  .gesture-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .gesture-strip {
    grid-template-columns: 1fr;
  }
}
.gesture-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: var(--card-shadow);
  transition: transform 0.2s ease, border-color 0.2s ease;
}
.gesture-card:hover {
  transform: translateY(-2px);
  border-color: var(--mode-accent);
}
.gesture-icon {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: rgba(var(--mode-accent-rgb), 0.1);
  border: 1px solid rgba(var(--mode-accent-rgb), 0.2);
  color: var(--mode-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.gesture-icon svg { width: 20px; height: 20px; }
.gesture-card h4 { margin: 0 0 3px; font-size: 13.5px; color: var(--text-main); font-weight: 700; }
.gesture-card strong { display: block; font-size: 10.5px; color: var(--mode-accent); margin-bottom: 3px; font-weight: 600; }
.gesture-card p { margin: 0; font-size: 12px; color: var(--text-muted); line-height: 1.45; }

/* Shortcuts Grid */
.shortcut-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 10px;
  margin-top: 14px;
}
.shortcut {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  box-shadow: var(--card-shadow);
  transition: all 0.2s ease;
}
.shortcut:hover {
  border-color: var(--mode-accent);
  transform: translateY(-1px);
}
.shortcut kbd {
  font-family: var(--font-mono);
  font-size: 10.5px;
  font-weight: 700;
  padding: 4px 8px;
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-bottom-width: 2px;
  border-radius: 6px;
  color: var(--mode-accent);
  flex-shrink: 0;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.shortcut b { display: block; font-size: 12.5px; color: var(--text-main); margin-bottom: 2px; }
.shortcut span { font-size: 11px; color: var(--text-muted); line-height: 1.35; }

/* Dedicated Simulator & Playground View */
section.simulator {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 18px;
  padding: 26px 28px;
  box-shadow: var(--card-shadow);
  margin-top: 20px;
}
.sim-heading {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 14px;
}
.sim-heading h3 { margin: 3px 0 0; font-size: 20px; color: var(--text-main); font-weight: 800; }
.sim-modes { display: flex; gap: 6px; flex-wrap: wrap; }
.sim-mode {
  padding: 5px 12px;
  border-radius: 999px;
  border: 1px solid var(--border-color);
  background: var(--bg-page);
  color: var(--text-muted);
  font-size: 11.5px;
  font-weight: 600;
  transition: all 0.2s ease;
}
.sim-mode:hover {
  color: var(--text-main);
  border-color: var(--mode-accent);
}
.sim-mode.active {
  background: var(--mode-accent);
  color: #fff;
  border-color: transparent;
  box-shadow: 0 2px 10px rgba(var(--mode-accent-rgb), 0.35);
}
.sim-workspace {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 22px;
  margin-bottom: 26px;
}
@media (max-width: 900px) {
  .sim-workspace { grid-template-columns: 1fr; }
}

.sim-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}
.sim-cell {
  background: var(--bg-page);
  border: 1.5px solid var(--border-color);
  border-radius: 12px;
  padding: 14px 10px;
  text-align: center;
  min-height: 84px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  transition: all 0.15s ease;
  user-select: none;
  cursor: pointer;
}
.sim-cell:hover, .sim-cell.gaze-focused {
  border-color: var(--mode-accent);
  background: rgba(var(--mode-accent-rgb), 0.08);
  transform: scale(1.02);
}
.sim-cell.active-click {
  background: var(--mode-accent) !important;
  color: #fff !important;
}
.sim-cell.active-click .sim-cell-label,
.sim-cell.active-click .sim-cell-hint {
  color: #fff !important;
}
.sim-cell-label { font-size: 12px; font-weight: 700; color: var(--text-main); margin-bottom: 3px; line-height: 1.25; }
.sim-cell-hint { font-size: 10.5px; color: var(--text-muted); line-height: 1.25; }

.jaw-meter-container {
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
.jaw-meter-header {
  display: flex;
  justify-content: space-between;
  font-size: 10.5px;
  font-weight: 700;
  margin-bottom: 6px;
}
.jaw-track {
  height: 7px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
}
.jaw-fill {
  height: 100%;
  background: var(--mode-accent);
  transition: width 0.08s ease;
}

.sim-controls {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.sim-info {
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 14px 16px;
}
.sim-info h4 {
  margin: 3px 0 5px;
  font-size: 13.5px;
  color: var(--text-main);
  font-weight: 700;
}
.sim-info p {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.45;
}

.vscode-pane {
  background: #090d16;
  border: 1px solid #1e293b;
  border-radius: 12px;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.vscode-titlebar {
  background: #0f172a;
  padding: 9px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid #1e293b;
}
.vscode-dots { display: flex; gap: 5px; }
.vscode-dots span { width: 9px; height: 9px; border-radius: 50%; }
.vscode-dots span:nth-child(1) { background: #ef4444; }
.vscode-dots span:nth-child(2) { background: #f59e0b; }
.vscode-dots span:nth-child(3) { background: #10b981; }
.vscode-filename { font-size: 11.5px; color: #94a3b8; font-family: var(--font-mono); }
.vscode-code {
  margin: 0;
  padding: 16px;
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: #e2e8f0;
  overflow-y: auto;
  flex: 1;
  line-height: 1.6;
}
.c-comment { color: #64748b; font-style: italic; }
.c-keyword { color: #f43f5e; font-weight: 600; }
.c-func { color: #38bdf8; }
.c-type { color: #a78bfa; }
.c-num { color: #f59e0b; }

/* Dojo Section */
.dojo-section {
  border-top: 1px solid var(--border-color);
  padding-top: 20px;
}
.dojo-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.dojo-header h3 {
  margin: 3px 0 0;
  font-size: 17px;
  color: var(--text-main);
  font-weight: 700;
}
.dojo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 14px;
}
.dojo-card {
  background: var(--bg-page);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: all 0.2s ease;
}
.dojo-card.completed {
  border-color: #10b981;
  background: rgba(16, 185, 129, 0.05);
}
.dojo-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.dojo-badge {
  font-size: 9.5px;
  font-weight: 800;
  background: var(--mode-accent);
  color: #fff;
  border-radius: 4px;
  padding: 2px 6px;
}
.dojo-kicker {
  font-size: 9.5px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
}
.dojo-status {
  margin-left: auto;
  font-size: 10.5px;
  font-weight: 700;
}
.dojo-status.pending { color: #f59e0b; }
.dojo-status.completed { color: #10b981; }
.dojo-card h4 {
  margin: 0 0 5px;
  font-size: 14px;
  color: var(--text-main);
  font-weight: 700;
}
.dojo-card p {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.45;
}
.dojo-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-top: auto;
}
.dojo-action-btn {
  font-size: 11px;
  padding: 4px 10px;
}
.dojo-hint {
  font-size: 10.5px;
  color: var(--text-muted);
  font-style: italic;
}

.celebration-banner {
  display: none;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid #10b981;
  border-radius: 12px;
  padding: 16px;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}
.celebration-badge {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  background: #10b981;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.celebration-badge .ui-icon {
  width: 22px;
  height: 22px;
}
.celebration-text h4 {
  margin: 0 0 3px;
  font-size: 15px;
  color: #10b981;
  font-weight: 800;
}
.celebration-text p {
  margin: 0;
  font-size: 12.5px;
  color: var(--text-main);
  line-height: 1.45;
}
.celebration-btn {
  margin-left: auto;
  border-color: #10b981;
  color: #10b981;
}

/* Legal Footer */
.legal-footer {
  margin-top: 40px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
}
.legal-header {
  margin-bottom: 14px;
}
.legal-header h4 {
  margin: 2px 0 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main);
}
.legal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
@media (max-width: 900px) {
  .legal-grid {
    grid-template-columns: 1fr;
  }
}
.legal-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  box-shadow: var(--card-shadow);
}
.legal-icon {
  width: 36px;
  height: 36px;
  border-radius: 9px;
  background: rgba(var(--mode-accent-rgb), 0.1);
  border: 1px solid rgba(var(--mode-accent-rgb), 0.2);
  color: var(--mode-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.legal-icon svg {
  width: 20px;
  height: 20px;
  max-width: 20px;
  max-height: 20px;
}
.legal-item b {
  display: block;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--text-main);
  margin-bottom: 3px;
}
.legal-item p {
  margin: 0;
  font-size: 11.5px;
  line-height: 1.45;
  color: var(--text-muted);
}
.legal-subbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: var(--font-mono);
  font-size: 10.5px;
  color: var(--text-muted);
  padding-top: 12px;
  border-top: 1px solid var(--border-subtle);
  flex-wrap: wrap;
  gap: 8px;
  opacity: 0.75;
}

/* Print styling (A4 landscape) */
@media print {
  @page { size:A4 landscape; margin: 8mm; }
  body { background: #ffffff !important; color: #000000 !important; }
  .sticky-header, .sim-controls, #soundToggle, .theme-toggle, .search-box, .legal-footer { display: none !important; }
  section.page { display: block !important; opacity: 1 !important; page-break-after: always; }
  section.simulator { display: none !important; }
}
"""


def build_interactive_guide_html(catalog: Dict[str, Any]) -> str:
    """Renders the complete offline guide from a catalog dictionary."""
    pages = catalog.get("pages", [])
    simulator = catalog.get("simulator", {})
    data_json = json.dumps(catalog, ensure_ascii=False).replace("</", "<\\/")
    legal_items = catalog.get("legal", [])
    legal_html = "".join(
        f'<div class="legal-item"><span class="legal-icon">{_ui_icon(item.get("icon", "sparkles"), size=20)}</span>'
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
        tab_label = _esc(page.get("tab", f"Página {index + 1}").strip())
        tabs.append(
            f'<button class="tab{active}" data-page-target="{index}">{tab_label}</button>'
        )

        extra = ""
        if page_id == "gestures":
            extra = _gesture_strip(catalog.get("gestures", []), catalog.get("gesture_thresholds", {}))
        if page_id == "custom":
            extra = _shortcut_grid(catalog.get("shortcuts", []))

        page_cards = list(page.get("cards", []))
        mid = (len(page_cards) + 1) // 2
        left_cards = _cards(page_cards[:mid], accent)
        right_cards = _cards(page_cards[mid:], accent)

        sections.append(
            f'''
            <section class="page{active}" data-page="{index}" id="{_esc(page_id)}">
              <div class="page-hero">
                <div class="page-hero-text">
                  <div class="page-hero-topline">
                    <span class="ribbon-star">{_ui_icon("star-badge")}</span>
                    <span class="kicker">{_esc(page.get("kicker", "CENTRO DE MANDO"))}</span>
                  </div>
                  <h2 class="page-title brush-title"><span>{_esc(page.get("title", ""))}</span></h2>
                  <p class="intro">{_esc(page.get("intro", ""))}</p>
                </div>
                <div class="hero-stats">
                  <div class="stat-pill"><div class="stat-val">&lt; 35ms</div><div class="stat-lbl">One Euro</div></div>
                  <div class="stat-pill"><div class="stat-val">Zero-Dwell</div><div class="stat-lbl">Anti-Midas</div></div>
                  <div class="stat-pill"><div class="stat-val">6 Modos</div><div class="stat-lbl">Sniper / AST</div></div>
                </div>
              </div>
              <div class="double-page-container">
                <div class="page page-left">
                  <div class="cards-subgrid">{left_cards}</div>
                </div>
                <div class="book-spine" aria-hidden="true"></div>
                <div class="page page-right">
                  <div class="cards-subgrid">{right_cards}</div>
                </div>
              </div>
              {f'<div class="page-extra-section">{extra}</div>' if extra else ''}
              <div class="page-numbers"><span>{index * 2 + 1}</span><span>{index * 2 + 2}</span></div>
            </section>'''
        )

    # Dedicated Simulator view
    sim_block = _simulator(simulator, catalog.get("dojo_challenges", []))

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IDEye — Manual Interactivo</title>
  {f'<link rel="icon" href="{app_icon}">' if app_icon else ''}
  <style>
  {STUDIO_CSS}
  </style>
</head>
<body data-theme="nintendo-booklet">

  <!-- Floating Gaze Simulation Reticle -->
  <div id="gazeReticle" class="gaze-reticle" aria-hidden="true" style="position:fixed; pointer-events:none; z-index:9999; transform:translate(-50%, -50%); display:none;">
    <svg viewBox="0 0 40 40" width="36" height="36">
      <circle cx="20" cy="20" r="14" fill="none" stroke="currentColor" stroke-width="2"/>
      <circle cx="20" cy="20" r="3" fill="currentColor"/>
    </svg>
  </div>

  <!-- Sticky Top Navigation Bar -->
  <header class="sticky-header">
    <div class="brand-section">
      <div class="brand-icon-frame">{logo_markup}</div>
      <div class="brand-info">
        <div class="brand-title">IDEye</div>
        <div class="brand-subtitle"><span id="pageLabel">Página 1</span> · Manual &amp; Playground</div>
      </div>
    </div>

    <!-- Navigation Pills -->
    <nav class="nav-pills" id="navTabs">
      {"".join(tabs)}
      <button type="button" class="tab tab-playground" id="tabPlayground" onclick="showSimulatorView()">
        <span class="live-dot"></span>SIMULADOR EN VIVO
      </button>
    </nav>

    <!-- Header Actions -->
    <div class="header-controls">
      <div class="search-box">
        <svg class="search-icon-svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
        <input type="search" placeholder="Buscar..." oninput="filterGuideContent(this.value)" aria-label="Buscar en la guía">
      </div>
      <button type="button" class="btn theme-toggle" id="themeToggle" onclick="toggleTheme()" title="Cambiar tema">
        <svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg><span class="theme-label">Cyber-Glass</span>
      </button>
      <button type="button" class="btn" onclick="window.print()" title="Imprimir / Exportar PDF">
        {_ui_icon("printer")}<span>Imprimir</span>
      </button>
    </div>
  </header>

  <!-- Main Content Container -->
  <main class="app-container">
    {"".join(sections)}
    {sim_block}

    <!-- Legal Footer -->
    <footer class="legal-footer">
      <div class="legal-header">
        <span class="mini-kicker">SEGURIDAD · PRIVACIDAD · ERGONOMÍA</span>
        <h4>Garantías de Arquitectura Local y Ergonomía</h4>
      </div>
      <div class="legal-grid">
        {legal_html}
      </div>
      <div class="legal-subbar">
        <span>IDEye Look-To-Code Engine · 100% Offline &amp; Local</span>
        <span>v1.0.0 · Manual Interactivo</span>
      </div>
    </footer>
  </main>

  <script>
  const GUIDE = {data_json};
  {THEME_JS}

  let currentPage = 0;
  let currentMode = "coding";
  let inSimulatorView = false;
  let isSniperActive = false;
  let hoveredCell = null;

  function showPage(index) {{
    inSimulatorView = false;
    const sim = document.getElementById("simSection");
    if (sim) sim.style.display = "none";
    const playTab = document.getElementById("tabPlayground");
    if (playTab) playTab.classList.remove("active");

    const pages = [...document.querySelectorAll("section.page")];
    if (!pages.length) return;
    currentPage = Math.max(0, Math.min(pages.length - 1, index));
    pages.forEach((p, i) => p.classList.toggle("active", i === currentPage));
    document.querySelectorAll("#navTabs .tab:not(.tab-playground)").forEach((tab, i) => {{
      tab.classList.toggle("active", i === currentPage);
    }});
    const label = document.getElementById("pageLabel");
    if (label) label.textContent = `Página ${{currentPage + 1}}`;
    window.scrollTo({{top: 0, behavior: "smooth"}});
  }}

  function showSimulatorView() {{
    inSimulatorView = true;
    document.querySelectorAll("section.page").forEach(p => p.classList.remove("active"));
    document.querySelectorAll("#navTabs .tab:not(.tab-playground)").forEach(tab => tab.classList.remove("active"));
    const playTab = document.getElementById("tabPlayground");
    if (playTab) playTab.classList.add("active");
    const label = document.getElementById("pageLabel");
    if (label) label.textContent = "Simulador";
    const sim = document.getElementById("simSection");
    if (sim) {{
      sim.style.display = "block";
      renderSimulator(currentMode);
      window.scrollTo({{top: sim.offsetTop - 80, behavior: "smooth"}});
    }}
  }}

  function renderSimulator(modeId) {{
    const mode = (GUIDE.simulator || {{}})[modeId];
    if (!mode) return;
    currentMode = modeId;
    applyModeAccent(modeId);
    document.querySelectorAll(".sim-mode").forEach(btn => {{
      btn.classList.toggle("active", btn.dataset.mode === modeId);
    }});
    const grid = document.getElementById("simGrid");
    if (!grid) return;
    grid.innerHTML = "";
    mode.cells.forEach((cell, idx) => {{
      const div = document.createElement("div");
      div.className = "sim-cell";
      div.dataset.cellIndex = String(idx);
      div.innerHTML = `<span class="sim-cell-label">${{cell.label}}</span><span class="sim-cell-hint">${{cell.hint}}</span>`;
      div.onclick = () => triggerCellClick(idx);
      grid.appendChild(div);
    }});
  }}

  function triggerCellClick(index) {{
    SoundFX.confirm();
    const mode = (GUIDE.simulator || {{}})[currentMode];
    if (!mode || !mode.cells || !mode.cells[index]) return;
    const cell = mode.cells[index];
    const editor = document.getElementById("vscCodeContent");
    if (editor && cell.snippet) {{
      editor.innerHTML = `<code><span class="c-comment"># Inyectado desde el HUD (Casilla ${{index + 1}}):</span>\\n${{cell.snippet}}</code>`;
    }}
    const cellEl = document.querySelector(`.sim-cell[data-cell-index="${{index}}"]`);
    if (cellEl) {{
      cellEl.classList.add("active-click");
      setTimeout(() => cellEl.classList.remove("active-click"), 250);
    }}
  }}

  function toggleSniperLens() {{
    isSniperActive = !isSniperActive;
    SoundFX.whoosh();
    completeDojoChallenge("sniper-lens");
  }}

  function triggerGazeScrollSim() {{
    SoundFX.tick();
    completeDojoChallenge("gaze-scroll");
  }}

  function triggerAgenticPromptSim() {{
    SoundFX.confirm();
    completeDojoChallenge("agentic-mcp");
  }}

  function completeDojoChallenge(id) {{
    try {{
      let prog = JSON.parse(localStorage.getItem("ideye_dojo_progress") || "{{}}");
      prog[id] = true;
      localStorage.setItem("ideye_dojo_progress", JSON.stringify(prog));
      updateDojoCards();
    }} catch (e) {{}}
  }}

  function updateDojoCards() {{
    try {{
      let prog = JSON.parse(localStorage.getItem("ideye_dojo_progress") || "{{}}");
      const challenges = GUIDE.dojo_challenges || [];
      let completedCount = 0;
      challenges.forEach(ch => {{
        const card = document.getElementById(`dojoCard_${{ch.id}}`);
        const status = document.getElementById(`dojoStatus_${{ch.id}}`);
        if (prog[ch.id]) {{
          completedCount++;
          if (card) card.classList.add("completed");
          if (status) {{ status.textContent = "COMPLETADO"; status.className = "dojo-status completed"; }}
        }}
      }});
      const celebration = document.getElementById("dojoCelebration");
      if (celebration && completedCount >= challenges.length && challenges.length > 0) {{
        celebration.style.display = "flex";
      }}
    }} catch (e) {{}}
  }}

  function resetDojoProgress() {{
    try {{
      localStorage.removeItem("ideye_dojo_progress");
      document.querySelectorAll(".dojo-card").forEach(c => c.classList.remove("completed"));
      document.querySelectorAll(".dojo-status").forEach(s => {{ s.textContent = "PENDIENTE"; s.className = "dojo-status pending"; }});
      const celebration = document.getElementById("dojoCelebration");
      if (celebration) celebration.style.display = "none";
    }} catch (e) {{}}
  }}

  // Tab navigation binding
  document.querySelectorAll("[data-page-target]").forEach(btn => {{
    btn.addEventListener("click", () => {{
      SoundFX.tick();
      showPage(Number(btn.dataset.pageTarget));
    }});
  }});

  // Mode switcher binding in simulator
  document.querySelectorAll(".sim-mode").forEach(btn => {{
    btn.addEventListener("click", () => {{
      SoundFX.mode();
      renderSimulator(btn.dataset.mode);
    }});
  }});

  // Mouse simulated gaze reticle
  window.addEventListener("mousemove", (e) => {{
    const reticle = document.getElementById("gazeReticle");
    if (reticle && inSimulatorView) {{
      reticle.style.display = "block";
      reticle.style.left = e.clientX + "px";
      reticle.style.top = e.clientY + "px";
    }} else if (reticle) {{
      reticle.style.display = "none";
    }}
  }});

  // Keyboard space = simulate mouth click in simulator
  window.addEventListener("keydown", (e) => {{
    if (e.code === "Space" && inSimulatorView) {{
      e.preventDefault();
      const jaw = document.getElementById("jawFill");
      const val = document.getElementById("jawValue");
      if (jaw) jaw.style.width = "85%";
      if (val) val.textContent = "MAR: 0.42 (CONFIRMADO)";
      SoundFX.confirm();
      completeDojoChallenge("mar-click");
      setTimeout(() => {{
        if (jaw) jaw.style.width = "15%";
        if (val) val.textContent = "MAR: 0.15 (Reposo)";
      }}, 300);
    }}
  }});

  // Initialize
  window.addEventListener("DOMContentLoaded", () => {{
    const savedTheme = localStorage.getItem("ideye_guide_theme") || "nintendo-booklet";
    applyTheme(savedTheme);
    updateSoundUI();
    updateDojoCards();
    showPage(0);
  }});
  </script>
</body>
</html>
"""

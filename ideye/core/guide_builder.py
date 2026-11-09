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
        Path(__file__).resolve().parent.parent.parent / "ideye.ico",
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
        "trophy": '<path d="M24 36h-6a10 10 0 0 1 0-20h6M72 36h6a10 10 0 0 0 0-20h-6M16 88h64M40 58v10c0 4-3 6-6 6h-2v14h32V74h-2c-3 0-6-2-6-6V58M24 16h48v12a24 24 0 0 1-48 0V16Z"/>',
        "crosshair": '<circle cx="48" cy="48" r="36"/><path d="M48 4v20M48 72v20M4 48h20M72 48h20"/>',
        "zap": '<path d="M52 8 16 54h28l-4 34 36-46H48l4-34Z"/>',
        "cpu": '<rect x="16" y="16" width="64" height="64" rx="8"/><rect x="36" y="36" width="24" height="24"/><path d="M36 4v12M60 4v12M36 80v12M60 80v12M80 36h12M80 60h12M4 36h12M4 60h12"/>',
        "volume-2": '<polygon points="44 20 24 36 8 36 8 60 24 60 44 76 44 20"/><path d="M62 34a20 20 0 0 1 0 28M76 20a40 40 0 0 1 0 56"/>',
        "volume-x": '<polygon points="44 20 24 36 8 36 8 60 24 60 44 76 44 20"/><line x1="88" y1="36" x2="64" y2="60"/><line x1="64" y1="36" x2="88" y2="60"/>',
    }
    body = icons.get(kind, icons["grid"])
    return f'<svg class="icon" {common} aria-hidden="true">{body}</svg>'


def _ui_icon(name: str, extra_class: str = "") -> str:
    try:
        from ideye.core.guide_catalog import SVG_ICONS
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
    bubbles = ("¡MIRA!", "¡BIEN!", "¡CLIC!", "¡UF!")
    for index, card in enumerate(cards):
        bubble = bubbles[index % len(bubbles)]
        blocks.append(
            f'''
            <article class="card card-{index % 2}" style="--accent:{accent}">
<div class="badge sticker">{_ui_icon("star-badge")}<span>{_esc(card.get("badge", "FIX"))}</span></div>
              <h3 class="brush-title"><span>{_esc(card.get("title", ""))}</span></h3>
              <div class="card-icon"><div class="illustration" style="--accent:{accent}">
                <span class="comic-bubble">{bubble}</span>
                <span class="comic-star">{_ui_icon("star-badge")}</span>
                {_icon(str(card.get("icon", "grid")))}
                <svg class="action-arrow" viewBox="0 0 48 32" fill="none" aria-hidden="true"><path d="M4 24c10-1 18-6 26-16M26 8h10v10" stroke="#111" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/><path d="M4 24c10-1 18-6 26-16M26 8h10v10" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>
              </div></div>
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
              <div class="jaw-threshold-line" title="Umbral Clic MAR = 0.45" style="left:45%"><span class="threshold-label">0.45</span></div>
            </div>
            <div class="jaw-actions">
              <button type="button" class="btn sim-action-btn" id="btnTriggerMAR" onclick="triggerMARClick()">{_ui_icon("zap")}<span>Disparar MAR [Espacio]</span></button>
              <button type="button" class="btn sim-action-btn" id="btnToggleSniper" onclick="toggleSniperLens()">{_ui_icon("crosshair")}<span>Sniper x3.5 (Ctrl+Alt+Z)</span></button>
              <button type="button" class="btn sim-action-btn" id="btnGazeScroll" onclick="triggerGazeScrollSim()">{_ui_icon("compass")}<span>Scroll Ocular (Ctrl+Alt+W)</span></button>
              <button type="button" class="btn sim-action-btn" id="btnAgenticPrompt" onclick="triggerAgenticPromptSim()">{_ui_icon("wand")}<span>Agentic Launcher (Ctrl+Alt+I)</span></button>
            </div>
          </div>
          <aside id="simInfo" class="sim-info">
            <span class="mini-kicker">CASILLA ENFOCADA</span>
            <h4>Elige una celda</h4>
            <p>Haz clic en cualquier casilla para ver qué hace e inyectar su código en el editor VS Code simulado.</p>
          </aside>
        </div>
        <div class="sim-right-pane">
          <div class="vscode-pane" id="simEditor">
            <div class="vsc-titlebar">
              <div class="vsc-tabs">
                <div class="vsc-tab active">
                  {_ui_icon("code-bracket", "vsc-tab-icon")}
                  <span>solution.py</span>
                  <span class="vsc-tab-close">×</span>
                </div>
                <div class="vsc-tab">
                  <span>diagnostics.log</span>
                </div>
              </div>
              <div class="vsc-breadcrumbs">ideye &gt; core &gt; solution.py</div>
              <div class="vsc-actions">
                <button type="button" class="vsc-btn" id="btnResetEditor" onclick="resetSimEditor()" title="Limpiar y restaurar código">{_ui_icon("rotate-ccw")}<span>Limpiar</span></button>
                <button type="button" class="vsc-btn" id="btnCopyEditor" onclick="copySimEditor()" title="Copiar código">{_ui_icon("clipboard")}<span>Copiar</span></button>
                <button type="button" class="vsc-btn vsc-btn-primary" id="btnRunSnippet" onclick="runSimSnippet()" title="Ejecutar">{_ui_icon("play")}<span>Ejecutar</span></button>
              </div>
            </div>
            <div class="vsc-editor-body">
              <div class="vsc-line-numbers" id="vscLineNumbers"></div>
              <pre class="vsc-code-content" id="vscCodeContent" spellcheck="false" contenteditable="true"></pre>
            </div>
            <div class="vsc-statusbar">
              <div class="vsc-status-left">
                <span class="vsc-status-item"><span class="vsc-dot"></span> IDEye 60Hz: Conectado</span>
                <span class="vsc-status-item">Ln <span id="vscLn">1</span>, Col <span id="vscCol">1</span></span>
                <span class="vsc-status-item">Modo: <b id="vscModeStatus">Código</b></span>
              </div>
              <div class="vsc-status-right">
                <span class="vsc-status-item">Spaces: 4</span>
                <span class="vsc-status-item">UTF-8</span>
                <span class="vsc-status-item">Python 3.12</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="dojo-section" id="dojoContainer" aria-label="Dojo de entrenamiento con micro-desafíos">
        <div class="dojo-header">
          <div class="dojo-title-box">
            <span class="dojo-trophy-icon">{_ui_icon("trophy")}</span>
            <div>
              <span class="mini-kicker">TRAINING DOJO · MICRO-DESAFÍOS GAMIFICADOS</span>
              <h3>Dojo de Entrenamiento Ocular</h3>
              <p>Supera los 6 micro-desafíos para dominar la interacción sin manos con Zero-Dwell y MAR.</p>
            </div>
          </div>
          <div class="dojo-progress-box">
            <div class="dojo-progress-label">
              <span>Progreso del Dojo:</span>
              <b><span id="dojoCompleted">0</span> / 6 (<span id="dojoPercent">0%</span>)</b>
            </div>
            <div class="dojo-meter">
              <div class="dojo-meter-fill" id="dojoMeterFill" style="width:0%"></div>
            </div>
          </div>
        </div>
        <div class="dojo-celebration" id="dojoCelebration" style="display:none">
          <div class="celebration-badge">{_ui_icon("trophy")}</div>
          <div class="celebration-text">
            <h4>¡MAESTRO DE IDEYE DESBLOQUEADO!</h4>
            <p>Has completado todos los desafíos: fijación Zero-Dwell, disparo bucal MAR, inyección de código, scroll inercial, lente Sniper y Agentic Launcher.</p>
          </div>
          <button type="button" class="btn celebration-btn" onclick="resetDojoProgress()">{_ui_icon("rotate-ccw")}<span>Reiniciar Retos</span></button>
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

  // Pre-unlock audio context on first user pointer or key gesture
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
      gain.gain.setValueAtTime(gainVal || 0.08, c.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + duration);
      osc.connect(gain);
      gain.connect(c.destination);
      osc.start();
      osc.stop(c.currentTime + duration);
    } catch (e) {}
  }

  return {
    isEnabled: () => enabled,
    setEnabled: (val) => {
      enabled = !!val;
      try { localStorage.setItem("ideye_sound_enabled", enabled ? "true" : "false"); } catch (e) {}
      updateSoundUI();
    },
    tick: () => playTone(980, "sine", 0.025, 0.035),
    click: () => {
      playTone(540, "triangle", 0.12, 0.08);
      setTimeout(() => playTone(1080, "sine", 0.08, 0.05), 25);
    },
    fanfare: () => {
      const notes = [523.25, 659.25, 783.99, 1046.50];
      notes.forEach((f, i) => {
        setTimeout(() => playTone(f, "triangle", 0.22, 0.09), i * 90);
      });
    },
    whoosh: () => playTone(440, "sine", 0.14, 0.05, 180),
    shockwave: () => playTone(300, "triangle", 0.16, 0.1, 110),
    chime: () => {
      playTone(659.25, "triangle", 0.12, 0.07);
      setTimeout(() => playTone(987.77, "sine", 0.16, 0.07), 70);
    },
  };
})();

const VOL_ON_SVG = '<polygon points="44 20 24 36 8 36 8 60 24 60 44 76 44 20"/><path d="M62 34a20 20 0 0 1 0 28M76 20a40 40 0 0 1 0 56"/>';
const VOL_OFF_SVG = '<polygon points="44 20 24 36 8 36 8 60 24 60 44 76 44 20"/><line x1="88" y1="36" x2="64" y2="60"/><line x1="64" y1="36" x2="88" y2="60"/>';

function toggleSound() {
  SoundFX.setEnabled(!SoundFX.isEnabled());
  if (SoundFX.isEnabled()) SoundFX.click();
}

function updateSoundUI() {
  const btn = document.getElementById("soundToggle");
  const label = document.getElementById("soundLabel");
  if (!btn || !label) return;
  const on = SoundFX.isEnabled();
  label.textContent = on ? "Sonido: ON" : "Sonido: OFF";
  btn.classList.toggle("muted", !on);
  const icon = btn.querySelector("svg");
  if (icon) {
    icon.innerHTML = on ? VOL_ON_SVG : VOL_OFF_SVG;
  }
}

// Multi-Theme Selector
const themeButton = document.getElementById("themeToggle");
function applyTheme(theme) {
  const selected = theme === "cyber-glass" ? "cyber-glass" : "nintendo-booklet";
  document.body.dataset.theme = selected;
  try { localStorage.setItem("ideye_guide_theme", selected); } catch (e) {}
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
  SoundFX.whoosh();
}

// Reactive Mode Accents (Cyan for Coding, Emerald for Writing, Purple for Terminal, Crimson for Gaming, Amber for Data/Math)
const MODE_COLORS = {
  coding: { accent: "#06b6d4", rgb: "6, 182, 212", name: "Código (AST)" },
  writing: { accent: "#10b981", rgb: "16, 185, 129", name: "Redacción (T9)" },
  terminal: { accent: "#a855f7", rgb: "168, 85, 247", name: "Terminal (Git)" },
  sniper: { accent: "#ef4444", rgb: "239, 68, 68", name: "Gaming (60Hz)" },
  data_math: { accent: "#f59e0b", rgb: "245, 158, 11", name: "Datos / Math (SQL & LaTeX)" },
};

function applyModeAccent(modeId) {
  const conf = MODE_COLORS[modeId] || MODE_COLORS.coding;
  document.documentElement.style.setProperty("--mode-accent", conf.accent);
  document.documentElement.style.setProperty("--mode-accent-rgb", conf.rgb);
  const statusEl = document.getElementById("vscModeStatus");
  if (statusEl) statusEl.textContent = conf.name;
}

// Simulated VS Code Editor
const INITIAL_CODE = `# IDEye L2C Engine — Editor Asistivo
# Mirada como intención, boca como confirmación
import math
from ideye.core import GestureDetector, OneEuroFilter

class GazeController:
    def __init__(self, fps: int = 60):
        self.fps = fps
        self.reticle_filter = OneEuroFilter(freq=fps, mincutoff=1.2, beta=0.02)
        self.resting_mar_baseline = 0.15
        self.zero_dwell_active = True

    def on_frame(self, iris_x: float, iris_y: float, mar: float):
        smooth_x, smooth_y = self.reticle_filter(iris_x, iris_y)
        # Mirar solo enfoca (Zero-Dwell Midas Elimination)
        if mar > 0.45:
            self.execute_mar_click(smooth_x, smooth_y)
`;

function initSimEditor() {
  const editor = document.getElementById("vscCodeContent");
  if (editor && !editor.dataset.initialized) {
    editor.dataset.initialized = "true";
    setEditorCode(INITIAL_CODE);
  }
}

function setEditorCode(codeText) {
  const editor = document.getElementById("vscCodeContent");
  if (!editor) return;
  editor.innerHTML = highlightSyntax(codeText);
  updateLineNumbers();
}

function highlightSyntax(code) {
  const escaped = code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  return escaped.split("\\n").map(line => {
    if (line.trim().startsWith("#") || line.trim().startsWith("//") || line.trim().startsWith("$") || line.trim().startsWith("--")) {
      return '<span class="syn-com">' + line + '</span>';
    }
    let hl = line
      .replace(/(".*?"|'.*?'|«.*?»)/g, '<span class="syn-str">$1</span>')
      .replace(/\\b(def|class|import|from|return|if|else|elif|for|while|await|async|pass|and|or|not|in|is|None|True|False|SELECT|FROM|WHERE|JOIN|GROUP|BY|ORDER|HAVING|LIMIT|INSERT|UPDATE|DELETE|CREATE|TABLE|ALTER|UNION)\\b/g, '<span class="syn-kw">$1</span>')
      .replace(/\\b([a-zA-Z_]\\w*)(?=\\s*\\()/g, '<span class="syn-fn">$1</span>')
      .replace(/\\b(\\d+(\\.\\d+)?)\\b/g, '<span class="syn-num">$1</span>');
    return hl;
  }).join("\\n");
}

function updateLineNumbers() {
  const editor = document.getElementById("vscCodeContent");
  const lineBox = document.getElementById("vscLineNumbers");
  if (!editor || !lineBox) return;
  const lineCount = editor.innerText.split("\\n").length;
  let html = "";
  for (let i = 1; i <= Math.max(lineCount, 12); i++) {
    html += "<span>" + i + "</span>";
  }
  lineBox.innerHTML = html;
  const lnEl = document.getElementById("vscLn");
  if (lnEl) lnEl.textContent = lineCount;
}

function injectCodeIntoEditor(snippet) {
  const editor = document.getElementById("vscCodeContent");
  if (!editor) return;
  const current = editor.innerText;
  const updated = current + (current.endsWith("\\n") ? "" : "\\n") + snippet;
  setEditorCode(updated);
  editor.scrollTop = editor.scrollHeight;
  SoundFX.click();
  completeDojoChallenge("code-inject");
}

function resetSimEditor() {
  setEditorCode(INITIAL_CODE);
  SoundFX.whoosh();
}

function copySimEditor() {
  const editor = document.getElementById("vscCodeContent");
  if (editor && navigator.clipboard) {
    navigator.clipboard.writeText(editor.innerText).catch(() => {});
    SoundFX.click();
  }
}

function runSimSnippet() {
  injectCodeIntoEditor("# [Ejecución IA] Pipeline verificado: 0 errores de sintaxis, 60 FPS estables\\n");
  SoundFX.fanfare();
}

// Training Dojo Challenges Engine with LocalStorage Persistence
const completedChallenges = new Set();

function completeDojoChallenge(id, silent) {
  if (completedChallenges.has(id)) return;
  completedChallenges.add(id);

  try {
    localStorage.setItem("ideye_dojo_progress", JSON.stringify([...completedChallenges]));
  } catch (e) {}

  const card = document.getElementById("dojoCard_" + id);
  const status = document.getElementById("dojoStatus_" + id);
  if (card) card.classList.add("completed");
  if (status) {
    status.classList.remove("pending");
    status.classList.add("done");
    status.textContent = "COMPLETADO";
  }

  const count = completedChallenges.size;
  const countEl = document.getElementById("dojoCompleted");
  const percentEl = document.getElementById("dojoPercent");
  const meterEl = document.getElementById("dojoMeterFill");
  if (countEl) countEl.textContent = count;
  const percent = Math.round((count / 6) * 100);
  if (percentEl) percentEl.textContent = percent + "%";
  if (meterEl) meterEl.style.width = percent + "%";

  if (!silent) {
    if (count === 6) {
      const celebration = document.getElementById("dojoCelebration");
      if (celebration) {
        celebration.style.display = "flex";
        celebration.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
      SoundFX.fanfare();
    } else {
      SoundFX.chime();
    }
  }
}

function triggerDojoChallenge(id) {
  showPage(2);
  if (id === "zero-dwell") {
    const firstCell = document.querySelector(".sim-cell");
    if (firstCell) {
      firstCell.classList.add("gaze-focused");
      setTimeout(() => firstCell.classList.remove("gaze-focused"), 1200);
    }
    completeDojoChallenge("zero-dwell");
  } else if (id === "mar-click") {
    triggerMARClick();
  } else if (id === "code-inject") {
    injectCodeIntoEditor("if mar > 0.45:\\n    # Snippet inyectado desde el Dojo\\n    trigger_action()\\n");
  } else if (id === "gaze-scroll") {
    triggerGazeScrollSim();
  } else if (id === "sniper-lens") {
    toggleSniperLens();
  } else if (id === "agentic-mcp") {
    triggerAgenticPromptSim();
  }
}

function jumpToDojo() {
  showPage(2);
  const dojo = document.getElementById("dojoContainer");
  if (dojo) dojo.scrollIntoView({ behavior: "smooth", block: "start" });
  SoundFX.tick();
}

function resetDojoProgress() {
  completedChallenges.clear();
  try { localStorage.removeItem("ideye_dojo_progress"); } catch (e) {}
  document.querySelectorAll(".dojo-card").forEach(c => c.classList.remove("completed"));
  document.querySelectorAll(".dojo-status").forEach(s => {
    s.classList.remove("done");
    s.classList.add("pending");
    s.textContent = "PENDIENTE";
  });
  const countEl = document.getElementById("dojoCompleted");
  const percentEl = document.getElementById("dojoPercent");
  const meterEl = document.getElementById("dojoMeterFill");
  const celebration = document.getElementById("dojoCelebration");
  if (countEl) countEl.textContent = "0";
  if (percentEl) percentEl.textContent = "0%";
  if (meterEl) meterEl.style.width = "0%";
  if (celebration) celebration.style.display = "none";
  SoundFX.whoosh();
}

// MAR Mouth Aperture & Zero-Dwell Click Confirmation
let hoveredCell = null;

function selectAndExecuteCell(btn, cell, index, modeName) {
  document.querySelectorAll(".sim-cell").forEach(c => c.classList.remove("selected"));
  if (btn) btn.classList.add("selected");
  const info = document.getElementById("simInfo");
  if (info) {
    info.innerHTML = `<span class="mini-kicker">${modeName.toUpperCase()} · CASILLA ${index + 1}</span><h4>${cell.label}</h4><p>${cell.hint}</p>`;
  }
  if (cell.snippet) {
    injectCodeIntoEditor(cell.snippet);
  } else {
    injectCodeIntoEditor(`# Acción: ${cell.label}\\n`);
  }
}

function triggerMARClick(originX, originY, targetBtn) {
  const jawFill = document.getElementById("jawFill");
  const jawValue = document.getElementById("jawValue");
  if (jawFill) {
    jawFill.style.width = "62%";
    jawFill.classList.add("triggered");
  }
  if (jawValue) {
    jawValue.textContent = "MAR: 0.62 [CLIC DISPARADO > 0.45]";
    jawValue.classList.add("triggered");
  }

  createShockwave(originX, originY);
  SoundFX.shockwave();
  completeDojoChallenge("mar-click");

  const btn = targetBtn || hoveredCell || document.querySelector(".sim-cell.selected") || document.querySelector(".sim-cell");
  if (btn && btn.dataset && btn.dataset.cellIndex !== undefined) {
    const idx = Number(btn.dataset.cellIndex);
    const mode = (GUIDE.simulator || {})[currentMode];
    if (mode && mode.cells && mode.cells[idx]) {
      selectAndExecuteCell(btn, mode.cells[idx], idx, mode.name);
    }
  }

  setTimeout(() => {
    if (jawFill) {
      jawFill.style.width = "15%";
      jawFill.classList.remove("triggered");
    }
    if (jawValue) {
      jawValue.textContent = "MAR: 0.15 (Línea Base Reposo)";
      jawValue.classList.remove("triggered");
    }
  }, 480);
}

function createShockwave(x, y) {
  const shock = document.createElement("div");
  shock.className = "gaze-shockwave";
  const posX = (x !== undefined && x !== null) ? x : reticleX;
  const posY = (y !== undefined && y !== null) ? y : reticleY;
  shock.style.left = posX + "px";
  shock.style.top = posY + "px";
  document.body.appendChild(shock);
  setTimeout(() => shock.remove(), 650);
}

// Sniper Lens Toggle
let isSniperActive = false;
function toggleSniperLens() {
  isSniperActive = !isSniperActive;
  const reticle = document.getElementById("gazeReticle");
  const btn = document.getElementById("btnToggleSniper");
  if (reticle) reticle.classList.toggle("sniper-mode", isSniperActive);
  if (btn) btn.classList.toggle("active", isSniperActive);
  SoundFX.whoosh();
  if (isSniperActive) completeDojoChallenge("sniper-lens");
}

// Gaze Scroll Simulation
function triggerGazeScrollSim() {
  const editor = document.getElementById("vscCodeContent");
  if (editor) {
    editor.scrollTop += 60;
  }
  SoundFX.tick();
  completeDojoChallenge("gaze-scroll");
}

// Agentic Prompt Simulation
function triggerAgenticPromptSim() {
  injectCodeIntoEditor(
    "# [Agentic Prompt Launcher & MCP Queue]\\n" +
    "# Tarea: Implementar optimización de landmarks con AST & NumPy\\n" +
    "# Diagnósticos: 0 errores, 1 advertencia de precisión subpíxel\\n" +
    "# Enviado a VS Code Chat y cola MCP local en 127.0.0.1:8765\\n"
  );
  completeDojoChallenge("agentic-mcp");
}

// Floating Gaze Reticle & Zero-Dwell Mouse Tracking
let reticleX = window.innerWidth / 2;
let reticleY = window.innerHeight / 2;
let targetX = reticleX;
let targetY = reticleY;

window.addEventListener("mousemove", (e) => {
  targetX = e.clientX;
  targetY = e.clientY;

  // Zero-Dwell rule: Looking / hovering ONLY focuses, NEVER triggers a click
  const el = document.elementFromPoint(e.clientX, e.clientY);
  const cell = el ? el.closest(".sim-cell") : null;
  if (cell !== hoveredCell) {
    if (hoveredCell) hoveredCell.classList.remove("gaze-focused");
    hoveredCell = cell;
    if (hoveredCell) {
      hoveredCell.classList.add("gaze-focused");
      SoundFX.tick();
      completeDojoChallenge("zero-dwell");
      if (hoveredCell.dataset && hoveredCell.dataset.cellIndex !== undefined) {
        const idx = Number(hoveredCell.dataset.cellIndex);
        const mode = (GUIDE.simulator || {})[currentMode];
        if (mode && mode.cells && mode.cells[idx]) {
          const info = document.getElementById("simInfo");
          if (info) {
            info.innerHTML = `<span class="mini-kicker">${mode.name.toUpperCase()} · ENFOQUE ZERO-DWELL (CASILLA ${idx + 1})</span><h4>${mode.cells[idx].label}</h4><p>${mode.cells[idx].hint}</p>`;
          }
        }
      }
    }
  }
});

function animateReticle() {
  const factor = isSniperActive ? 0.08 : 0.32;
  reticleX += (targetX - reticleX) * factor;
  reticleY += (targetY - reticleY) * factor;

  const reticle = document.getElementById("gazeReticle");
  if (reticle) {
    reticle.style.left = reticleX + "px";
    reticle.style.top = reticleY + "px";
  }
  requestAnimationFrame(animateReticle);
}
requestAnimationFrame(animateReticle);

// Global Keyboard Shortcuts
window.addEventListener("keydown", (e) => {
  if (e.code === "Space" && e.target.tagName !== "INPUT" && e.target.tagName !== "TEXTAREA" && !e.target.isContentEditable) {
    e.preventDefault();
    triggerMARClick();
  }
  if (e.altKey && e.ctrlKey && e.key.toLowerCase() === "z") {
    e.preventDefault();
    toggleSniperLens();
  }
  if (e.altKey && e.ctrlKey && e.key.toLowerCase() === "w") {
    e.preventDefault();
    triggerGazeScrollSim();
  }
  if (e.altKey && e.ctrlKey && e.key.toLowerCase() === "i") {
    e.preventDefault();
    triggerAgenticPromptSim();
  }
  if (e.altKey && e.ctrlKey && e.key.toLowerCase() === "o") {
    e.preventDefault();
    toggleTheme();
  }
});

// Initialize settings from localStorage
let initialTheme = "nintendo-booklet";
try {
  const savedTheme = localStorage.getItem("ideye_guide_theme");
  if (savedTheme === "cyber-glass" || savedTheme === "nintendo-booklet") initialTheme = savedTheme;
} catch (e) {}
applyTheme(initialTheme);
updateSoundUI();

// Restore Dojo progress
try {
  const savedProg = JSON.parse(localStorage.getItem("ideye_dojo_progress") || "[]");
  if (Array.isArray(savedProg)) {
    savedProg.forEach(id => completeDojoChallenge(id, true));
  }
} catch (e) {}
"""

CYBER_GLASS_CSS = """
/* ======================================================================
   CYBER-GLASS THEME - OLED Dark Mode with Translucent Glassmorphism
   ====================================================================== */
body[data-theme="cyber-glass"] {
  color: #e2e8f0;
  background-color: #030712;
  background-image:
    radial-gradient(at 0% 0%, rgba(var(--mode-accent-rgb), 0.16) 0px, transparent 55%),
    radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.12) 0px, transparent 55%),
    radial-gradient(circle at 50% 50%, rgba(15, 23, 42, 0.95), #030712);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
body[data-theme="cyber-glass"] .app {
  width: min(1360px, calc(100% - 32px));
}
body[data-theme="cyber-glass"] .hero {
  background: rgba(15, 23, 42, 0.65);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
body[data-theme="cyber-glass"] .brand h1 {
  background: linear-gradient(135deg, #fff 0%, #cbd5e1 50%, var(--mode-accent) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 800;
  letter-spacing: -0.03em;
}
body[data-theme="cyber-glass"] .btn {
  background: rgba(15, 23, 42, 0.7);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #e2e8f0;
  border-radius: 999px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
}
body[data-theme="cyber-glass"] .btn:hover {
  background: rgba(var(--mode-accent-rgb), 0.2);
  border-color: var(--mode-accent);
  color: #fff;
  box-shadow: 0 0 20px rgba(var(--mode-accent-rgb), 0.35);
}
body[data-theme="cyber-glass"] .tabs {
  gap: 10px;
}
body[data-theme="cyber-glass"] .tab {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #94a3b8;
  border-radius: 999px;
  padding: 10px 18px;
  font-weight: 700;
  transition: all 0.2s ease;
}
body[data-theme="cyber-glass"] .tab:hover {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.25);
  background: rgba(30, 41, 59, 0.6);
}
body[data-theme="cyber-glass"] .tab.active {
  background: var(--mode-accent);
  color: #030712;
  border-color: transparent;
  box-shadow: 0 0 25px rgba(var(--mode-accent-rgb), 0.5);
}
body[data-theme="cyber-glass"] .double-page-container {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 28px;
}
body[data-theme="cyber-glass"] .double-page-container > .page {
  display: flex !important;
  flex-direction: column;
  gap: 20px;
  padding: 0;
}
body[data-theme="cyber-glass"] .book-spine {
  display: none;
}
body[data-theme="cyber-glass"] .page-numbers {
  display: none;
}
body[data-theme="cyber-glass"] .ribbon {
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  border-left: 4px solid var(--mode-accent);
  border-radius: 14px;
  transform: none;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
  color: #f8fafc;
}
body[data-theme="cyber-glass"] .ribbon h2 {
  color: #f8fafc;
  -webkit-text-stroke: 0;
  text-shadow: none;
}
body[data-theme="cyber-glass"] .ribbon-star {
  color: var(--mode-accent);
}
body[data-theme="cyber-glass"] .intro {
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  padding: 16px 20px;
  color: #cbd5e1;
  transform: none;
  box-shadow: none;
}
body[data-theme="cyber-glass"] .card {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  transform: none !important;
}
body[data-theme="cyber-glass"] .card::before {
  display: none;
}
body[data-theme="cyber-glass"] .card:hover {
  border-color: var(--mode-accent);
  box-shadow: 0 0 25px rgba(var(--mode-accent-rgb), 0.25);
  transform: translateY(-3px) !important;
}
body[data-theme="cyber-glass"] .brush-title {
  background: transparent;
  color: #f1f5f9;
  -webkit-text-stroke: 0;
  text-shadow: none;
  border-radius: 0;
  border: none;
  padding: 0;
  margin: 12px 0 8px;
  transform: none;
  box-shadow: none;
  font-family: inherit;
  font-size: 18px;
}
body[data-theme="cyber-glass"] .illustration {
  background: rgba(2, 6, 23, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  outline: none;
  border-radius: 12px;
  box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.6);
  clip-path: none;
}
body[data-theme="cyber-glass"] .sticker {
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  background: rgba(var(--mode-accent-rgb), 0.2);
  color: var(--mode-accent);
  box-shadow: 0 0 15px rgba(var(--mode-accent-rgb), 0.3);
  transform: none;
  width: 44px;
  height: 44px;
  min-width: 44px;
  top: 12px;
  right: 12px;
}
body[data-theme="cyber-glass"] .sticker::after {
  display: none;
}
body[data-theme="cyber-glass"] .chip {
  background: rgba(var(--mode-accent-rgb), 0.15);
  color: var(--mode-accent);
  border: 1px solid rgba(var(--mode-accent-rgb), 0.3);
  border-radius: 999px;
  transform: none;
  box-shadow: none;
}
body[data-theme="cyber-glass"] .simulator {
  background: rgba(11, 19, 38, 0.65);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(var(--mode-accent-rgb), 0.3);
  border-radius: 20px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5), inset 0 0 30px rgba(var(--mode-accent-rgb), 0.08);
  transform: none;
}
body[data-theme="cyber-glass"] .sim-mode {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: #94a3b8;
  border-radius: 999px;
  transform: none;
  box-shadow: none;
}
body[data-theme="cyber-glass"] .sim-mode.active {
  background: var(--mode-accent);
  color: #030712;
  border-color: transparent;
  box-shadow: 0 0 15px rgba(var(--mode-accent-rgb), 0.4);
}
body[data-theme="cyber-glass"] .sim-cell {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: #e2e8f0;
  border-radius: 12px;
  transform: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  font-family: inherit;
}
body[data-theme="cyber-glass"] .sim-cell:hover,
body[data-theme="cyber-glass"] .sim-cell.selected {
  border-color: var(--mode-accent);
  background: rgba(var(--mode-accent-rgb), 0.15);
  box-shadow: 0 0 20px rgba(var(--mode-accent-rgb), 0.25);
  transform: translateY(-2px);
}
body[data-theme="cyber-glass"] .jaw-meter-container {
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  box-shadow: none;
}
body[data-theme="cyber-glass"] .vscode-pane {
  background: #030712;
  border: 1px solid rgba(255, 255, 255, 0.1);
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.6);
}
body[data-theme="cyber-glass"] .dojo-section {
  background: rgba(11, 19, 38, 0.65);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 20px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
}
body[data-theme="cyber-glass"] .dojo-card {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 14px;
  color: #e2e8f0;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
}
body[data-theme="cyber-glass"] .dojo-card.completed {
  background: rgba(34, 197, 94, 0.1);
  border-color: #22c55e;
  box-shadow: 0 0 20px rgba(34, 197, 94, 0.2);
}
body[data-theme="cyber-glass"] .dojo-badge {
  background: var(--mode-accent);
  color: #030712;
  border: none;
}
body[data-theme="cyber-glass"] .shortcut,
body[data-theme="cyber-glass"] .legal-item,
body[data-theme="cyber-glass"] .gesture-card {
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  color: #cbd5e1;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.25);
  transform: none !important;
}
body[data-theme="cyber-glass"] .legal-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.1);
  background: transparent;
  box-shadow: none;
  transform: none;
}
@media (max-width: 980px) {
  body[data-theme="cyber-glass"] .double-page-container {
    grid-template-columns: 1fr;
    gap: 20px;
  }
}
"""

NINTENDO_CSS = """
/* ======================================================================
   NINTENDO BOOKLET THEME - hand-made paper spread, no external assets
   ====================================================================== */
body[data-theme="nintendo-booklet"] {
  color: #172033;
  background-color: #5f3824;
  background-image:
    radial-gradient(circle at 3% 8%, rgba(255,255,255,.96) 0 3.2%, transparent 3.6%),
    radial-gradient(circle at 13% 20%, rgba(255,255,255,.92) 0 2.1%, transparent 2.6%),
    radial-gradient(circle at 7% 15%, rgba(255,255,255,.9) 0 1.3%, transparent 1.8%),
    radial-gradient(circle at 94% 12%, rgba(255,255,255,.9) 0 2.4%, transparent 2.9%),
    radial-gradient(circle at 86% 22%, rgba(255,255,255,.82) 0 1.4%, transparent 1.9%),
    radial-gradient(circle at 96% 76%, rgba(250,204,21,.95) 0 4.2%, transparent 4.6%),
    radial-gradient(circle at 5% 82%, rgba(225,29,72,.9) 0 3.8%, transparent 4.2%),
    radial-gradient(circle at 8% 94%, rgba(250,204,21,.9) 0 1.3%, transparent 1.8%),
    repeating-linear-gradient(90deg, rgba(0,0,0,.08) 0 2px, transparent 2px 86px),
    linear-gradient(90deg, #6e432b 0%, #815134 38%, #603722 100%);
  font-family: "Trebuchet MS", "Comic Sans MS", "Segoe UI", sans-serif;
}
body[data-theme="nintendo-booklet"]::before {
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  opacity: .55;
  background:
    linear-gradient(98deg, transparent 0 9%, rgba(255,255,255,.12) 9% 10%, transparent 10% 100%),
    radial-gradient(circle at 98% 45%, #facc15 0 18px, transparent 19px),
    radial-gradient(circle at 4% 52%, #facc15 0 14px, transparent 15px);
}
body[data-theme="nintendo-booklet"] .app {
  position: relative;
  z-index: 1;
  width: min(1420px, calc(100% - 24px));
  padding-top: 18px;
}
body[data-theme="nintendo-booklet"] .hero {
  position: relative;
  border: 5px solid #111;
  border-radius: 10px;
  background:
    repeating-linear-gradient(0deg, rgba(0,0,0,.025) 0 2px, transparent 2px 7px),
    linear-gradient(135deg, #fffdf5 0%, #f8e3a8 52%, #f3cf72 100%);
  box-shadow: 10px 10px 0 #111, 0 22px 50px rgba(0,0,0,.28);
  color: #111;
  transform: rotate(-.55deg);
  padding: 20px 24px;
}
body[data-theme="nintendo-booklet"] .hero::before,
body[data-theme="nintendo-booklet"] .hero::after {
  content: "";
  position: absolute;
  top: -16px;
  width: 86px;
  height: 28px;
  background: rgba(255,255,255,.62);
  border: 1px solid rgba(17,17,17,.18);
  box-shadow: 1px 2px 2px rgba(0,0,0,.16);
  z-index: 0;
}
body[data-theme="nintendo-booklet"] .hero::before { left: 9%; transform: rotate(-9deg); }
body[data-theme="nintendo-booklet"] .hero::after { right: 8%; transform: rotate(7deg); }
body[data-theme="nintendo-booklet"] .brand h1 {
  color: #b91c2c;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-size: clamp(24px, 3.2vw, 38px);
  font-weight: 900;
  letter-spacing: -.045em;
  line-height: 1.22;
  -webkit-text-stroke: 1.5px #111;
  text-shadow: 3px 3px 0 #111;
  text-wrap: balance;
  position: relative;
  z-index: 3;
}
body[data-theme="nintendo-booklet"] .brand {
  position: relative;
  z-index: 3;
}
body[data-theme="nintendo-booklet"] .hero-actions {
  position: relative;
  z-index: 3;
}
body[data-theme="nintendo-booklet"] .brand p {
  color: #242424;
  font-weight: 900;
  letter-spacing: .02em;
}
body[data-theme="nintendo-booklet"] .brand-icon-frame {
  background: #fffdf7;
  color: #111;
  border: 3px solid #111;
  border-radius: 50%;
  box-shadow: 4px 4px 0 #111;
}
body[data-theme="nintendo-booklet"] .btn {
  border: 3px solid #111;
  background: #facc15;
  color: #111;
  border-radius: 6px;
  box-shadow: 4px 4px 0 #111;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-weight: 900;
  transform: rotate(-.5deg);
}
body[data-theme="nintendo-booklet"] .btn:hover { background: #fde047; transform: translate(-1px,-1px) rotate(-.5deg); }
body[data-theme="nintendo-booklet"] .theme-toggle { background: #22c55e; color: #fff; }
body[data-theme="nintendo-booklet"] .tabs {
  position: relative;
  z-index: 2;
  gap: 7px;
  margin: 24px 8px 0;
  align-items: flex-end;
}
body[data-theme="nintendo-booklet"] .tab {
  border: 3px solid #111;
  border-bottom-width: 6px;
  background: #fef3c7;
  color: #111;
  border-radius: 11px 11px 4px 4px;
  box-shadow: 4px 4px 0 #111;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-weight: 900;
  padding: 10px 16px;
  transform: rotate(-1.2deg);
  min-height: 44px;
}
body[data-theme="nintendo-booklet"] .tab:nth-child(1) { background: #ef4444; color: #fff; transform: rotate(-1.8deg); }
body[data-theme="nintendo-booklet"] .tab:nth-child(2) { background: #fde047; color: #111; transform: rotate(.7deg); }
body[data-theme="nintendo-booklet"] .tab:nth-child(3) { background: #86efac; color: #111; transform: rotate(-.4deg); }
body[data-theme="nintendo-booklet"] .tab:nth-child(4) { background: #93c5fd; color: #111; transform: rotate(1deg); }
body[data-theme="nintendo-booklet"] .tab:nth-child(5) { background: #f9a8d4; color: #111; transform: rotate(-.9deg); }
body[data-theme="nintendo-booklet"] .tab.active {
  background: #b91c2c;
  color: #facc15;
  border-color: #111;
  box-shadow: 5px 5px 0 #111;
  transform: translateY(4px) rotate(-1deg);
}
body[data-theme="nintendo-booklet"] .page.active {
  position: relative;
  display: block;
  padding: 20px 28px 64px;
  border: 8px solid #fff;
  border-radius: 8px;
  outline: 4px solid #111;
  box-shadow: 12px 12px 0 #111, 0 28px 70px rgba(0,0,0,.34);
  background:
    radial-gradient(circle at 8% 8%, rgba(255,249,217,.9) 0 6%, transparent 7%),
    radial-gradient(circle at 92% 96%, rgba(232,247,201,.65) 0 9%, transparent 10%),
    repeating-linear-gradient(0deg, rgba(80,60,40,.035) 0 1px, transparent 1px 5px),
    linear-gradient(90deg, #fffdf7 0 49.65%, #fffdf7 50.35% 100%);
  transform: rotate(.15deg);
}
body[data-theme="nintendo-booklet"] .double-page-container {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 48px;
  width: 100%;
  max-width: 1400px;
  margin: 0 auto;
}
body[data-theme="nintendo-booklet"] .double-page-container > .page {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 20px 40px;
  box-sizing: border-box;
  width: 100%;
  min-height: 100%;
}
body[data-theme="nintendo-booklet"] .book-spine {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 32px;
  transform: translateX(-50%);
  pointer-events: none;
  z-index: 10;
  background: linear-gradient(to right, rgba(0,0,0,.03), rgba(0,0,0,.12) 35%, rgba(0,0,0,.18) 50%, rgba(0,0,0,.12) 65%, rgba(0,0,0,.03));
}
body[data-theme="nintendo-booklet"] .book-spine::before,
body[data-theme="nintendo-booklet"] .book-spine::after {
  content: "";
  position: absolute;
  top: 0;
  bottom: 0;
  width: 1px;
  border-left: 2px dashed rgba(0,0,0,.15);
}
body[data-theme="nintendo-booklet"] .book-spine::before { left: 4px; }
body[data-theme="nintendo-booklet"] .book-spine::after { right: 4px; }
body[data-theme="nintendo-booklet"] .cards-subgrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 20px;
  width: 100%;
}
body[data-theme="nintendo-booklet"] .cards-subgrid.mechanics { margin-top: 4px; }
body[data-theme="nintendo-booklet"] .tab-navigation {
  margin-top: 16px;
  margin-bottom: 24px;
}
body[data-theme="nintendo-booklet"] .ribbon {
  position: relative;
  z-index: 2;
  display: block;
  width: calc(100% - 8px);
  margin: 2px 0 18px 4px;
  padding: 17px 20px 17px 54px;
  border: 4px solid #111;
  border-radius: 4px;
  background:
    repeating-linear-gradient(0deg, rgba(0,0,0,.06) 0 2px, transparent 2px 8px),
    #d21f2b;
  color: #facc15;
  transform: rotate(-2.1deg);
  box-shadow: 9px 9px 0 #111;
  clip-path: polygon(1% 3%, 98% 0, 100% 91%, 2% 100%);
  isolation: isolate;
}
body[data-theme="nintendo-booklet"] .ribbon::before {
  content: "";
  position: absolute;
  inset: 8px -14px -9px 13px;
  background: #facc15;
  z-index: -1;
  transform: rotate(2.2deg);
  clip-path: polygon(1% 7%, 100% 0, 98% 92%, 0 100%);
}
body[data-theme="nintendo-booklet"] .ribbon-star {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%) rotate(-10deg);
  color: #facc15;
  width: 36px;
  height: 36px;
  filter: drop-shadow(2px 2px 0 #111);
  z-index: 2;
}
body[data-theme="nintendo-booklet"] .ribbon-star .ui-icon { width: 36px; height: 36px; stroke-width: 2.2; }
body[data-theme="nintendo-booklet"] .kicker {
  color: #fde68a;
  opacity: 1;
  font-size: 10px;
  letter-spacing: .13em;
  text-shadow: 1px 1px 0 #111;
}
body[data-theme="nintendo-booklet"] .ribbon h2 {
  color: #fff;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-size: clamp(25px, 3.7vw, 44px);
  font-weight: 900;
  line-height: .98;
  -webkit-text-stroke: 2px #111;
  text-shadow: 3px 3px 0 #111, 5px 5px 0 #facc15;
}
body[data-theme="nintendo-booklet"] .intro {
  color: #1e293b;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-size: 16px;
  font-weight: 800;
  line-height: 1.55;
  max-width: 640px;
  padding: 15px 17px;
  border: 3px solid #111;
  background:
    repeating-linear-gradient(0deg, transparent 0 25px, rgba(59,130,246,.12) 25px 26px),
    #fffdf7;
  box-shadow: 5px 5px 0 #111;
  transform: rotate(.6deg);
}
body[data-theme="nintendo-booklet"] .card-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 34px 24px;
  padding-top: 6px;
}
body[data-theme="nintendo-booklet"] .card {
  overflow: visible;
  min-height: 310px;
  padding: 18px 22px;
  border: 4px solid #111;
  border-radius: 6px;
  background:
    repeating-linear-gradient(0deg, rgba(0,0,0,.025) 0 2px, transparent 2px 7px),
    #fffdf7;
  box-shadow: 8px 8px 0 rgba(0,0,0,.82);
  transform: rotate(-1.1deg);
  transition: transform .18s cubic-bezier(.2,1.6,.4,1), box-shadow .18s ease;
}
body[data-theme="nintendo-booklet"] .card::before {
  content: "";
  position: absolute;
  top: -14px;
  left: 18px;
  width: 82px;
  height: 24px;
  background: rgba(255,255,255,.6);
  border: 1px solid rgba(17,17,17,.16);
  transform: rotate(-7deg);
  z-index: 6;
}
body[data-theme="nintendo-booklet"] .card.card-1 { transform: rotate(1.2deg); }
body[data-theme="nintendo-booklet"] .card:hover {
  transform: rotate(0deg) scale(1.025);
  box-shadow: 12px 12px 0 rgba(0,0,0,.86);
  z-index: 8;
}
body[data-theme="nintendo-booklet"] .card::after { display: none; }
body[data-theme="nintendo-booklet"] .card-icon { margin: 0 0 12px; }
body[data-theme="nintendo-booklet"] .illustration {
  position: relative;
  overflow: hidden;
  height: 158px;
  display: grid;
  place-items: center;
  color: #fff;
  background:
    radial-gradient(circle at 76% 18%, #fff7a8 0 11%, transparent 12%),
    repeating-conic-gradient(from -8deg at 72% 40%, rgba(255,255,255,.28) 0 6deg, transparent 6deg 16deg),
    linear-gradient(145deg, var(--accent), #38bdf8 62%, #22c55e 100%);
  border: 6px solid #fff;
  outline: 4px solid #111;
  box-shadow: 6px 6px 0 #111;
  clip-path: polygon(3% 0, 97% 0, 100% 12%, 100% 100%, 0 100%, 0 12%);
}
body[data-theme="nintendo-booklet"] .illustration::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(255,255,255,.85) 1px, transparent 1.5px);
  background-size: 12px 12px;
  opacity: .28;
  pointer-events: none;
}
body[data-theme="nintendo-booklet"] .illustration .icon {
  position: relative;
  z-index: 2;
  width: 90px;
  height: 90px;
  filter: drop-shadow(4px 4px 0 #111);
}
body[data-theme="nintendo-booklet"] .comic-bubble {
  position: absolute;
  top: 9px;
  left: 10px;
  z-index: 5;
  padding: 8px 11px 9px;
  background: #fff;
  color: #111;
  border: 3px solid #111;
  border-radius: 45% 55% 48% 52% / 52% 46% 54% 48%;
  box-shadow: 3px 3px 0 #111;
  font-size: 13px;
  font-weight: 900;
  line-height: 1;
  transform: rotate(-7deg);
}
body[data-theme="nintendo-booklet"] .comic-bubble::after {
  content: "";
  position: absolute;
  right: 9px;
  bottom: -9px;
  width: 14px;
  height: 14px;
  background: #fff;
  border-right: 3px solid #111;
  border-bottom: 3px solid #111;
  transform: rotate(28deg);
}
body[data-theme="nintendo-booklet"] .comic-star {
  position: absolute;
  right: 10px;
  top: 10px;
  z-index: 5;
  width: 26px;
  height: 26px;
  color: #facc15;
  filter: drop-shadow(2px 2px 0 #111);
  transform: rotate(12deg);
}
body[data-theme="nintendo-booklet"] .comic-star .ui-icon { width: 26px; height: 26px; }
body[data-theme="nintendo-booklet"] .action-arrow {
  position: absolute;
  right: 10px;
  bottom: 8px;
  z-index: 5;
  width: 44px;
  height: 32px;
  color: #fff;
  filter: drop-shadow(2px 2px 0 #111);
}
body[data-theme="nintendo-booklet"] .sticker {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  top: -24px;
  right: -14px;
  width: 66px;
  height: 66px;
  min-width: 66px;
  border: 4px solid #fff;
  background: #22c55e;
  color: #fff;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-size: 13px;
  font-weight: 900;
  text-shadow: 1px 1px 0 #111;
  box-shadow: 5px 5px 0 rgba(0,0,0,.55);
  z-index: 9;
  transform: rotate(8deg);
}
body[data-theme="nintendo-booklet"] .sticker::after {
  content: "";
  position: absolute;
  inset: 5px;
  border: 2px dashed rgba(255,255,255,.72);
  border-radius: 50%;
}
body[data-theme="nintendo-booklet"] .card:nth-child(even) .sticker { background: #facc15; color: #111; }
body[data-theme="nintendo-booklet"] .sticker .ui-icon { width: 16px; height: 16px; stroke-width: 2.4; }
body[data-theme="nintendo-booklet"] .sticker span { font-size: 9px; line-height: 1; }
body[data-theme="nintendo-booklet"] .brush-title {
  position: relative;
  top: auto;
  left: auto;
  right: auto;
  margin: 26px 0 12px;
  z-index: 7;
  min-height: 44px;
  padding: 10px 14px 11px;
  background: #16a34a;
  color: #fff;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-size: clamp(13px, 1.3vw, 16px);
  font-weight: 900;
  line-height: 1.15;
  text-align: left;
  overflow: visible;
  overflow-wrap: anywhere;
  -webkit-text-stroke: 1.4px #000;
  text-shadow: 1px 2px 0 #000;
  transform: rotate(-1.2deg);
  box-shadow: 4px 4px 0 #111;
}
body[data-theme="nintendo-booklet"] .card-1 .brush-title { background: #f59e0b; color: #111; -webkit-text-stroke: 1.2px #111; text-shadow: 2px 2px 0 #fff; }
body[data-theme="nintendo-booklet"] .brush-title span { display: block; }
body[data-theme="nintendo-booklet"] .card p {
  color: #1e293b;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.45;
}
body[data-theme="nintendo-booklet"] .chip {
  border: 2px solid #111;
  background: #fef3c7;
  color: #111;
  border-radius: 4px;
  box-shadow: 2px 2px 0 #111;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-weight: 900;
  transform: rotate(-1deg);
}
body[data-theme="nintendo-booklet"] .threshold-row span,
body[data-theme="nintendo-booklet"] .gesture-card,
body[data-theme="nintendo-booklet"] .shortcut,
body[data-theme="nintendo-booklet"] .legal-item {
  border: 3px solid #111;
  background:
    repeating-linear-gradient(0deg, rgba(0,0,0,.02) 0 2px, transparent 2px 7px),
    #fffdf7;
  color: #1e293b;
  box-shadow: 5px 5px 0 #111;
  border-radius: 6px;
}
body[data-theme="nintendo-booklet"] .threshold-row span,
body[data-theme="nintendo-booklet"] .shortcut { transform: rotate(-.7deg); }
body[data-theme="nintendo-booklet"] .threshold-row span:nth-child(even),
body[data-theme="nintendo-booklet"] .shortcut:nth-child(even) { transform: rotate(.7deg); }
body[data-theme="nintendo-booklet"] .threshold-row b,
body[data-theme="nintendo-booklet"] .gesture-card strong { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .gesture-card p,
body[data-theme="nintendo-booklet"] .shortcut span,
body[data-theme="nintendo-booklet"] .legal-item p { color: #334155; }
body[data-theme="nintendo-booklet"] .gesture-icon,
body[data-theme="nintendo-booklet"] .legal-icon { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .gesture-icon {
  background: #fff;
  border: 3px solid #111;
  padding: 5px;
  box-shadow: 3px 3px 0 #111;
  transform: rotate(-4deg);
}
body[data-theme="nintendo-booklet"] .simulator {
  border: 4px solid #111;
  background:
    repeating-linear-gradient(0deg, rgba(0,0,0,.025) 0 2px, transparent 2px 7px),
    #fffdf7;
  box-shadow: 8px 8px 0 #111;
  transform: rotate(-.3deg);
}
body[data-theme="nintendo-booklet"] .sim-heading h3,
body[data-theme="nintendo-booklet"] .mini-kicker { color: #111; }
body[data-theme="nintendo-booklet"] .sim-mode {
  border: 2px solid #111;
  background: #fef3c7;
  color: #111;
  border-radius: 5px;
  box-shadow: 3px 3px 0 #111;
  font-weight: 900;
  transform: rotate(-1deg);
}
body[data-theme="nintendo-booklet"] .sim-mode.active { background: #b91c2c; color: #facc15; }
body[data-theme="nintendo-booklet"] .sim-cell {
  border: 3px solid #111;
  background:
    repeating-linear-gradient(0deg, transparent 0 21px, rgba(59,130,246,.12) 21px 22px),
    #fff7d6;
  color: #111;
  box-shadow: 4px 4px 0 #111;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  transform: rotate(-.6deg);
}
body[data-theme="nintendo-booklet"] .sim-cell:nth-child(even) { transform: rotate(.6deg); }
body[data-theme="nintendo-booklet"] .sim-cell small { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .sim-info {
  border: 3px solid #111;
  background: #fffdf7;
  box-shadow: 5px 5px 0 #111;
}
body[data-theme="nintendo-booklet"] .sim-info h4 { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .sim-info p { color: #1e293b; }
body[data-theme="nintendo-booklet"] .shortcut-grid { gap: 14px; margin-top: 22px; }
body[data-theme="nintendo-booklet"] .shortcut { gap: 11px; padding: 12px 13px; }
body[data-theme="nintendo-booklet"] .pager { gap: 10px; padding-top: 28px; }
body[data-theme="nintendo-booklet"] .pager .btn,
body[data-theme="nintendo-booklet"] .page-dot {
  border: 3px solid #111;
  background: #fffdf7;
  color: #111;
  box-shadow: 4px 4px 0 #111;
}
body[data-theme="nintendo-booklet"] .page-dot.active { background: #b91c2c; color: #facc15; }
body[data-theme="nintendo-booklet"] .page-label { color: #fffdf7; font-weight: 900; text-shadow: 2px 2px 0 #111; }
body[data-theme="nintendo-booklet"] .legal-footer {
  margin-top: 28px;
  border: 4px solid #111;
  background: #fffdf7;
  box-shadow: 8px 8px 0 #111;
  padding: 18px;
  transform: rotate(-.3deg);
}
body[data-theme="nintendo-booklet"] .build-stamp { color: #334155; font-weight: 800; }
body[data-theme="nintendo-booklet"] kbd {
  border: 2px solid #111;
  background: #fef3c7;
  color: #111;
  border-bottom-width: 4px;
  box-shadow: 3px 3px 0 #111;
}
body[data-theme="nintendo-booklet"] .page-numbers span {
  position: absolute;
  bottom: 8px;
  color: #fff;
  font-family: "Trebuchet MS", "Comic Sans MS", sans-serif;
  font-size: 30px;
  font-weight: 900;
  -webkit-text-stroke: 2px #000;
  text-shadow: 4px 4px 0 #000;
  z-index: 6;
  transform: rotate(-5deg);
}
body[data-theme="nintendo-booklet"] .page-numbers span:first-child { left: 24px; }
body[data-theme="nintendo-booklet"] .page-numbers span:last-child { right: 24px; transform: rotate(5deg); }
body[data-theme="nintendo-booklet"] .sound-toggle { background: #38bdf8; color: #111; }
body[data-theme="nintendo-booklet"] .sim-workspace { gap: 20px; }
body[data-theme="nintendo-booklet"] .jaw-meter-container { border: 3px solid #111; background: #fffdf5; box-shadow: 4px 4px 0 #111; }
body[data-theme="nintendo-booklet"] .jaw-value { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .jaw-track { background: #f1f5f9; border: 2px solid #111; }
body[data-theme="nintendo-booklet"] .sim-action-btn { border: 2px solid #111; background: #fef3c7; color: #111; font-weight: 800; box-shadow: 2px 2px 0 #111; }
body[data-theme="nintendo-booklet"] .sim-action-btn:hover { background: #fde047; }
body[data-theme="nintendo-booklet"] .vscode-pane { background: #182234; border: 4px solid #111; box-shadow: 6px 6px 0 #111; color: #f8fafc; }
body[data-theme="nintendo-booklet"] .vsc-titlebar { background: #0f172a; border-bottom: 2px solid #111; }
body[data-theme="nintendo-booklet"] .vsc-tab { background: #1e293b; color: #f8fafc; border-top: 3px solid #b91c2c; }
body[data-theme="nintendo-booklet"] .vsc-btn { border: 2px solid #111; background: #fde047; color: #111; font-weight: 900; }
body[data-theme="nintendo-booklet"] .vsc-btn:hover { background: #facc15; }
body[data-theme="nintendo-booklet"] .vsc-editor-body { background: #0b1322; color: #f8fafc; }
body[data-theme="nintendo-booklet"] .vsc-line-numbers { background: #0e1726; border-right: 2px solid #111; color: #94a3b8; }
body[data-theme="nintendo-booklet"] .vsc-code-content { color: #f8fafc; }
body[data-theme="nintendo-booklet"] .vsc-statusbar { background: #facc15; color: #111; border-top: 3px solid #111; }
body[data-theme="nintendo-booklet"] .dojo-section { border: 4px solid #111; background: #fffdf5; box-shadow: 8px 8px 0 #111; }
body[data-theme="nintendo-booklet"] .dojo-header { border-bottom: 3px solid #111; }
body[data-theme="nintendo-booklet"] .dojo-trophy-icon { border: 2px solid #111; box-shadow: 2px 2px 0 #111; }
body[data-theme="nintendo-booklet"] .dojo-meter { border: 2px solid #111; background: #f1f5f9; }
body[data-theme="nintendo-booklet"] .dojo-card { border: 3px solid #111; background: #fffdf7; box-shadow: 4px 4px 0 #111; color: #111; }
body[data-theme="nintendo-booklet"] .dojo-card.completed { background: #f0fdf4; border-color: #16a34a; }
body[data-theme="nintendo-booklet"] .dojo-badge { border: 1px solid #111; background: #fde047; color: #111; }
body[data-theme="nintendo-booklet"] .dojo-card p { color: #334155; }
body[data-theme="nintendo-booklet"] .dojo-action-btn { border: 2px solid #111; background: #facc15; color: #111; font-weight: 800; box-shadow: 2px 2px 0 #111; }
body[data-theme="nintendo-booklet"] .dojo-celebration { border: 3px solid #111; background: #fef08a; box-shadow: 4px 4px 0 #111; color: #111; }
body[data-theme="nintendo-booklet"] .celebration-badge { border: 2px solid #111; }
body[data-theme="nintendo-booklet"] .celebration-text h4 { color: #b91c2c; }
body[data-theme="nintendo-booklet"] .celebration-text p { color: #111; }
@media (max-width: 980px) and (min-width: 641px) {
  body[data-theme="nintendo-booklet"] .page.active { padding: 18px 18px 58px; }
  body[data-theme="nintendo-booklet"] .double-page-container { gap: 28px; }
  body[data-theme="nintendo-booklet"] .double-page-container > .page { padding: 16px 22px; gap: 18px; }
  body[data-theme="nintendo-booklet"] .cards-subgrid { grid-template-columns: 1fr; gap: 18px; }
}
@media (max-width: 640px) {
  body[data-theme="nintendo-booklet"] .page.active { padding: 22px 14px 58px; }
  body[data-theme="nintendo-booklet"] .double-page-container { grid-template-columns: 1fr; gap: 24px; }
  body[data-theme="nintendo-booklet"] .double-page-container > .page { padding: 12px 8px; }
  body[data-theme="nintendo-booklet"] .book-spine { display: none; }
  body[data-theme="nintendo-booklet"] .cards-subgrid { grid-template-columns: 1fr; }
}
@media print {
  body[data-theme="nintendo-booklet"] { background: #fff !important; }
  body[data-theme="nintendo-booklet"] .page.active { display: block; box-shadow: none; outline: 2px solid #555; }
  body[data-theme="nintendo-booklet"] .double-page-container { grid-template-columns: 1fr 1fr; gap: 36px; }
  body[data-theme="nintendo-booklet"] .book-spine { opacity: .45; }
  body[data-theme="nintendo-booklet"] .hero { box-shadow: none; }
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
            extra = _simulator(simulator, catalog.get("dojo_challenges", [])) + _shortcut_grid(catalog.get("shortcuts", []))
        if page_id == "custom":
            extra = _shortcut_grid(catalog.get("shortcuts", []))
        page_cards = list(page.get("cards", []))
        left_count = 2 if len(page_cards) <= 6 else (len(page_cards) + 1) // 2
        left_cards = _cards(page_cards[:left_count], accent)
        right_cards = page_cards[left_count:]
        right_primary = _cards(right_cards[:2], accent)
        right_mechanics = _cards(right_cards[2:], accent) if len(right_cards) > 2 else ""
        mechanics_block = (
            f'<div class="cards-subgrid mechanics">{right_mechanics}</div>'
            if right_mechanics
            else ""
        )
        sections.append(
            f'''
            <section class="page{active}" data-page="{index}" id="{_esc(page_id)}">
              <div class="double-page-container">
                <div class="page page-left">
                  <div class="ribbon" style="--ribbon:{accent}">
                    <span class="ribbon-star">{_ui_icon("star-badge")}</span>
                    <span class="kicker">{_esc(page.get("kicker", ""))}</span>
                    <h2>{_esc(page.get("title", ""))}</h2>
                  </div>
                  <p class="intro">{_esc(page.get("intro", ""))}</p>
                  <div class="cards-subgrid">{left_cards}</div>
                </div>
                <div class="page page-right">
                  <div class="cards-subgrid">{right_primary}</div>
                  {mechanics_block}
                  {extra}
                </div>
                <div class="book-spine" aria-hidden="true"></div>
              </div>
              <div class="page-numbers"><span>{index * 2 + 11}</span><span>{index * 2 + 12}</span></div>
            </section>'''
        )

    pager = "\n".join(
        f'<button class="page-dot{" active" if index == 0 else ""}" data-page-target="{index}">{index + 1}</button>'
        for index in range(len(pages))
    )
    html = f'''<!DOCTYPE html>
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
  --mode-accent:#06b6d4; --mode-accent-rgb:6, 182, 212;
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
.double-page-container {{ display:grid; grid-template-columns:minmax(0, 1fr) minmax(0, 1fr); gap:28px; width:100%; }}
.double-page-container > .page {{ display:flex !important; flex-direction:column; gap:20px; width:100%; }}
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
.sim-workspace {{ display:grid; grid-template-columns:minmax(300px, 1fr) minmax(360px, 1.25fr); gap:18px; margin-top:16px; }}
.sim-left-pane, .sim-right-pane {{ display:flex; flex-direction:column; gap:14px; }}
.sim-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:8px; }}
.sim-cell {{ min-height:82px; border:1px solid #31435e; border-radius:12px; background:linear-gradient(150deg,#15233b,#0f172a); color:#dbeafe; padding:8px; text-align:left; font-weight:800; font-size:12px; line-height:1.25; box-shadow:2px 2px 0 rgba(0,0,0,.35); }}
.sim-cell:hover, .sim-cell.selected {{ border-color:var(--yellow); background:linear-gradient(150deg,#263651,#15233b); transform:translateY(-2px); }}
.sim-cell small {{ display:block; color:#7dd3fc; font-size:10px; font-weight:600; margin-top:4px; }}
.sim-info {{ border:1px solid var(--line); border-radius:14px; padding:15px; background:#0d1729; min-height:100px; }}
.sim-info h4 {{ margin:3px 0 8px; color:var(--yellow); font-size:20px; }}
.sim-info p {{ margin:0; color:#b6c2d6; line-height:1.55; font-size:14px; }}
.jaw-meter-container {{ border:1px solid var(--line); border-radius:14px; padding:14px; background:#0d1729; }}
.jaw-meter-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
.jaw-value {{ font-size:11px; font-weight:800; color:var(--mode-accent, var(--cyan)); }}
.jaw-value.triggered {{ color:#22c55e; }}
.jaw-track {{ position:relative; height:14px; background:#1e293b; border-radius:999px; border:1px solid #334155; }}
.jaw-fill {{ height:100%; background:linear-gradient(90deg, #22c55e, var(--mode-accent, var(--cyan))); border-radius:999px; transition:width .14s ease; }}
.jaw-fill.triggered {{ background:linear-gradient(90deg, #eab308, #ef4444); box-shadow:0 0 12px #ef4444; }}
.jaw-threshold-line {{ position:absolute; top:-3px; bottom:-3px; width:2px; background:#ef4444; }}
.threshold-label {{ position:absolute; top:-16px; left:-10px; font-size:9px; color:#ef4444; font-weight:900; }}
.jaw-actions {{ display:grid; grid-template-columns:repeat(2, 1fr); gap:6px; margin-top:10px; }}
.sim-action-btn {{ font-size:11px; padding:7px 10px; justify-content:flex-start; text-align:left; }}
.sim-action-btn.active {{ border-color:var(--yellow); color:var(--yellow); }}
.vscode-pane {{ display:flex; flex-direction:column; border-radius:14px; overflow:hidden; background:#0b1120; color:#e2e8f0; border:1px solid var(--line); box-shadow:0 14px 40px rgba(0,0,0,.45); font-family:ui-monospace,SFMono-Regular,"Cascadia Code","Roboto Mono",Consolas,monospace; min-height:400px; }}
.vsc-titlebar {{ display:flex; align-items:center; justify-content:space-between; background:#0f172a; border-bottom:1px solid var(--line); padding:6px 12px; gap:8px; flex-wrap:wrap; }}
.vsc-tabs {{ display:flex; gap:4px; }}
.vsc-tab {{ display:flex; align-items:center; gap:6px; padding:5px 12px; background:#0b1120; border-top:2px solid var(--mode-accent, var(--cyan)); color:#f8fafc; font-size:12px; border-radius:4px 4px 0 0; }}
.vsc-tab-icon {{ width:14px; height:14px; }}
.vsc-tab-close {{ opacity:.6; cursor:pointer; margin-left:4px; }}
.vsc-breadcrumbs {{ font-size:11px; color:#64748b; flex:1; }}
.vsc-actions {{ display:flex; gap:5px; }}
.vsc-btn {{ background:#1e293b; color:#cbd5e1; border:1px solid #334155; border-radius:6px; padding:4px 8px; font-size:11px; display:inline-flex; align-items:center; gap:4px; cursor:pointer; font-weight:700; }}
.vsc-btn:hover {{ background:#334155; color:#fff; }}
.vsc-btn-primary {{ background:var(--mode-accent, var(--cyan)); color:#05101a; border-color:transparent; }}
.vsc-editor-body {{ display:flex; flex:1; min-height:280px; max-height:360px; overflow-y:auto; background:#070d19; }}
.vsc-line-numbers {{ padding:12px 10px; color:#475569; text-align:right; user-select:none; font-size:12px; line-height:1.6; border-right:1px solid #1e293b; display:flex; flex-direction:column; background:#0a101d; }}
.vsc-code-content {{ margin:0; padding:12px 14px; flex:1; font-size:12.5px; line-height:1.6; white-space:pre-wrap; word-break:break-word; outline:none; color:#f1f5f9; overflow-x:auto; }}
.syn-kw {{ color:#f43f5e; font-weight:700; }}
.syn-fn {{ color:#c084fc; }}
.syn-str {{ color:#34d399; }}
.syn-com {{ color:#64748b; font-style:italic; }}
.syn-num {{ color:#38bdf8; }}
.vsc-statusbar {{ display:flex; justify-content:space-between; align-items:center; background:var(--mode-accent, var(--cyan)); color:#06111f; padding:4px 12px; font-size:11px; font-weight:800; transition:background .25s ease; }}
.vsc-status-left, .vsc-status-right {{ display:flex; gap:14px; align-items:center; }}
.vsc-dot {{ width:8px; height:8px; background:#22c55e; border-radius:50%; display:inline-block; box-shadow:0 0 6px #22c55e; }}
.dojo-section {{ margin-top:22px; padding:20px; border-radius:18px; background:#0c1527; border:1px solid var(--line); box-shadow:0 12px 40px rgba(0,0,0,.3); }}
.dojo-header {{ display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:16px; border-bottom:1px solid var(--line); padding-bottom:16px; margin-bottom:16px; }}
.dojo-title-box {{ display:flex; align-items:center; gap:14px; }}
.dojo-trophy-icon {{ width:44px; height:44px; border-radius:12px; background:linear-gradient(135deg,#fbbf24,#f59e0b); color:#111; display:grid; place-items:center; flex-shrink:0; }}
.dojo-trophy-icon .ui-icon {{ width:24px; height:24px; }}
.dojo-progress-box {{ min-width:210px; }}
.dojo-progress-label {{ display:flex; justify-content:space-between; font-size:12px; margin-bottom:6px; }}
.dojo-meter {{ height:10px; border-radius:999px; background:#1e293b; overflow:hidden; border:1px solid #334155; }}
.dojo-meter-fill {{ height:100%; background:linear-gradient(90deg,#22c55e,#10b981); transition:width .3s ease; }}
.dojo-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(270px,1fr)); gap:12px; }}
.dojo-card {{ padding:15px; border-radius:14px; background:rgba(15,23,42,.8); border:1px solid var(--line); display:flex; flex-direction:column; justify-content:space-between; transition:transform .18s ease,border-color .18s ease; }}
.dojo-card:hover {{ transform:translateY(-2px); border-color:var(--mode-accent, var(--cyan)); }}
.dojo-card.completed {{ border-color:#22c55e; background:rgba(34,197,94,.08); }}
.dojo-card-header {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
.dojo-badge {{ font-size:10px; font-weight:900; padding:2px 7px; border-radius:999px; background:var(--mode-accent, var(--cyan)); color:#05101a; }}
.dojo-kicker {{ font-size:10px; color:var(--muted); font-weight:800; }}
.dojo-status {{ font-size:10px; font-weight:900; padding:2px 7px; border-radius:999px; }}
.dojo-status.pending {{ background:#334155; color:#94a3b8; }}
.dojo-status.done {{ background:#22c55e; color:#06111f; }}
.dojo-card h4 {{ margin:4px 0 6px; font-size:15px; }}
.dojo-card p {{ font-size:12px; color:#94a3b8; line-height:1.45; margin:0 0 12px; }}
.dojo-card-footer {{ display:flex; flex-direction:column; gap:6px; }}
.dojo-action-btn {{ width:100%; font-size:11px; }}
.dojo-hint {{ font-size:10.5px; color:#64748b; font-style:italic; }}
.dojo-celebration {{ display:flex; align-items:center; gap:14px; padding:14px 18px; border-radius:14px; background:linear-gradient(135deg,rgba(234,179,8,.2),rgba(34,197,94,.2)); border:2px solid #eab308; margin-bottom:16px; animation:pop .3s ease both; }}
.celebration-badge {{ width:44px; height:44px; border-radius:50%; background:#eab308; color:#111; display:grid; place-items:center; flex-shrink:0; }}
.celebration-badge .ui-icon {{ width:24px; height:24px; }}
.celebration-text {{ flex:1; }}
.celebration-text h4 {{ margin:0 0 3px; color:#fef08a; font-size:17px; }}
.celebration-text p {{ margin:0; font-size:12px; color:#f1f5f9; line-height:1.35; }}
.celebration-btn {{ white-space:nowrap; font-size:11px; }}
.gaze-reticle {{ position:fixed; pointer-events:none; z-index:9999; width:32px; height:32px; margin-left:-16px; margin-top:-16px; transition:transform .08s ease; }}
.reticle-ring {{ width:100%; height:100%; border:2px solid var(--mode-accent, #06b6d4); border-radius:50%; box-shadow:0 0 10px var(--mode-accent, #06b6d4); box-sizing:border-box; }}
.reticle-dot {{ position:absolute; top:50%; left:50%; width:4px; height:4px; margin-left:-2px; margin-top:-2px; background:#fff; border-radius:50%; }}
.reticle-ch {{ position:absolute; background:var(--mode-accent, #06b6d4); }}
.ch-top {{ top:-5px; left:50%; width:2px; height:5px; margin-left:-1px; }}
.ch-bottom {{ bottom:-5px; left:50%; width:2px; height:5px; margin-left:-1px; }}
.ch-left {{ left:-5px; top:50%; width:5px; height:2px; margin-top:-1px; }}
.ch-right {{ right:-5px; top:50%; width:5px; height:2px; margin-top:-1px; }}
.reticle-sniper-badge {{ display:none; position:absolute; top:-16px; right:-20px; background:#ef4444; color:#fff; font-size:9px; font-weight:900; padding:1px 5px; border-radius:999px; }}
.gaze-reticle.sniper-mode {{ width:60px; height:60px; margin-left:-30px; margin-top:-30px; }}
.gaze-reticle.sniper-mode .reticle-ring {{ border-width:3px; border-color:#ef4444; box-shadow:0 0 20px rgba(239,68,68,.7); }}
.gaze-reticle.sniper-mode .reticle-sniper-badge {{ display:block; }}
.gaze-shockwave {{ position:fixed; pointer-events:none; z-index:9998; border:3px solid var(--mode-accent, #06b6d4); border-radius:50%; width:24px; height:24px; margin-left:-12px; margin-top:-12px; animation:shockwave-expand .6s cubic-bezier(.1,.8,.3,1) forwards; }}
@keyframes shockwave-expand {{ 0% {{ transform:scale(1); opacity:1; border-width:4px; }} 100% {{ transform:scale(6.5); opacity:0; border-width:1px; }} }}
.sim-cell.gaze-focused, .card.gaze-focused {{ outline:2px solid var(--mode-accent, #06b6d4); outline-offset:2px; box-shadow:0 0 14px var(--mode-accent, #06b6d4); }}
.sound-toggle.muted {{ opacity:.65; filter:grayscale(1); }}
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

{CYBER_GLASS_CSS}
{NINTENDO_CSS}
@media (max-width:760px) {{
  .hero {{ align-items:flex-start; flex-direction:column; }}
  .sim-workspace {{ grid-template-columns:1fr; }}
  .ribbon {{ transform:rotate(-.8deg); }}
}}
@media print {{
  @page {{ size:A4 landscape; margin:10mm; }}
  body {{ background:#fff !important; color:#111; }}
  .app {{ width:100%; padding:0; }}
  .hero {{ border:0; box-shadow:none; background:#fff; padding:0 0 8px; }}
  .hero-actions, .tabs, .pager, .sim-modes, #gazeReticle, #soundToggle, .gaze-shockwave, .dojo-celebration .celebration-btn {{ display:none !important; }}
  .page {{ display:block !important; break-after:page; page-break-after:always; color:#111; }}
  .page:last-of-type {{ break-after:auto; page-break-after:auto; }}
  .ribbon {{ box-shadow:3px 3px 0 #999; border-color:#777; }}
  .intro, .card p, .gesture-card p, .sim-info p, .shortcut span {{ color:#333; }}
  .card, .gesture-card, .simulator, .shortcut, .legal-item, .dojo-section, .dojo-card, .vscode-pane {{ background:#fff; border-color:#bbb; box-shadow:none; break-inside:avoid; }}
  .legal-item b, .legal-item p, .dojo-card h4, .dojo-card p {{ color:#222; }}
  .card h3, .card p, .sim-info h4, .shortcut b {{ color:#111; }}
  .sim-cell {{ background:#f4f4f4; color:#111; border-color:#999; box-shadow:none; }}
  .sim-cell small {{ color:#333; }}
  .badge, .chip, .dojo-badge {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
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
<button class="btn dojo-jump-btn" id="dojoJumpBtn" type="button" onclick="jumpToDojo()">{_ui_icon("trophy")}<span>Dojo 60 Hz</span></button>
<button class="btn sound-toggle" id="soundToggle" type="button" onclick="toggleSound()">{_ui_icon("volume-2", "sound-icon")}<span id="soundLabel">Sonido: ON</span></button>
<button class="btn theme-toggle" id="themeToggle" type="button" onclick="toggleTheme()">{_ui_icon("palette")}<span id="themeLabel">Estilo: Nintendo Booklet / Cyber-Glass</span></button>
<button class="btn" onclick="window.print()">{_ui_icon("printer")}<span>Guardar como PDF</span></button>
    </div>
  </header>
  <nav class="tabs tab-navigation" aria-label="Categorías del manual">{''.join(tabs)}</nav>
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
<div id="gazeReticle" class="gaze-reticle" aria-hidden="true">
  <div class="reticle-ring"></div>
  <div class="reticle-dot"></div>
  <div class="reticle-ch ch-top"></div>
  <div class="reticle-ch ch-bottom"></div>
  <div class="reticle-ch ch-left"></div>
  <div class="reticle-ch ch-right"></div>
  <div class="reticle-sniper-badge" id="reticleSniperBadge">3.5x</div>
</div>
<script>
const GUIDE = {data_json};
{THEME_JS}
let currentPage = 0;
let currentMode = Object.keys(GUIDE.simulator || {{}})[0] || "coding";

function showPage(index) {{
  const pages = [...document.querySelectorAll("section.page")];
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
  applyModeAccent(modeId);
  document.querySelectorAll(".sim-mode").forEach(btn => btn.classList.toggle("active", btn.dataset.mode === modeId));
  const grid = document.getElementById("simGrid");
  if (!grid) return;
  grid.innerHTML = "";
  mode.cells.forEach((cell, index) => {{
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sim-cell";
    button.dataset.cellIndex = index;
    button.innerHTML = `<span>${{cell.label}}</span><small>${{cell.hint}}</small>`;
    button.addEventListener("click", (e) => {{
      triggerMARClick(e.clientX, e.clientY, button);
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
initSimEditor();
</script>
</body>
</html>'''
    return "\n".join(line.rstrip() for line in html.splitlines())

"""Inline JavaScript (theme, audio, simulator) embedded in the guide."""


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

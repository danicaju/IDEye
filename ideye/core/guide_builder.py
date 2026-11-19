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


from ideye.core.guide_widgets import (  # noqa: F401
    _ACCENTS,
    _app_icon_data_uri,
    _esc,
    _icon,
    _ui_icon,
    _brand_logo,
    _cards,
    _gesture_strip,
    _shortcut_grid,
    _simulator,
)
from ideye.core.guide_theme_js import THEME_JS  # noqa: F401
from ideye.core.guide_css_base import CSS_BASE
from ideye.core.guide_css_components import CSS_COMPONENTS
from ideye.core.guide_css_pages import CSS_PAGES

STUDIO_CSS = CSS_BASE + CSS_COMPONENTS + CSS_PAGES


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

        mode_count = len(catalog.get("modes", [])) or 6
        page_cards = list(page.get("cards", []))
        all_cards = _cards(page_cards, accent)

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
                  <div class="stat-pill"><div class="stat-val">&lt; 35 ms</div><div class="stat-lbl">De la cámara al cursor</div></div>
                  <div class="stat-pill"><div class="stat-val">Zero-Dwell</div><div class="stat-lbl">Mirar no acciona nada</div></div>
                  <div class="stat-pill"><div class="stat-val">{mode_count} modos</div><div class="stat-lbl">Cada uno con su menú</div></div>
                </div>
              </div>
              <div class="double-page-container">
                <div class="cards-subgrid">{all_cards}</div>
                <div class="book-spine" aria-hidden="true"></div>
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

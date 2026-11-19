"""Guide CSS: cards, ribbons, badges and widgets."""

CSS_COMPONENTS = """\

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
  border-radius: var(--r-l);
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
  position: relative;
}

/* Clean spine: one hairline between the two columns, no binding rings. */
.book-spine {
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  width: 1px;
  transform: translateX(-0.5px);
  background: linear-gradient(180deg, transparent 0%, var(--border-color) 12%, var(--border-color) 88%, transparent 100%);
  opacity: 0.7;
  pointer-events: none;
}

/* Cards Grid */
.cards-subgrid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: stretch;
  gap: 20px 40px;
}
@media (max-width: 960px) {
  .cards-subgrid {
    grid-template-columns: minmax(0, 1fr);
    gap: 16px;
  }
  .book-spine {
    display: none;
  }
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--r-l);
  padding: 18px 20px;
  box-shadow: var(--card-shadow);
  transition: transform 0.22s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.22s ease, border-color 0.22s ease;
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow-wrap: anywhere;
}
.card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  border-radius: var(--r-l) var(--r-l) 0 0;
  height: 2.5px;
  background: linear-gradient(90deg, var(--accent, var(--mode-accent)), transparent 85%);
  opacity: 0.6;
  transition: opacity 0.2s ease;
}
.card:hover {
  border-color: var(--accent, var(--mode-accent));
  box-shadow: var(--card-shadow);
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
  border-radius: var(--r-s);
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
  font-family: var(--font-display);
  font-size: 17px;
  font-weight: 700;
  margin: 0 0 6px;
  color: var(--text-main);
  letter-spacing: -0.01em;
  line-height: 1.3;
}
.card-desc {
  font-size: 13.5px;
  color: var(--text-muted);
  margin: 0 0 12px;
  line-height: 1.6;
  max-width: 62ch;
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
  border-radius: var(--r-s);
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
  border-radius: var(--r-l);
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
  border-radius: var(--r-l);
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
  border-radius: var(--r-s);
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
  border-radius: var(--r-s);
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
  border-radius: var(--r-s);
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
  border-radius: var(--r-l);
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
"""

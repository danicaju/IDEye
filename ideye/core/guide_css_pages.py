"""Guide CSS: pages, simulator, responsive and print rules."""

CSS_PAGES = """\

.sim-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}
.sim-cell {
  background: var(--bg-page);
  border: 1.5px solid var(--border-color);
  border-radius: var(--r-l);
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
  border-radius: var(--r-l);
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
  border-radius: var(--r-s);
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
  border-radius: var(--r-l);
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
  border-radius: var(--r-l);
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
  border-radius: var(--r-l);
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
  border-radius: var(--r-s);
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
  border-radius: var(--r-l);
  padding: 16px;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
}
.celebration-badge {
  width: 42px;
  height: 42px;
  border-radius: var(--r-s);
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
  border-radius: var(--r-l);
  box-shadow: var(--card-shadow);
}
.legal-icon {
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

/* Motion, transparency and contrast preferences */
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}
@media (prefers-reduced-transparency: reduce) {
  .sticky-header {
    background: var(--bg-card);
    backdrop-filter: none;
    -webkit-backdrop-filter: none;
  }
}
@media (prefers-contrast: more) {
  :root { --border-color: #64748b; }
  body[data-theme="cyber-glass"] { --border-color: rgba(255, 255, 255, 0.4); }
  .card { border-width: 2px; }
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

"""Guide CSS: design tokens, layout and typography."""

CSS_BASE = """
/* ===================================================================
   IDEye Studio Redesign System (Switch Booklet Light vs Cyber-Glass Dark)
   =================================================================== */

:root {
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'Consolas', monospace;
  --mode-accent: #0ea5e9;
  --r-s: 8px;
  --r-l: 14px;
  --font-display: 'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, 'Times New Roman', serif;
  --mode-accent-rgb: 14, 165, 233;

  /* Switch Booklet Light (Editorial Nintendo Style) */
  --bg-page: #f8fafc;
  --bg-body-grad: radial-gradient(circle at 10% 10%, rgba(14, 165, 233, 0.05) 0%, transparent 40%),
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
  --hero-glow: radial-gradient(ellipse at 15% 30%, rgba(var(--mode-accent-rgb), 0.1) 0%, transparent 65%);
}

body[data-theme="nintendo-booklet"],
body[data-theme="switch"] {
  --bg-page: #f8fafc;
  --bg-body-grad: radial-gradient(circle at 10% 10%, rgba(14, 165, 233, 0.05) 0%, transparent 40%),
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
  --hero-glow: radial-gradient(ellipse at 15% 30%, rgba(var(--mode-accent-rgb), 0.1) 0%, transparent 65%);
}

body[data-theme="cyber-glass"] {
  --bg-page: #070b14;
  --bg-body-grad: radial-gradient(circle at 12% 15%, rgba(14, 165, 233, 0.1) 0%, transparent 45%),
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
  --hero-glow: radial-gradient(ellipse at 15% 30%, rgba(var(--mode-accent-rgb), 0.16) 0%, transparent 65%);
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
  border-radius: var(--r-l);
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
  border-radius: var(--r-s);
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
  border-radius: var(--r-l);
  padding: 24px 28px;
  margin-bottom: 20px;
  box-shadow: var(--card-shadow);
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
  position: relative;
}
.page-hero::before {
  content: "";
  border-radius: inherit;
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
  padding: 0;
  background: none;
  border: none;
  margin-bottom: 6px;
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
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.02em;
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
  font-weight: 700;
  letter-spacing: 0.1px;
  color: var(--mode-accent);
}
.mini-kicker {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.1px;
  color: var(--mode-accent);
}
"""

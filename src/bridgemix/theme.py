"""
Application theme — design tokens and QSS stylesheet.

Palette and channel colours taken from tools/design/BridgeMixUi.htm

String constants (hex)  → use in QSS and f-strings
QColor constants (Q_*)  → use in QPainter-based widgets; never hardcode QColor values
                          in individual widget files; always reference these instead.
"""
from PyQt6.QtGui import QColor

# ── Channel accent colours ─────────────────────────────────────────────────────
CH_MIC   = "#e05c12"   # orange (accent)
CH_AUX   = "#4a9eff"   # blue
CH_CHAT  = "#a78bfa"   # purple
CH_GAME  = "#22c55e"   # green
CH_MUSIC = "#f59e0b"   # yellow
CH_SYS   = "#34d399"   # teal
CH_SFX   = "#fb7185"   # pink

CHANNEL_COLORS: dict[str, str] = {
    "mic":   CH_MIC,
    "aux":   CH_AUX,
    "chat":  CH_CHAT,
    "game":  CH_GAME,
    "music": CH_MUSIC,
    "sys":   CH_SYS,
    "sfx":   CH_SFX,
}

# ── Surfaces ───────────────────────────────────────────────────────────────────
BG        = "#0e0e0f"
SURFACE   = "#141416"
SURFACE_2 = "#1a1a1d"
SURFACE_3 = "#202024"
SURFACE_4 = "#28282d"
SURFACE_5 = "#313136"

# ── Text ───────────────────────────────────────────────────────────────────────
TEXT       = "#e8e8ea"
TEXT_MUTED = "#7a7a82"
TEXT_FAINT = "#48484f"

# ── Accent ────────────────────────────────────────────────────────────────────
ACCENT       = "#e05c12"
ACCENT_HOVER = "#f0702a"
ACCENT_SOFT  = "rgba(224,92,18,0.14)"
ACCENT_GLOW  = "rgba(224,92,18,0.35)"

# ── Semantic ───────────────────────────────────────────────────────────────────
GREEN  = "#22c55e"
RED    = "#f87171"
BLUE   = "#4a9eff"

# ── QColor palette (for QPainter-based widgets) ───────────────────────────────
# Mirrors the hex-string tokens above so painting code never hardcodes a colour.
# Import with:  from bridgemix import theme  →  use theme.Q_ACCENT, etc.

Q_BG           = QColor(BG)           # #0e0e0f — canvas background
Q_ACCENT       = QColor(ACCENT)       # #e05c12 — brand orange (toggle ON, active)
Q_ACCENT_HOVER = QColor(ACCENT_HOVER) # #f0702a — hot / hover state
Q_SURFACE_4    = QColor(SURFACE_4)    # #28282d — inactive groove / track fill
Q_SURFACE_5    = QColor(SURFACE_5)    # #313136 — toggle OFF track
Q_TEXT         = QColor(TEXT)         # #e8e8ea — primary text / peak hold dash
Q_TEXT_MUTED   = QColor(TEXT_MUTED)   # #7a7a82 — secondary text / axis labels
Q_TEXT_FAINT   = QColor(TEXT_FAINT)   # #48484f — grid lines / de-emphasised text
Q_RED          = QColor(RED)          # #f87171 — clip zone / clip flash
Q_GREEN        = QColor(GREEN)        # #22c55e — optimal zone


# ── Global application stylesheet ─────────────────────────────────────────────
APP_STYLESHEET = """
/* ── Base ──────────────────────────────────────────────────────────────────── */
/* Plain widgets default to transparent so they show the nearest opaque ancestor
   (QMainWindow / #content_area / surfaces below).  The canvas colour is set on
   those containers, not here — a background-color on this base QWidget rule would
   be overridden by the transparent default that follows and paint nothing. */
QWidget {
    color: #e8e8ea;
    font-family: "Segoe UI", "Ubuntu", "Cantarell", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 12px;
    border: none;
    outline: none;
    background-color: transparent;
}
QMainWindow { background-color: #0e0e0f; }
QDialog     { background-color: #141416; }

/* ── Status bar ─────────────────────────────────────────────────────────────── */
QStatusBar {
    background-color: #141416;
    color: #7a7a82;
    border-top: 1px solid rgba(255,255,255,0.07);
    padding: 2px 8px;
    font-size: 11px;
}
QStatusBar::item { border: none; }

/* ── Header / sidebar / content ─────────────────────────────────────────────── */
QFrame#header {
    background-color: #141416;
    border-bottom: 1px solid rgba(255,255,255,0.07);
}
QWidget#sidebar {
    background-color: #141416;
    border-right: 1px solid rgba(255,255,255,0.07);
}
QWidget#content_area { background-color: #0e0e0f; }

/* ── Sidebar nav buttons ────────────────────────────────────────────────────── */
QPushButton#nav_btn {
    background-color: transparent;
    color: #48484f;
    border: none;
    border-radius: 6px;
    padding: 10px 4px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}
QPushButton#nav_btn:hover {
    background-color: rgba(255,255,255,0.04);
    color: #7a7a82;
}
QPushButton#nav_btn:checked {
    background-color: rgba(224,92,18,0.12);
    color: #e05c12;
    border-left: 2px solid #e05c12;
    border-radius: 0px 6px 6px 0px;
}

/* ── Group boxes ────────────────────────────────────────────────────────────── */
QGroupBox {
    background-color: #141416;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 10px;
    margin-top: 24px;
    padding: 10px 8px 8px 8px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 5px;
    color: #48484f;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.1em;
    background: transparent;
}

/* ── Buttons ────────────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #202024;
    color: #e8e8ea;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton:hover {
    background-color: #28282d;
    border-color: rgba(255,255,255,0.2);
}
QPushButton:pressed { background-color: #313136; }
QPushButton:disabled {
    color: #48484f;
    border-color: rgba(255,255,255,0.05);
}
QPushButton:checked {
    background-color: rgba(224,92,18,0.16);
    color: #e05c12;
    border-color: rgba(224,92,18,0.35);
}

QPushButton#btn_primary {
    background-color: #e05c12;
    color: #ffffff;
    border-color: #e05c12;
    font-weight: 600;
}
QPushButton#btn_primary:hover {
    background-color: #f0702a;
    border-color: #f0702a;
}

/* Footer info/about button: borderless circular glyph, muted until hover */
QPushButton#btn_about {
    background: transparent;
    border: none;
    border-radius: 14px;
    padding: 0;
    color: #7a7a82;
    font-size: 16px;
}
QPushButton#btn_about:hover {
    background-color: rgba(255,255,255,0.08);
    color: #e8e8ea;
}
/* An update is available: tint the glyph the brand orange */
QPushButton#btn_about[update="true"] {
    color: #e05c12;
}

/* Connected: green status pill */
QPushButton#btn_connect {
    background: rgba(34,197,94,0.12);
    color: #22c55e;
    border: 1px solid rgba(34,197,94,0.30);
    border-radius: 10px;
    padding: 5px 16px;
    font-size: 12px;
    font-weight: 700;
}
QPushButton#btn_connect:hover {
    background: rgba(34,197,94,0.20);
    border-color: rgba(34,197,94,0.48);
}
/* Disconnected: orange-bordered pill — prompts action */
QPushButton#btn_connect[connected="false"] {
    background: transparent;
    color: #e05c12;
    border: 1px solid rgba(224,92,18,0.40);
}
QPushButton#btn_connect[connected="false"]:hover {
    background: rgba(224,92,18,0.08);
    color: #f0702a;
    border-color: rgba(224,92,18,0.65);
}

/* Mix Link — ghost/outline pill chip; secondary to the Personal/Stream selector */
QPushButton#MixLinkBtn {
    background: transparent;
    color: #7a7a82;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 13px;
    padding: 4px 14px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
QPushButton#MixLinkBtn:hover {
    color: #e8e8ea;
    border-color: rgba(255,255,255,0.22);
}
QPushButton#MixLinkBtn:checked {
    background: rgba(224,92,18,0.10);
    color: #e05c12;
    border-color: rgba(224,92,18,0.45);
}

QPushButton#btn_mute {
    background-color: transparent;
    color: #48484f;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 4px;
    padding: 3px 6px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.07em;
}
QPushButton#btn_mute:hover { color: #7a7a82; border-color: rgba(255,255,255,0.12); }
QPushButton#btn_mute:checked {
    background-color: rgba(248,113,113,0.14);
    color: #f87171;
    border-color: rgba(248,113,113,0.3);
}

/* ── Combo boxes ────────────────────────────────────────────────────────────── */
QComboBox {
    background-color: #1a1a1d;
    color: #e8e8ea;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 6px;
    padding: 5px 10px 5px 10px;
    font-size: 12px;
    min-height: 26px;
    selection-background-color: rgba(224,92,18,0.2);
}
QComboBox:hover { border-color: rgba(255,255,255,0.14); }
QComboBox:focus { border-color: #e05c12; }
QComboBox::drop-down {
    border: none;
    width: 24px;
    padding-right: 6px;
}
QComboBox::down-arrow {
    width: 0;
    height: 0;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #7a7a82;
}
QComboBox QAbstractItemView {
    background-color: #1a1a1d;
    color: #e8e8ea;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    outline: none;
    selection-background-color: rgba(224,92,18,0.2);
    selection-color: #e8e8ea;
}

/* ── Vertical sliders (generic) ─────────────────────────────────────────────── */
QSlider::groove:vertical {
    background-color: #28282d;
    border-radius: 2px;
    width: 4px;
}
QSlider::handle:vertical {
    background-color: #e05c12;
    border: none;
    border-radius: 2px;
    width: 18px;
    height: 8px;
    margin: 0 -7px;
}
QSlider::handle:vertical:hover {
    background-color: #f0702a;
}
QSlider::sub-page:vertical {
    background-color: #28282d;
    border-radius: 2px;
}
QSlider::add-page:vertical {
    background-color: rgba(224, 92, 18, 0.35);
    border-radius: 2px;
}

/* ── Horizontal sliders ─────────────────────────────────────────────────────── */
QSlider::groove:horizontal {
    background-color: #28282d;
    border-radius: 2px;
    height: 4px;
}
QSlider::handle:horizontal {
    background-color: #e05c12;
    border: none;
    border-radius: 2px;
    width: 12px;
    height: 12px;
    margin: -4px 0;
}
QSlider::handle:horizontal:hover {
    background-color: #f0702a;
}
QSlider::sub-page:horizontal {
    background-color: rgba(224, 92, 18, 0.35);
    border-radius: 2px;
}
QSlider::add-page:horizontal {
    background-color: #28282d;
    border-radius: 2px;
}

/* ── Disabled / read-only sliders ──────────────────────────────────────────── */
QSlider:disabled::groove:vertical,
QSlider:disabled::groove:horizontal   { background-color: #1e1e22; }
QSlider:disabled::handle:vertical,
QSlider:disabled::handle:horizontal   { background-color: #3a3a42; }
QSlider:disabled::sub-page:vertical   { background-color: #1e1e22; }
QSlider:disabled::sub-page:horizontal { background-color: rgba(80, 80, 88, 0.30); }
QSlider:disabled::add-page:vertical   { background-color: rgba(80, 80, 88, 0.30); }
QSlider:disabled::add-page:horizontal { background-color: #1e1e22; }

/* ── Dial ───────────────────────────────────────────────────────────────────── */
QDial {
    background-color: #202024;
}

/* ── Radio buttons ──────────────────────────────────────────────────────────── */
QRadioButton {
    color: #7a7a82;
    spacing: 6px;
    background-color: transparent;
}
QRadioButton:hover { color: #e8e8ea; }
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 7px;
    border: 1px solid rgba(255,255,255,0.14);
    background-color: #202024;
}
QRadioButton::indicator:hover { border-color: #e05c12; }
QRadioButton::indicator:checked {
    background-color: #e05c12;
    border-color: #e05c12;
}

/* ── Check boxes ────────────────────────────────────────────────────────────── */
QCheckBox {
    color: #7a7a82;
    spacing: 6px;
    background-color: transparent;
}
QCheckBox:hover { color: #e8e8ea; }
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 3px;
    border: 1px solid rgba(255,255,255,0.14);
    background-color: #202024;
}
QCheckBox::indicator:hover { border-color: #e05c12; }
QCheckBox::indicator:checked {
    background-color: #e05c12;
    border-color: #e05c12;
}

/* ── List widget ────────────────────────────────────────────────────────────── */
QListWidget {
    background-color: #1a1a1d;
    color: #e8e8ea;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 6px;
    outline: none;
    padding: 4px;
}
QListWidget::item {
    padding: 5px 10px;
    border-radius: 4px;
    color: #7a7a82;
}
QListWidget::item:hover { background-color: rgba(255,255,255,0.04); color: #e8e8ea; }
QListWidget::item:selected {
    background-color: rgba(224,92,18,0.16);
    color: #e05c12;
}

/* ── Progress bars (VU meter / monitor bars) ────────────────────────────────── */
QProgressBar {
    background-color: #28282d;
    border: none;
    border-radius: 3px;
    min-height: 6px;
    max-height: 8px;
    text-align: right;
    color: #7a7a82;
    font-size: 10px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #b84a0e, stop:1 #e05c12);
    border-radius: 3px;
}

/* Vertical peak meters are custom-painted (controls.PeakMeter), not styled here. */

/* ── Scroll bars ────────────────────────────────────────────────────────────── */
QScrollBar:vertical {
    background-color: #141416;
    width: 6px;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical {
    background-color: #313136;
    border-radius: 3px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background-color: #48484f; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background-color: #141416;
    height: 6px;
    border: none;
}
QScrollBar::handle:horizontal {
    background-color: #313136;
    border-radius: 3px;
    min-width: 20px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

/* ── Text / line edit ───────────────────────────────────────────────────────── */
QLineEdit {
    background-color: #1a1a1d;
    color: #e8e8ea;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 12px;
    selection-background-color: rgba(224,92,18,0.3);
}
QLineEdit:hover { border-color: rgba(255,255,255,0.12); }
QLineEdit:focus { border-color: #e05c12; }
QLineEdit::placeholder { color: #48484f; }

QTextEdit, QPlainTextEdit {
    background-color: #1a1a1d;
    color: #e8e8ea;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 6px;
    padding: 6px;
    selection-background-color: rgba(224,92,18,0.3);
    font-family: "Consolas", "DejaVu Sans Mono", "Liberation Mono", "Courier New", monospace;
    font-size: 11px;
}

/* ── Spin box ───────────────────────────────────────────────────────────────── */
QSpinBox {
    background-color: #1a1a1d;
    color: #e8e8ea;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 12px;
}
QSpinBox:focus { border-color: #e05c12; }
QSpinBox::up-button, QSpinBox::down-button {
    background-color: #28282d;
    border: none;
    width: 16px;
    border-radius: 3px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background-color: #313136;
}

/* ── Frames (separators) ────────────────────────────────────────────────────── */
QFrame[frameShape="4"] { color: rgba(255,255,255,0.07); }
QFrame[frameShape="5"] { color: rgba(255,255,255,0.07); }

/* ── Tool bar (legacy fallback) ─────────────────────────────────────────────── */
QToolBar {
    background-color: #141416;
    border-bottom: 1px solid rgba(255,255,255,0.07);
    spacing: 6px;
    padding: 4px 8px;
}
QToolBar::separator {
    background-color: rgba(255,255,255,0.07);
    width: 1px;
    margin: 4px 2px;
}

/* ── Message box ────────────────────────────────────────────────────────────── */
QMessageBox { background-color: #141416; }
QMessageBox QLabel { background-color: transparent; }

/* ── File dialog ────────────────────────────────────────────────────────────── */
QFileDialog { background-color: #141416; }

/* ── Mic type segmented toggle buttons (INPUT page) ─────────────────────────── */
QPushButton#MicTypeBtn {
    background-color: #1a1a1d;
    color: #48484f;
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 6px;
    padding: 0px 16px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
QPushButton#MicTypeBtn:hover {
    background-color: #202024;
    color: #7a7a82;
    border-color: rgba(255,255,255,0.13);
}
QPushButton#MicTypeBtn:checked {
    background-color: rgba(224,92,18,0.14);
    color: #e05c12;
    border: 1px solid rgba(224,92,18,0.42);
}
QPushButton#MicTypeBtn:checked:hover {
    background-color: rgba(224,92,18,0.22);
    border-color: rgba(224,92,18,0.62);
}

/* ── Home page — mixer strip cards ─────────────────────────────────────────── */
QFrame#InputCard {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #131418, stop:1 #0d0e11);
    border: 1px solid rgba(255,255,255,0.10);
    border-radius: 10px;
}

/* ── Home page — lower section blocks ──────────────────────────────────────── */
QFrame#HomeLowerBlock {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #111318, stop:1 #0b0d11);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 10px;
}

/* ── Bus mute buttons inside strips ────────────────────────────────────────── */
QPushButton#BusMuteBtn {
    background-color: #252528;
    color: #7a7a82;
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 4px;
    padding: 2px 0;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.06em;
}
QPushButton#BusMuteBtn:hover {
    color: #e8e8ea;
    border-color: rgba(255,255,255,0.16);
}
QPushButton#BusMuteBtn:checked {
    background-color: rgba(220,60,40,0.20);
    color: #f87171;
    border-color: rgba(220,60,40,0.35);
}

/* ── Destructive action button (e.g. factory reset) ────────────────────────── */
QPushButton#DangerBtn {
    background-color: rgba(220,60,40,0.14);
    color: #f87171;
    border: 1px solid rgba(220,60,40,0.40);
    border-radius: 6px;
    padding: 6px 16px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.04em;
}
QPushButton#DangerBtn:hover {
    background-color: rgba(220,60,40,0.24);
    border-color: rgba(220,60,40,0.60);
}
QPushButton#DangerBtn:disabled {
    background-color: #1a1a1d;
    color: #48484f;
    border-color: rgba(255,255,255,0.07);
}

/* ── Wide-groove vertical fader in hardware strips ──────────────────────────── */
QSlider#MixerFader::groove:vertical {
    background-color: #1a1a1d;
    border-radius: 4px;
    width: 8px;
}
QSlider#MixerFader::handle:vertical {
    background-color: #e05c12;
    border: none;
    border-radius: 2px;
    width: 22px;
    height: 10px;
    margin: 0 -7px;
}
QSlider#MixerFader::handle:vertical:hover {
    background-color: #f0702a;
}
QSlider#MixerFader::sub-page:vertical {
    background-color: #1a1a1d;
    border-radius: 4px;
}
QSlider#MixerFader::add-page:vertical {
    background-color: rgba(224,92,18,0.35);
    border-radius: 4px;
}

/* ── Output faders (mixer home page) ────────────────────────────────────────── */
/* Writable — same groove/knob proportions as MixerFader, unified orange colour  */
QSlider#OutputFader::groove:vertical {
    background-color: #1a1a1d;
    border-radius: 4px;
    width: 8px;
}
QSlider#OutputFader::handle:vertical {
    background-color: #e05c12;
    border: none;
    border-radius: 2px;
    width: 22px;
    height: 10px;
    margin: 0 -7px;
}
QSlider#OutputFader::handle:vertical:hover {
    background-color: #f0702a;
}
QSlider#OutputFader::sub-page:vertical {
    background-color: #1a1a1d;
    border-radius: 4px;
}
QSlider#OutputFader::add-page:vertical {
    background-color: rgba(224, 92, 18, 0.35);
    border-radius: 4px;
}
/* Read-only — identical proportions, grey knob so it reads as non-interactive   */
QSlider#OutputFaderRO::groove:vertical {
    background-color: #18181b;
    border-radius: 4px;
    width: 8px;
}
QSlider#OutputFaderRO::handle:vertical,
QSlider#OutputFaderRO::handle:vertical:hover {
    background-color: #3a3a42;
    border: none;
    border-radius: 2px;
    width: 22px;
    height: 10px;
    margin: 0 -7px;
}
QSlider#OutputFaderRO::sub-page:vertical {
    background-color: #18181b;
    border-radius: 4px;
}
QSlider#OutputFaderRO::add-page:vertical {
    background-color: rgba(72, 72, 80, 0.30);
    border-radius: 4px;
}

/* Read-only badge */
QLabel#RoBadge {
    color: #7a7a88;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.04em;
    border: 1px solid #3a3a44;
    border-radius: 3px;
    padding: 1px 5px;
}

/* ── Fader value readout ────────────────────────────────────────────────────── */
QLabel#FaderValue {
    color: #7a7a82;
    font-size: 10px;
    font-family: "Consolas", "DejaVu Sans Mono", "Liberation Mono", "Courier New", monospace;
}

/* ── Strip section labels (Button Action, etc.) ─────────────────────────────── */
QLabel#StripActionLabel {
    color: #5a5a62;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-top: 2px;
}

/* ── Page title ─────────────────────────────────────────────────────────────── */
QLabel#PageTitle {
    font-size: 20px;
    font-weight: 700;
    color: #f3f4f6;
    letter-spacing: -0.01em;
    background: transparent;
}

/* ── MIDI monitor log ────────────────────────────────────────────────────────── */
QTextEdit#MidiLog {
    background-color: #09090b;
    color: #d4d4d8;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #3f3f46;
}

/* ── Tab widget (MIDI monitor) ──────────────────────────────────────────────── */
QTabWidget::pane {
    border: none;
    background-color: #0e0e0f;
}
QTabBar {
    background-color: transparent;
}
QTabBar::tab {
    background-color: transparent;
    color: #48484f;
    padding: 8px 18px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    border-bottom: 2px solid transparent;
    margin-right: 2px;
}
QTabBar::tab:hover { color: #7a7a82; }
QTabBar::tab:selected {
    color: #e05c12;
    border-bottom: 2px solid #e05c12;
}
"""

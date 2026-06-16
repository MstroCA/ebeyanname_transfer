# -*- coding: utf-8 -*-
"""Uygulama teması (QSS) ve renk paleti."""

# Palet — koyu lacivert kabuk, açık içerik, mercan vurgu
COLORS = {
    "bg":        "#0E1726",   # en dış kabuk
    "sidebar":   "#13203A",
    "surface":   "#FFFFFF",
    "surface_2": "#F4F6FB",
    "border":    "#E2E6EF",
    "text":      "#1A2233",
    "text_soft": "#5A6478",
    "text_inv":  "#EAF0FB",
    "accent":    "#3D63DD",   # birincil aksiyon
    "accent_d":  "#2E4DB0",
    "ok":        "#30A46C",
    "warn":      "#F5A524",
    "danger":    "#E5484D",
    "danger_d":  "#C13A3E",
}

QSS = f"""
QMainWindow, QWidget {{
    background: {COLORS['surface_2']};
    color: {COLORS['text']};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}

/* ── Sidebar ── */
#Sidebar {{
    background: {COLORS['sidebar']};
    border: none;
}}
#Brand {{
    color: {COLORS['text_inv']};
    font-size: 16px;
    font-weight: 700;
    padding: 22px 20px 6px 20px;
}}
#BrandSub {{
    color: #7E8AA8;
    font-size: 11px;
    padding: 0 20px 18px 20px;
}}
QPushButton#NavBtn {{
    background: transparent;
    color: #AEB9D4;
    text-align: left;
    padding: 12px 20px;
    border: none;
    border-left: 3px solid transparent;
    font-size: 13px;
}}
QPushButton#NavBtn:hover {{
    background: rgba(255,255,255,0.04);
    color: {COLORS['text_inv']};
}}
QPushButton#NavBtn:checked {{
    background: rgba(61,99,221,0.16);
    color: #FFFFFF;
    border-left: 3px solid {COLORS['accent']};
    font-weight: 600;
}}

/* ── Kartlar ── */
#Card {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
}}
#PageTitle {{ font-size: 22px; font-weight: 700; }}
#PageSub {{ color: {COLORS['text_soft']}; font-size: 13px; }}
#SectionTitle {{ font-size: 15px; font-weight: 600; }}

/* ── Inputlar ── */
QLineEdit, QSpinBox, QComboBox, QPlainTextEdit {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: {COLORS['accent']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {COLORS['accent']};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['surface_2']};
    selection-color: {COLORS['text']};
    outline: none;
}}
QLabel#FieldLabel {{ color: {COLORS['text_soft']}; font-size: 12px; font-weight: 600; }}

/* ── Butonlar ── */
QPushButton {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    padding: 9px 16px;
    font-weight: 600;
}}
QPushButton:hover {{ background: {COLORS['surface_2']}; }}
QPushButton#Primary {{
    background: {COLORS['accent']};
    color: white;
    border: none;
}}
QPushButton#Primary:hover {{ background: {COLORS['accent_d']}; }}
QPushButton#Primary:disabled {{ background: #A9B6E2; color: #EEF1FB; }}
QPushButton#Danger {{
    background: {COLORS['danger']}; color: white; border: none;
}}
QPushButton#Danger:hover {{ background: {COLORS['danger_d']}; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid {COLORS['border']}; }}

/* ── Tablo / listeler ── */
QTableWidget, QListWidget {{
    background: {COLORS['surface']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    gridline-color: {COLORS['border']};
}}
QHeaderView::section {{
    background: {COLORS['surface_2']};
    color: {COLORS['text_soft']};
    padding: 8px;
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    font-weight: 600;
}}
QTableWidget::item {{ padding: 6px; }}

/* ── İlerleme ── */
QProgressBar {{
    background: {COLORS['surface_2']};
    border: 1px solid {COLORS['border']};
    border-radius: 8px;
    height: 16px;
    text-align: center;
    color: {COLORS['text_soft']};
}}
QProgressBar::chunk {{
    background: {COLORS['accent']};
    border-radius: 7px;
}}

/* ── Log konsolu ── */
#LogConsole {{
    background: #0E1726;
    color: #D7E0F4;
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    font-family: 'Cascadia Code', 'Consolas', monospace;
    font-size: 12px;
    padding: 8px;
}}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C3CADA; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""

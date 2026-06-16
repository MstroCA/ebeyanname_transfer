# -*- coding: utf-8 -*-
"""
Ortam bazlı veritabanı SVG ikonları.

Her ortamın kendi rengi var:
  PROD  → kırmızı/mercan (dikkat: canlı veri)
  TEST  → amber/sarı
  LOCAL → yeşil (güvenli)

Klasik "database silindir yığını" formu kullanılır.
"""

from __future__ import annotations
from ..core.environments import Environment

ENV_COLORS = {
    Environment.PROD:  {"main": "#E5484D", "soft": "#FEEBEC", "dark": "#A01F23"},
    Environment.TEST:  {"main": "#F5A524", "soft": "#FEF3DD", "dark": "#A8650A"},
    Environment.LOCAL: {"main": "#30A46C", "soft": "#E6F6EC", "dark": "#1B6E45"},
}


def db_svg(env: Environment, size: int = 64) -> str:
    c = ENV_COLORS[env]
    main, dark = c["main"], c["dark"]
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g_{env.value}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{main}"/>
      <stop offset="1" stop-color="{dark}"/>
    </linearGradient>
  </defs>
  <!-- alt katman -->
  <ellipse cx="32" cy="48" rx="20" ry="7" fill="{dark}"/>
  <path d="M12 32 v16 a20 7 0 0 0 40 0 v-16" fill="url(#g_{env.value})"/>
  <ellipse cx="32" cy="32" rx="20" ry="7" fill="{main}"/>
  <!-- orta katman -->
  <path d="M12 20 v12 a20 7 0 0 0 40 0 v-12" fill="url(#g_{env.value})"/>
  <ellipse cx="32" cy="20" rx="20" ry="7" fill="{main}"/>
  <!-- üst katman -->
  <path d="M12 12 v8 a20 7 0 0 0 40 0 v-8" fill="url(#g_{env.value})"/>
  <ellipse cx="32" cy="12" rx="20" ry="7" fill="{main}"/>
  <ellipse cx="32" cy="12" rx="20" ry="7" fill="none" stroke="#ffffff" stroke-opacity="0.35" stroke-width="1.5"/>
</svg>"""


def badge_svg(env: Environment, size: int = 18) -> str:
    """Küçük yuvarlak ortam rozeti."""
    c = ENV_COLORS[env]
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
  <circle cx="9" cy="9" r="8" fill="{c['main']}" stroke="#fff" stroke-width="1.5"/>
</svg>"""

# -*- coding: utf-8 -*-
"""
Environment-aware database SVG icons.

Colors are keyed by environment name (case-insensitive) to support
the new dynamic environment registry.
"""

from __future__ import annotations
from ..core.environments import Environment

# Color palette per environment tier
_ENV_COLOR_MAP: dict[str, dict] = {
    "PROD":        {"main": "#E5484D", "soft": "#FEEBEC", "dark": "#A01F23"},
    "PRODUCTION":  {"main": "#E5484D", "soft": "#FEEBEC", "dark": "#A01F23"},
    "STAGING":     {"main": "#F5A524", "soft": "#FEF3DD", "dark": "#A8650A"},
    "TEST":        {"main": "#F5A524", "soft": "#FEF3DD", "dark": "#A8650A"},
    "QA":          {"main": "#F5A524", "soft": "#FEF3DD", "dark": "#A8650A"},
    "LOCAL":       {"main": "#30A46C", "soft": "#E6F6EC", "dark": "#1B6E45"},
    "DEV":         {"main": "#30A46C", "soft": "#E6F6EC", "dark": "#1B6E45"},
    "DEVELOPMENT": {"main": "#30A46C", "soft": "#E6F6EC", "dark": "#1B6E45"},
    "DEFAULT":     {"main": "#8A93A6", "soft": "#F4F6FB", "dark": "#5A6478"},
}


def _get_env_colors(env: Environment) -> dict:
    key = env.name.upper()
    return _ENV_COLOR_MAP.get(key, _ENV_COLOR_MAP["DEFAULT"])


# Keep backward-compatible ENV_COLORS dict (keyed by string names for direct lookups)
ENV_COLORS = _ENV_COLOR_MAP


def db_svg(env: Environment, size: int = 64) -> str:
    c = _get_env_colors(env)
    main, dark = c["main"], c["dark"]
    safe_id = env.name.replace(" ", "_").upper()
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="g_{safe_id}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{main}"/>
      <stop offset="1" stop-color="{dark}"/>
    </linearGradient>
  </defs>
  <ellipse cx="32" cy="48" rx="20" ry="7" fill="{dark}"/>
  <path d="M12 32 v16 a20 7 0 0 0 40 0 v-16" fill="url(#g_{safe_id})"/>
  <ellipse cx="32" cy="32" rx="20" ry="7" fill="{main}"/>
  <path d="M12 20 v12 a20 7 0 0 0 40 0 v-12" fill="url(#g_{safe_id})"/>
  <ellipse cx="32" cy="20" rx="20" ry="7" fill="{main}"/>
  <path d="M12 12 v8 a20 7 0 0 0 40 0 v-8" fill="url(#g_{safe_id})"/>
  <ellipse cx="32" cy="12" rx="20" ry="7" fill="{main}"/>
  <ellipse cx="32" cy="12" rx="20" ry="7" fill="none" stroke="#ffffff" stroke-opacity="0.35" stroke-width="1.5"/>
</svg>"""


def badge_svg(env: Environment, size: int = 18) -> str:
    c = _get_env_colors(env)
    return f"""<svg width="{size}" height="{size}" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
  <circle cx="9" cy="9" r="8" fill="{c['main']}" stroke="#fff" stroke-width="1.5"/>
</svg>"""

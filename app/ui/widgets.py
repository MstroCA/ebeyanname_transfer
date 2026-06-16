# -*- coding: utf-8 -*-
"""Ortak UI yardımcıları: SVG render, ortam rozeti, kart."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout

from ..core.environments import Environment
from .icons import db_svg, ENV_COLORS


def svg_pixmap(svg: str, size: int) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return pm


def db_icon_label(env: Environment, size: int = 56) -> QLabel:
    lbl = QLabel()
    lbl.setPixmap(svg_pixmap(db_svg(env, size), size))
    lbl.setFixedSize(size, size)
    return lbl


def env_color(env: Environment) -> str:
    return ENV_COLORS[env]["main"]


class Card(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(18, 18, 18, 18)
        self._lay.setSpacing(12)

    def layout_(self) -> QVBoxLayout:
        return self._lay

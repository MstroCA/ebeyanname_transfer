# -*- coding: utf-8 -*-
"""Main window: sidebar nav + page stack."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QButtonGroup, QDialog, QMessageBox,
)

from .. import __version__, __app_name__, __author__, __description__
from ..core.store import ConnectionStore
from .theme import QSS
from .connections_view import ConnectionsView
from .transfer_view import TransferView
from .monitoring_view import MonitoringView
from .profiles_view import ProfilesView


def asset_path(name: str) -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "assets" / name  # type: ignore
    return Path(__file__).resolve().parent.parent.parent / "assets" / name


def app_icon() -> QIcon:
    p = asset_path("app.ico")
    if p.exists():
        return QIcon(str(p))
    p2 = asset_path("logo.png")
    return QIcon(str(p2)) if p2.exists() else QIcon()


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setFixedWidth(420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(10)

        logo = QLabel()
        lp = asset_path("logo.png")
        if lp.exists():
            logo.setPixmap(QPixmap(str(lp)).scaled(
                72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)

        name = QLabel(__app_name__)
        name.setAlignment(Qt.AlignCenter)
        name.setStyleSheet("font-size:18px; font-weight:700;")
        lay.addWidget(name)

        ver = QLabel(f"Version {__version__}")
        ver.setAlignment(Qt.AlignCenter)
        ver.setStyleSheet("color:#5A6478;")
        lay.addWidget(ver)

        desc = QLabel(__description__)
        desc.setAlignment(Qt.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#5A6478; padding-top:6px;")
        lay.addWidget(desc)

        author = QLabel(__author__)
        author.setAlignment(Qt.AlignCenter)
        author.setStyleSheet("color:#8A93A6; font-size:11px; padding-top:8px;")
        lay.addWidget(author)

        btn = QPushButton("Close")
        btn.setObjectName("Primary")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__app_name__} · Platform Engineering")
        self.setWindowIcon(app_icon())
        self.resize(1120, 740)
        self.setStyleSheet(QSS)

        self.store = ConnectionStore()

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ──
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        brand = QLabel(__app_name__)
        brand.setObjectName("Brand")
        sub = QLabel("Platform Engineering")
        sub.setObjectName("BrandSub")
        sl.addWidget(brand)
        sl.addWidget(sub)

        self.stack = QStackedWidget()
        self.v_transfer = TransferView(self.store)
        self.v_conns = ConnectionsView(self.store)
        self.v_monitor = MonitoringView()
        self.v_profiles = ProfilesView()
        self.stack.addWidget(self.v_transfer)   # 0
        self.stack.addWidget(self.v_conns)      # 1
        self.stack.addWidget(self.v_monitor)    # 2
        self.stack.addWidget(self.v_profiles)   # 3

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        nav_items = [
            ("Transfer", 0),
            ("Connections", 1),
            ("History", 2),
            ("Profiles", 3),
        ]
        for text, idx in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("NavBtn")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, i=idx: self._navigate(i))
            self.nav_group.addButton(btn)
            sl.addWidget(btn)
            if idx == 0:
                btn.setChecked(True)

        sl.addStretch()
        about_btn = QPushButton(f"About · v{__version__}")
        about_btn.setObjectName("NavBtn")
        about_btn.clicked.connect(self._show_about)
        sl.addWidget(about_btn)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(central)

        self.statusBar().showMessage(f"{__app_name__} v{__version__} — ready")

        self.v_conns.changed.connect(self.v_transfer.reload_connections)
        self.v_profiles.changed.connect(self.v_transfer._load_profiles)

    def _show_about(self):
        AboutDialog(self).exec()

    def _navigate(self, idx: int):
        self.stack.setCurrentIndex(idx)
        if idx == 0:
            self.v_transfer.reload_connections()
        elif idx == 2:
            self.v_monitor.refresh()
        elif idx == 3:
            self.v_profiles.refresh()

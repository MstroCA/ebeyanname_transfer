# -*- coding: utf-8 -*-
"""İzleme ekranı: çalıştırma geçmişi, durum rozetleri, özet istatistik."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QAbstractItemView, QFileDialog,
)

from ..core import monitoring
from .widgets import Card

STATUS_STYLE = {
    "success":   ("#E6F6EC", "#1B6E45", "Başarılı"),
    "warning":   ("#FEF3DD", "#A8650A", "Uyarılı"),
    "error":     ("#FEEBEC", "#A01F23", "Hata"),
    "blocked":   ("#FEEBEC", "#A01F23", "Engellendi"),
    "cancelled": ("#F4F6FB", "#5A6478", "İptal"),
}


class StatCard(Card):
    def __init__(self, title: str):
        super().__init__()
        self.value = QLabel("0")
        self.value.setStyleSheet("font-size:26px; font-weight:700;")
        cap = QLabel(title)
        cap.setStyleSheet("color:#5A6478; font-size:12px; font-weight:600;")
        self.layout_().addWidget(self.value)
        self.layout_().addWidget(cap)

    def set(self, v):
        self.value.setText(str(v))


class MonitoringView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        head = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("İzleme")
        t.setObjectName("PageTitle")
        s = QLabel("Tüm aktarım çalıştırmaları, durumları ve log dosyaları burada tutulur.")
        s.setObjectName("PageSub")
        col.addWidget(t)
        col.addWidget(s)
        head.addLayout(col)
        head.addStretch()
        refresh = QPushButton("Yenile")
        refresh.setObjectName("Ghost")
        refresh.clicked.connect(self.refresh)
        head.addWidget(refresh, alignment=Qt.AlignTop)
        root.addLayout(head)

        stats = QHBoxLayout()
        stats.setSpacing(14)
        self.c_total = StatCard("Toplam çalıştırma")
        self.c_success = StatCard("Başarılı")
        self.c_problem = StatCard("Hata / Uyarı")
        self.c_blocked = StatCard("Engellenen yön")
        for c in (self.c_total, self.c_success, self.c_problem, self.c_blocked):
            stats.addWidget(c)
        root.addLayout(stats)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Zaman", "Yön", "Beyanname", "Durum", "Satır", "Süre", "Log"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in (2, 3, 4, 5, 6):
            h.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(44)
        root.addWidget(self.table, 1)

        self.empty = QLabel("Henüz aktarım yapılmadı.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color:#5A6478; padding:40px;")
        root.addWidget(self.empty)

        self.refresh()

    def refresh(self):
        records = monitoring.read_history(limit=200)
        self.empty.setVisible(not records)
        self.table.setVisible(bool(records))

        total = len(records)
        success = sum(1 for r in records if r.status == "success")
        problem = sum(1 for r in records if r.status in ("error", "warning"))
        blocked = sum(1 for r in records if r.status == "blocked")
        self.c_total.set(total)
        self.c_success.set(success)
        self.c_problem.set(problem)
        self.c_blocked.set(blocked)

        self.table.setRowCount(0)
        for r in records:
            self._add_row(r)

    def _add_row(self, r: monitoring.RunRecord):
        row = self.table.rowCount()
        self.table.insertRow(row)

        try:
            ts = datetime.fromisoformat(r.timestamp).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            ts = r.timestamp
        self.table.setItem(row, 0, QTableWidgetItem(ts))
        self.table.setItem(row, 1, QTableWidgetItem(
            f"{r.source_name} ({r.source_env})  →  {r.target_name} ({r.target_env})"))
        self.table.setItem(row, 2, QTableWidgetItem(str(r.beyanname_id)))

        bg, fg, label = STATUS_STYLE.get(r.status, ("#F4F6FB", "#5A6478", r.status))
        badge = QLabel(label)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background:{bg}; color:{fg}; border-radius:10px; "
            f"padding:3px 10px; font-weight:700; font-size:11px;")
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(6, 4, 6, 4)
        wl.addWidget(badge)
        self.table.setCellWidget(row, 3, wrap)

        self.table.setItem(row, 4, QTableWidgetItem(str(r.total_rows)))
        self.table.setItem(row, 5, QTableWidgetItem(f"{r.duration_sec:g} sn"))

        open_btn = QPushButton("Aç")
        open_btn.setObjectName("Ghost")
        open_btn.clicked.connect(lambda _, p=r.log_file: self._open_log(p))
        ow = QWidget()
        owl = QHBoxLayout(ow)
        owl.setContentsMargins(6, 4, 6, 4)
        owl.addWidget(open_btn)
        self.table.setCellWidget(row, 6, ow)

    def _open_log(self, path: str):
        import os
        import subprocess
        import sys
        if not os.path.exists(path):
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

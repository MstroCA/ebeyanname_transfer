# -*- coding: utf-8 -*-
"""Aktarım ekranı: kaynak/hedef seçimi, yön doğrulama, canlı log."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QPlainTextEdit, QProgressBar, QCheckBox,
    QMessageBox, QFrame, QSizePolicy,
)

from ..core.environments import Environment, check_direction
from ..core.store import Connection, ConnectionStore
from .widgets import Card, db_icon_label, env_color
from .transfer_worker import TransferWorker
from .theme import COLORS


LEVEL_COLORS = {
    "info": "#9FB0D0", "ok": "#5DD39E", "warn": "#F5C26B",
    "error": "#F08A8E", "step": "#8FB8FF",
}


class EndpointCard(Card):
    """Kaynak veya hedef seçici kart (ikon + combobox)."""
    selection_changed = Signal()

    def __init__(self, role_title: str, parent=None):
        super().__init__(parent)
        lay = self.layout_()
        head = QLabel(role_title)
        head.setObjectName("FieldLabel")
        lay.addWidget(head)

        row = QHBoxLayout()
        row.setSpacing(14)
        self.icon = db_icon_label(Environment.LOCAL, 52)
        row.addWidget(self.icon)

        col = QVBoxLayout()
        col.setSpacing(6)
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_change)
        col.addWidget(self.combo)
        self.detail = QLabel("—")
        self.detail.setStyleSheet("color:#5A6478; font-size:12px;")
        col.addWidget(self.detail)
        row.addLayout(col, 1)
        lay.addLayout(row)

        self._conns: list[Connection] = []

    def set_connections(self, conns: list[Connection]):
        cur_id = self.current().id if self.current() else None
        self._conns = conns
        self.combo.blockSignals(True)
        self.combo.clear()
        for c in conns:
            self.combo.addItem(f"{c.name}  ·  {c.env.label}", c.id)
        if cur_id:
            i = self.combo.findData(cur_id)
            if i >= 0:
                self.combo.setCurrentIndex(i)
        self.combo.blockSignals(False)
        self._refresh_visual()

    def current(self) -> Connection | None:
        cid = self.combo.currentData()
        return next((c for c in self._conns if c.id == cid), None)

    def _on_change(self):
        self._refresh_visual()
        self.selection_changed.emit()

    def _refresh_visual(self):
        c = self.current()
        if c:
            self.icon.setPixmap(db_icon_label(c.env, 52).pixmap())
            self.detail.setText(f"{c.masked_summary()}  ·  {c.user}")
        else:
            self.detail.setText("—")


class TransferView(QWidget):
    def __init__(self, store: ConnectionStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.worker: TransferWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        t = QLabel("Aktarım")
        t.setObjectName("PageTitle")
        root.addWidget(t)
        sub = QLabel("Kaynak ve hedef veritabanını seçin. Veri yalnızca üst ortamdan "
                     "alt ortama aktarılabilir (Prod→Test, Prod→Local, Test→Local).")
        sub.setObjectName("PageSub")
        sub.setWordWrap(True)
        root.addWidget(sub)

        # ── kaynak → ok → hedef ──
        endpoints = QHBoxLayout()
        endpoints.setSpacing(14)
        self.src = EndpointCard("KAYNAK")
        self.tgt = EndpointCard("HEDEF")
        self.src.selection_changed.connect(self._validate)
        self.tgt.selection_changed.connect(self._validate)

        self.arrow = QLabel("→")
        self.arrow.setAlignment(Qt.AlignCenter)
        self.arrow.setFixedWidth(56)
        self.arrow.setStyleSheet("font-size:30px; color:#5A6478; font-weight:700;")

        endpoints.addWidget(self.src, 1)
        endpoints.addWidget(self.arrow)
        endpoints.addWidget(self.tgt, 1)
        root.addLayout(endpoints)

        # ── yön durumu bandı ──
        self.dir_banner = QLabel("")
        self.dir_banner.setWordWrap(True)
        self.dir_banner.setAlignment(Qt.AlignCenter)
        self.dir_banner.setStyleSheet("padding:10px; border-radius:8px; font-weight:600;")
        root.addWidget(self.dir_banner)

        # ── parametreler ──
        params = Card()
        pg = QGridLayout()
        pg.setHorizontalSpacing(14)
        pg.setVerticalSpacing(10)
        self.beyanname_id = QLineEdit()
        self.beyanname_id.setPlaceholderText("Ör: 6")
        self.created_by = QLineEdit()
        self.created_by.setPlaceholderText("Opsiyonel — local kullanıcı kodu")
        self.mukellef_vkn = QLineEdit()
        self.mukellef_vkn.setPlaceholderText("Opsiyonel — VKN override")
        self.skip_delete = QCheckBox("Hedefteki mevcut veriyi silme (skip-delete)")

        def fl(txt):
            l = QLabel(txt)
            l.setObjectName("FieldLabel")
            return l

        pg.addWidget(fl("Beyanname ID *"), 0, 0)
        pg.addWidget(self.beyanname_id, 0, 1)
        pg.addWidget(fl("created_by"), 0, 2)
        pg.addWidget(self.created_by, 0, 3)
        pg.addWidget(fl("mükellef VKN"), 1, 0)
        pg.addWidget(self.mukellef_vkn, 1, 1)
        pg.addWidget(self.skip_delete, 1, 2, 1, 2)
        params.layout_().addLayout(pg)
        root.addWidget(params)

        # ── aksiyon + ilerleme ──
        action = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("Hazır")
        action.addWidget(self.progress, 1)
        self.btn_cancel = QPushButton("İptal")
        self.btn_cancel.setObjectName("Ghost")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_start = QPushButton("Aktarımı Başlat")
        self.btn_start.setObjectName("Primary")
        self.btn_start.clicked.connect(self._start)
        action.addWidget(self.btn_cancel)
        action.addWidget(self.btn_start)
        root.addLayout(action)

        # ── log konsolu ──
        self.console = QPlainTextEdit()
        self.console.setObjectName("LogConsole")
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(180)
        root.addWidget(self.console, 1)

        self.reload_connections()

    def reload_connections(self):
        conns = self.store.all()
        self.src.set_connections(conns)
        self.tgt.set_connections(conns)
        self._validate()

    # ── yön doğrulama ──
    def _validate(self) -> bool:
        s, t = self.src.current(), self.tgt.current()
        if not s or not t:
            self.dir_banner.setText("Kaynak ve hedef seçin.")
            self.dir_banner.setStyleSheet(
                "padding:10px;border-radius:8px;background:#F4F6FB;color:#5A6478;font-weight:600;")
            self.arrow.setText("→")
            self.arrow.setStyleSheet("font-size:30px;color:#5A6478;font-weight:700;")
            self.btn_start.setEnabled(False)
            return False

        chk = check_direction(s.env, t.env)
        if chk.allowed:
            self.dir_banner.setText("✓ " + chk.reason)
            self.dir_banner.setStyleSheet(
                f"padding:10px;border-radius:8px;background:#E6F6EC;color:#1B6E45;font-weight:600;")
            self.arrow.setText("→")
            self.arrow.setStyleSheet(f"font-size:30px;color:{COLORS['ok']};font-weight:700;")
            self.btn_start.setEnabled(not (self.worker and self.worker.isRunning()))
            return True
        else:
            self.dir_banner.setText("⛔ " + chk.reason)
            self.dir_banner.setStyleSheet(
                f"padding:10px;border-radius:8px;background:#FEEBEC;color:#A01F23;font-weight:600;")
            self.arrow.setText("✕")
            self.arrow.setStyleSheet(f"font-size:30px;color:{COLORS['danger']};font-weight:700;")
            self.btn_start.setEnabled(False)
            return False

    def _append(self, level: str, msg: str):
        color = LEVEL_COLORS.get(level, "#D7E0F4")
        ts = datetime.now().strftime("%H:%M:%S")
        prefix = {"ok": "✓", "warn": "⚠", "error": "✕", "step": "▸", "info": "·"}.get(level, "·")
        self.console.appendHtml(
            f'<span style="color:#5A6478">{ts}</span> '
            f'<span style="color:{color}">{prefix} {msg}</span>'
        )
        self.console.verticalScrollBar().setValue(
            self.console.verticalScrollBar().maximum())

    # ── başlat / iptal ──
    def _start(self):
        if not self._validate():
            return
        bid = self.beyanname_id.text().strip()
        if not bid.isdigit():
            QMessageBox.warning(self, "Geçersiz ID", "Beyanname ID sayısal olmalı.")
            return

        s, t = self.src.current(), self.tgt.current()
        # Prod hedef olamaz ama yine de hedef PROD ise ekstra uyarı (savunma katmanı)
        confirm = QMessageBox.question(
            self, "Aktarımı onayla",
            f"{s.name} ({s.env.label})\n→ {t.name} ({t.env.label})\n\n"
            f"Beyanname ID: {bid}\n"
            f"{'Mevcut veri korunacak' if self.skip_delete.isChecked() else 'Hedefteki aynı kayıt silinip yeniden yazılacak'}.\n\n"
            "Devam edilsin mi?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.console.clear()
        self.progress.setValue(0)
        self.progress.setFormat("Başlıyor...")
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        self.worker = TransferWorker(
            source=s, target=t, beyanname_id=int(bid),
            created_by=self.created_by.text().strip() or None,
            mukellef_vkn=self.mukellef_vkn.text().strip() or None,
            skip_delete=self.skip_delete.isChecked(),
        )
        self.worker.log.connect(self._append)
        self.worker.percent.connect(self._on_percent)
        self.worker.finished_run.connect(self._on_done)
        self.worker.blocked.connect(self._on_blocked)
        self.worker.start()

    def _on_percent(self, c: int, total: int):
        if total > 0:
            pct = int(c / total * 100)
            self.progress.setValue(pct)
            self.progress.setFormat(f"%{pct}  ({c}/{total} tablo)")

    def _on_blocked(self, msg: str):
        self.progress.setFormat("Engellendi")
        self._reset_buttons()
        QMessageBox.critical(self, "Yön yasağı", msg)

    def _on_done(self, summary):
        self._reset_buttons()
        if summary is None:
            return
        if summary.fatal_error:
            self.progress.setFormat("Hata")
            self._append("error", f"Aktarım başarısız: {summary.fatal_error}")
        else:
            self.progress.setValue(100)
            status = "tamamlandı" if summary.ok else "uyarılarla tamamlandı"
            self.progress.setFormat(f"%100 — {status}")
            self._append("ok",
                f"Bitti: {summary.total_rows} satır, "
                f"{summary.skipped_tables} tablo atlandı, "
                f"{summary.total_errors} hata.")

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self._append("warn", "İptal isteniyor...")

    def _reset_buttons(self):
        self.btn_cancel.setEnabled(False)
        self._validate()

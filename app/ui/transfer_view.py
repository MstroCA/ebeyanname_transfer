# -*- coding: utf-8 -*-
"""Transfer screen: source/target, profile, generic params, dry-run, live log."""

from __future__ import annotations

import json
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QLineEdit, QPushButton, QPlainTextEdit, QProgressBar, QCheckBox,
    QMessageBox, QFrame, QInputDialog,
)

from ..core.environments import EnvironmentRegistry, check_direction
from ..core.store import Connection, ConnectionStore
from ..core.profiles import ProfileStore, TransferProfile, BUILTIN_PROFILES
from .widgets import Card, db_icon_label, env_color
from .transfer_worker import TransferWorker
from .theme import COLORS


LEVEL_COLORS = {
    "info": "#9FB0D0", "ok": "#5DD39E", "warn": "#F5C26B",
    "error": "#F08A8E", "step": "#8FB8FF",
}


class EndpointCard(Card):
    selection_changed = Signal()

    def __init__(self, role_title: str, parent=None):
        super().__init__(parent)
        lay = self.layout_()
        head = QLabel(role_title)
        head.setObjectName("FieldLabel")
        lay.addWidget(head)

        row = QHBoxLayout()
        row.setSpacing(14)
        from ..core.environments import LOCAL
        self.icon = db_icon_label(LOCAL, 52)
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
        self.profile_store = ProfileStore()
        self.worker: TransferWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        t = QLabel("Transfer")
        t.setObjectName("PageTitle")
        root.addWidget(t)
        self.sub = QLabel(self._build_subtitle())
        self.sub.setObjectName("PageSub")
        self.sub.setWordWrap(True)
        root.addWidget(self.sub)

        # ── Profile selector ──
        prof_row = QHBoxLayout()
        prof_row.setSpacing(10)
        prof_lbl = QLabel("Profile")
        prof_lbl.setObjectName("FieldLabel")
        prof_lbl.setFixedWidth(80)
        self.profile_combo = QComboBox()
        self.profile_combo.currentIndexChanged.connect(self._on_profile_change)
        self.btn_save_profile = QPushButton("Save as Profile")
        self.btn_save_profile.setObjectName("Ghost")
        self.btn_save_profile.clicked.connect(self._save_profile)
        prof_row.addWidget(prof_lbl)
        prof_row.addWidget(self.profile_combo, 1)
        prof_row.addWidget(self.btn_save_profile)
        root.addLayout(prof_row)

        # ── source → arrow → target ──
        endpoints = QHBoxLayout()
        endpoints.setSpacing(14)
        self.src = EndpointCard("SOURCE")
        self.tgt = EndpointCard("TARGET")
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

        # ── direction banner ──
        self.dir_banner = QLabel("")
        self.dir_banner.setWordWrap(True)
        self.dir_banner.setAlignment(Qt.AlignCenter)
        self.dir_banner.setStyleSheet("padding:10px; border-radius:8px; font-weight:600;")
        root.addWidget(self.dir_banner)

        # ── parameters ──
        params = Card()
        pg = QGridLayout()
        pg.setHorizontalSpacing(14)
        pg.setVerticalSpacing(10)

        self.root_table = QLineEdit()
        self.root_table.setPlaceholderText("e.g. beyanname, order, invoice")
        self.pk_column = QLineEdit()
        self.pk_column.setPlaceholderText("Primary key column (default: id)")
        self.pk_column.setText("id")
        self.fk_column = QLineEdit()
        self.fk_column.setPlaceholderText("FK column in child tables (e.g. order_id)")
        self.record_id = QLineEdit()
        self.record_id.setPlaceholderText("Record ID value (e.g. 42)")
        self.created_by_field = QLineEdit()
        self.created_by_field.setPlaceholderText("Optional — override created_by / updated_by")
        self.field_overrides = QLineEdit()
        self.field_overrides.setPlaceholderText('Optional JSON e.g. {"env_tag": "local"}')
        self.skip_delete = QCheckBox("Keep existing data in target (skip delete)")
        self.dry_run = QCheckBox("Dry run — preview only, no writes")
        self.dry_run.stateChanged.connect(self._on_dry_run_change)

        def fl(txt):
            l = QLabel(txt)
            l.setObjectName("FieldLabel")
            return l

        pg.addWidget(fl("Root Table *"), 0, 0)
        pg.addWidget(self.root_table, 0, 1)
        pg.addWidget(fl("PK Column"), 0, 2)
        pg.addWidget(self.pk_column, 0, 3)
        pg.addWidget(fl("FK Column *"), 1, 0)
        pg.addWidget(self.fk_column, 1, 1)
        pg.addWidget(fl("Record ID *"), 1, 2)
        pg.addWidget(self.record_id, 1, 3)
        pg.addWidget(fl("created_by"), 2, 0)
        pg.addWidget(self.created_by_field, 2, 1)
        pg.addWidget(fl("Field Overrides"), 2, 2)
        pg.addWidget(self.field_overrides, 2, 3)
        pg.addWidget(self.skip_delete, 3, 0, 1, 2)
        pg.addWidget(self.dry_run, 3, 2, 1, 2)
        params.layout_().addLayout(pg)
        root.addWidget(params)

        # ── action + progress ──
        action = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setValue(0)
        self.progress.setFormat("Ready")
        action.addWidget(self.progress, 1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("Ghost")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_start = QPushButton("Start Transfer")
        self.btn_start.setObjectName("Primary")
        self.btn_start.clicked.connect(self._start)
        action.addWidget(self.btn_cancel)
        action.addWidget(self.btn_start)
        root.addLayout(action)

        # ── log console ──
        self.console = QPlainTextEdit()
        self.console.setObjectName("LogConsole")
        self.console.setReadOnly(True)
        self.console.setMinimumHeight(180)
        root.addWidget(self.console, 1)

        self._load_profiles()
        self.reload_connections()

    def _build_subtitle(self) -> str:
        envs = EnvironmentRegistry.instance().all()
        high = [e for e in envs if e.rank >= 2]
        low = [e for e in envs if e.rank < 2]
        if high and low:
            h = "/".join(e.label for e in high[:3])
            l = "/".join(e.label for e in low[:2])
            return f"Data flows downstream only ({h} → {l}). Select source and target, then configure the record to transfer."
        return "Select source and target connections, then configure the record to transfer."

    def _load_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for p in self.profile_store.all():
            self.profile_combo.addItem(p.name, p.id)
        self.profile_combo.blockSignals(False)
        if self.profile_combo.count() > 0:
            self._on_profile_change(0)

    def _on_profile_change(self, idx: int):
        pid = self.profile_combo.currentData()
        p = self.profile_store.get(pid)
        if p:
            self.root_table.setText(p.root_table)
            self.pk_column.setText(p.pk_column)
            self.fk_column.setText(p.fk_column)

    def _save_profile(self):
        rt = self.root_table.text().strip()
        fk = self.fk_column.text().strip()
        if not rt or not fk:
            QMessageBox.warning(self, "Missing fields", "Root Table and FK Column are required to save a profile.")
            return
        name, ok = QInputDialog.getText(self, "Save Profile", "Profile name:")
        if ok and name.strip():
            p = TransferProfile.new(
                name=name.strip(), root_table=rt,
                fk_column=fk, pk_column=self.pk_column.text().strip() or "id",
            )
            self.profile_store.add(p)
            self._load_profiles()

    def _on_dry_run_change(self, state: int):
        if state:
            self.btn_start.setText("Preview (Dry Run)")
            self.btn_start.setStyleSheet(
                f"background:{COLORS['warn']}; color:white; border:none; border-radius:8px; padding:9px 16px; font-weight:600;"
            )
        else:
            self.btn_start.setText("Start Transfer")
            self.btn_start.setStyleSheet("")
            self.btn_start.setObjectName("Primary")

    def reload_connections(self):
        conns = self.store.all()
        self.src.set_connections(conns)
        self.tgt.set_connections(conns)
        self.sub.setText(self._build_subtitle())
        self._validate()

    def _validate(self) -> bool:
        s, t = self.src.current(), self.tgt.current()
        if not s or not t:
            self.dir_banner.setText("Select source and target connections.")
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
                "padding:10px;border-radius:8px;background:#E6F6EC;color:#1B6E45;font-weight:600;")
            self.arrow.setText("→")
            self.arrow.setStyleSheet(f"font-size:30px;color:{COLORS['ok']};font-weight:700;")
            self.btn_start.setEnabled(not (self.worker and self.worker.isRunning()))
            return True
        else:
            self.dir_banner.setText("⛔ " + chk.reason)
            self.dir_banner.setStyleSheet(
                "padding:10px;border-radius:8px;background:#FEEBEC;color:#A01F23;font-weight:600;")
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
        self.console.verticalScrollBar().setValue(self.console.verticalScrollBar().maximum())

    def _start(self):
        if not self._validate():
            return
        rt = self.root_table.text().strip()
        fk = self.fk_column.text().strip()
        pk = self.pk_column.text().strip() or "id"
        rid = self.record_id.text().strip()
        if not rt:
            QMessageBox.warning(self, "Missing", "Root Table is required.")
            return
        if not fk:
            QMessageBox.warning(self, "Missing", "FK Column is required.")
            return
        if not rid:
            QMessageBox.warning(self, "Missing", "Record ID is required.")
            return

        # Parse field overrides
        overrides_raw = self.field_overrides.text().strip()
        field_overrides = {}
        if overrides_raw:
            try:
                field_overrides = json.loads(overrides_raw)
                if not isinstance(field_overrides, dict):
                    raise ValueError("Must be a JSON object")
            except (json.JSONDecodeError, ValueError) as e:
                QMessageBox.warning(self, "Invalid JSON", f"Field Overrides must be a JSON object:\n{e}")
                return

        s, t = self.src.current(), self.tgt.current()
        is_dry = self.dry_run.isChecked()
        action = "Preview (Dry Run)" if is_dry else "Transfer"

        confirm = QMessageBox.question(
            self, f"Confirm {action}",
            f"{s.name} ({s.env.label})\n→ {t.name} ({t.env.label})\n\n"
            f"Table: {rt}  |  FK: {fk}  |  Record ID: {rid}\n"
            f"{'⚡ DRY RUN — no data will be written' if is_dry else ('Keep existing' if self.skip_delete.isChecked() else 'Overwrite existing')}.\n\n"
            "Continue?",
        )
        if confirm != QMessageBox.Yes:
            return

        self.console.clear()
        self.progress.setValue(0)
        self.progress.setFormat("Starting...")
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)

        cb = self.created_by_field.text().strip() or None

        self.worker = TransferWorker(
            source=s, target=t,
            record_id=rid, root_table=rt, pk_column=pk, fk_column=fk,
            created_by=cb, field_overrides=field_overrides or None,
            skip_delete=self.skip_delete.isChecked(),
            dry_run=is_dry,
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
            self.progress.setFormat(f"%{pct}  ({c}/{total} tables)")

    def _on_blocked(self, msg: str):
        self.progress.setFormat("Blocked")
        self._reset_buttons()
        QMessageBox.critical(self, "Direction blocked", msg)

    def _on_done(self, summary):
        self._reset_buttons()
        if summary is None:
            return
        tag = "[DRY RUN] " if (summary and summary.dry_run) else ""
        if summary.fatal_error:
            self.progress.setFormat("Error")
            self._append("error", f"Transfer failed: {summary.fatal_error}")
        else:
            self.progress.setValue(100)
            status = "completed" if summary.ok else "completed with warnings"
            self.progress.setFormat(f"%100 — {tag}{status}")
            self._append("ok",
                f"{tag}Done: {summary.total_rows} rows, "
                f"{summary.skipped_tables} tables skipped, "
                f"{summary.total_errors} errors.")

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self._append("warn", "Cancellation requested...")

    def _reset_buttons(self):
        self.btn_cancel.setEnabled(False)
        self._validate()

# -*- coding: utf-8 -*-
"""Veritabanı tanımlama menüsü: bağlantıları ekle/düzenle/sil/test et."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QSpinBox, QComboBox, QPushButton, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QPlainTextEdit, QAbstractItemView,
)

from ..core.environments import Environment
from ..core.store import Connection, ConnectionStore
from ..core.engine import TransferEngine
from .widgets import Card, db_icon_label, env_color


class _TestWorker(QThread):
    done = Signal(bool, str)

    def __init__(self, conn: Connection):
        super().__init__()
        self.conn = conn

    def run(self):
        ok, msg = TransferEngine.test_connection(self.conn)
        self.done.emit(ok, msg)


class ConnectionDialog(QDialog):
    """Tek bağlantı tanımlama/düzenleme formu."""

    def __init__(self, parent=None, conn: Connection | None = None):
        super().__init__(parent)
        self.setWindowTitle("Veritabanı Tanımı")
        self.setMinimumWidth(460)
        self._conn = conn
        self._worker: _TestWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        title = QLabel("Veritabanı Tanımı")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(12)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Ör: Prod KATV")
        self.env = QComboBox()
        for e in (Environment.PROD, Environment.TEST, Environment.LOCAL):
            self.env.addItem(e.label, e.value)
        self.host = QLineEdit()
        self.host.setPlaceholderText("localhost veya sunucu adresi")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(5432)
        self.dbname = QLineEdit()
        self.dbname.setPlaceholderText("beyan_katv")
        self.user = QLineEdit()
        self.user.setPlaceholderText("postgres")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.note = QLineEdit()
        self.note.setPlaceholderText("İsteğe bağlı not")

        def lbl(t):
            l = QLabel(t)
            l.setObjectName("FieldLabel")
            return l

        rows = [
            ("Ad", self.name),
            ("Ortam", self.env),
            ("Host", self.host),
            ("Port", self.port),
            ("Veritabanı", self.dbname),
            ("Kullanıcı", self.user),
            ("Şifre", self.password),
            ("Not", self.note),
        ]
        for i, (t, w) in enumerate(rows):
            grid.addWidget(lbl(t), i, 0, Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(w, i, 1)
        root.addLayout(grid)

        self.test_status = QLabel("")
        self.test_status.setWordWrap(True)
        root.addWidget(self.test_status)

        btns = QHBoxLayout()
        self.btn_test = QPushButton("Bağlantıyı Test Et")
        self.btn_test.setObjectName("Ghost")
        self.btn_test.clicked.connect(self._on_test)
        btns.addWidget(self.btn_test)
        btns.addStretch()
        cancel = QPushButton("İptal")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Kaydet")
        save.setObjectName("Primary")
        save.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        root.addLayout(btns)

        if conn:
            self._fill(conn)

    def _fill(self, c: Connection):
        self.name.setText(c.name)
        idx = self.env.findData(c.environment)
        if idx >= 0:
            self.env.setCurrentIndex(idx)
        self.host.setText(c.host)
        self.port.setValue(c.port)
        self.dbname.setText(c.dbname)
        self.user.setText(c.user)
        self.password.setText(c.password)
        self.note.setText(c.note)

    def _collect(self) -> Connection | None:
        name = self.name.text().strip()
        host = self.host.text().strip()
        dbname = self.dbname.text().strip()
        user = self.user.text().strip()
        if not all([name, host, dbname, user]):
            QMessageBox.warning(self, "Eksik bilgi",
                                "Ad, Host, Veritabanı ve Kullanıcı zorunludur.")
            return None
        env_val = self.env.currentData()
        if self._conn:
            c = self._conn
            c.name, c.environment, c.host = name, env_val, host
            c.port, c.dbname, c.user = self.port.value(), dbname, user
            c.password, c.note = self.password.text(), self.note.text().strip()
            return c
        return Connection.new(
            name=name, environment=env_val, host=host, port=self.port.value(),
            dbname=dbname, user=user, password=self.password.text(),
            note=self.note.text().strip(),
        )

    def _on_test(self):
        c = self._collect()
        if not c:
            return
        self.btn_test.setEnabled(False)
        self.test_status.setText("Bağlanılıyor...")
        self.test_status.setStyleSheet("color:#5A6478;")
        self._worker = _TestWorker(c)
        self._worker.done.connect(self._test_done)
        self._worker.start()

    def _test_done(self, ok: bool, msg: str):
        self.btn_test.setEnabled(True)
        if ok:
            self.test_status.setText("✓ " + msg)
            self.test_status.setStyleSheet("color:#30A46C; font-weight:600;")
        else:
            self.test_status.setText("✕ " + msg)
            self.test_status.setStyleSheet("color:#E5484D;")

    def _on_save(self):
        c = self._collect()
        if c:
            self.result_conn = c
            self.accept()


class ConnectionsView(QWidget):
    """Tanımlı veritabanlarının listesi + yönetim."""

    changed = Signal()

    def __init__(self, store: ConnectionStore, parent=None):
        super().__init__(parent)
        self.store = store

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        head = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("Veritabanları")
        t.setObjectName("PageTitle")
        s = QLabel("Aktarımda kullanılacak veritabanı bağlantılarını tanımlayın. "
                   "Şifreler bu makineye özel olarak şifreli saklanır.")
        s.setObjectName("PageSub")
        s.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(s)
        head.addLayout(col)
        head.addStretch()
        add = QPushButton("+ Yeni Veritabanı")
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        head.addWidget(add, alignment=Qt.AlignTop)
        root.addLayout(head)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Ortam", "Ad", "Bağlantı", "Kullanıcı", "İşlem"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.setColumnWidth(0, 130)
        self.table.setColumnWidth(4, 180)
        self.table.verticalHeader().setDefaultSectionSize(56)
        root.addWidget(self.table)

        self.empty = QLabel("Henüz veritabanı tanımlanmadı. Sağ üstten yeni bir bağlantı ekleyin.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color:#5A6478; padding:40px;")
        root.addWidget(self.empty)

        self.refresh()

    def refresh(self):
        conns = self.store.all()
        self.empty.setVisible(not conns)
        self.table.setVisible(bool(conns))
        self.table.setRowCount(0)
        for c in conns:
            self._add_row(c)

    def _env_cell(self, c: Connection) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(8)
        lay.addWidget(db_icon_label(c.env, 28))
        tag = QLabel(c.env.label)
        tag.setStyleSheet(
            f"color:{env_color(c.env)}; font-weight:700; font-size:12px;")
        lay.addWidget(tag)
        lay.addStretch()
        return w

    def _add_row(self, c: Connection):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setCellWidget(r, 0, self._env_cell(c))
        self.table.setItem(r, 1, QTableWidgetItem(c.name))
        self.table.setItem(r, 2, QTableWidgetItem(c.masked_summary()))
        self.table.setItem(r, 3, QTableWidgetItem(c.user))

        act = QWidget()
        lay = QHBoxLayout(act)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)
        edit = QPushButton("Düzenle")
        edit.setObjectName("Ghost")
        edit.setMinimumWidth(72)
        edit.clicked.connect(lambda _, cc=c: self._edit(cc))
        dele = QPushButton("Sil")
        dele.setObjectName("Danger")
        dele.setMinimumWidth(48)
        dele.clicked.connect(lambda _, cc=c: self._delete(cc))
        lay.addWidget(edit)
        lay.addWidget(dele)
        self.table.setCellWidget(r, 4, act)

    def _add(self):
        dlg = ConnectionDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.store.add(dlg.result_conn)
            self.refresh()
            self.changed.emit()

    def _edit(self, c: Connection):
        dlg = ConnectionDialog(self, conn=c)
        if dlg.exec() == QDialog.Accepted:
            self.store.update(dlg.result_conn)
            self.refresh()
            self.changed.emit()

    def _delete(self, c: Connection):
        if QMessageBox.question(
            self, "Silinsin mi?",
            f"'{c.name}' bağlantısı silinecek. Emin misiniz?",
        ) == QMessageBox.Yes:
            self.store.remove(c.id)
            self.refresh()
            self.changed.emit()

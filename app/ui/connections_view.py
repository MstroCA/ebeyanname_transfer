# -*- coding: utf-8 -*-
"""Connection management: list, add, edit, delete, test."""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QSpinBox, QComboBox, QPushButton, QDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QAbstractItemView, QDialogButtonBox,
    QScrollArea, QFrame,
)

from ..core.environments import Environment, EnvironmentRegistry
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


# ── Environment manager dialog ────────────────────────────────────────────────

class ManageEnvironmentsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Environments")
        self.setMinimumWidth(460)
        self.registry = EnvironmentRegistry.instance()

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        root.addWidget(QLabel("Built-in environments cannot be removed. Add custom environments below."))

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Rank", "Type"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        root.addWidget(self.table)

        # add new env row
        add_row = QHBoxLayout()
        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("Environment name (e.g. UAT)")
        self.new_rank = QSpinBox()
        self.new_rank.setRange(1, 10)
        self.new_rank.setValue(2)
        self.new_rank.setPrefix("rank ")
        add_btn = QPushButton("Add")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self._add)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.setObjectName("Danger")
        remove_btn.clicked.connect(self._remove)
        add_row.addWidget(self.new_name, 1)
        add_row.addWidget(self.new_rank)
        add_row.addWidget(add_btn)
        add_row.addWidget(remove_btn)
        root.addLayout(add_row)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.accept)
        root.addWidget(btns)

        self._refresh()

    def _refresh(self):
        from ..core.environments import BUILTIN_ENVIRONMENTS
        builtin_names = {e.name.upper() for e in BUILTIN_ENVIRONMENTS}
        self.table.setRowCount(0)
        for env in self.registry.all():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(env.name))
            self.table.setItem(r, 1, QTableWidgetItem(str(env.rank)))
            typ = "Built-in" if env.name.upper() in builtin_names else "Custom"
            self.table.setItem(r, 2, QTableWidgetItem(typ))

    def _add(self):
        name = self.new_name.text().strip().upper()
        if not name:
            return
        self.registry.add_custom(name, self.new_rank.value())
        self.new_name.clear()
        self._refresh()

    def _remove(self):
        rows = self.table.selectedItems()
        if not rows:
            return
        row = self.table.currentRow()
        name = self.table.item(row, 0).text()
        typ = self.table.item(row, 2).text()
        if typ == "Built-in":
            QMessageBox.warning(self, "Cannot Remove", "Built-in environments cannot be removed.")
            return
        self.registry.remove_custom(name)
        self._refresh()


# ── Connection dialog ─────────────────────────────────────────────────────────

class ConnectionDialog(QDialog):
    def __init__(self, parent=None, conn: Connection | None = None):
        super().__init__(parent)
        self.setWindowTitle("Database Connection")
        self.setMinimumWidth(480)
        self._conn = conn
        self._worker: _TestWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        title = QLabel("Database Connection")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(12)

        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Prod Main DB")

        self.env_combo = QComboBox()
        for e in EnvironmentRegistry.instance().all():
            self.env_combo.addItem(f"{e.label}  ({e.name})", e.name)

        self.db_type = QComboBox()
        self.db_type.addItem("PostgreSQL", "postgresql")
        self.db_type.addItem("MySQL / MariaDB", "mysql")
        self.db_type.currentIndexChanged.connect(self._on_db_type_change)

        self.host = QLineEdit()
        self.host.setPlaceholderText("localhost or server address")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(5432)
        self.dbname = QLineEdit()
        self.dbname.setPlaceholderText("database name")
        self.user = QLineEdit()
        self.user.setPlaceholderText("postgres")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.note = QLineEdit()
        self.note.setPlaceholderText("Optional note")

        def lbl(t):
            l = QLabel(t)
            l.setObjectName("FieldLabel")
            return l

        rows = [
            ("Name", self.name),
            ("Environment", self.env_combo),
            ("DB Type", self.db_type),
            ("Host", self.host),
            ("Port", self.port),
            ("Database", self.dbname),
            ("User", self.user),
            ("Password", self.password),
            ("Note", self.note),
        ]
        for i, (t, w) in enumerate(rows):
            grid.addWidget(lbl(t), i, 0, Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(w, i, 1)
        root.addLayout(grid)

        self.test_status = QLabel("")
        self.test_status.setWordWrap(True)
        root.addWidget(self.test_status)

        btns = QHBoxLayout()
        self.btn_test = QPushButton("Test Connection")
        self.btn_test.setObjectName("Ghost")
        self.btn_test.clicked.connect(self._on_test)
        btns.addWidget(self.btn_test)
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("Primary")
        save.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        root.addLayout(btns)

        if conn:
            self._fill(conn)

    def _on_db_type_change(self, idx: int):
        db_type = self.db_type.currentData()
        default_port = 3306 if db_type == "mysql" else 5432
        self.port.setValue(default_port)

    def _fill(self, c: Connection):
        self.name.setText(c.name)
        idx = self.env_combo.findData(c.environment)
        if idx >= 0:
            self.env_combo.setCurrentIndex(idx)
        idx2 = self.db_type.findData(c.db_type)
        if idx2 >= 0:
            self.db_type.setCurrentIndex(idx2)
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
            QMessageBox.warning(self, "Missing fields", "Name, Host, Database and User are required.")
            return None
        env_val = self.env_combo.currentData()
        db_type = self.db_type.currentData()
        if self._conn:
            c = self._conn
            c.name, c.environment, c.host = name, env_val, host
            c.port, c.dbname, c.user = self.port.value(), dbname, user
            c.password = self.password.text()
            c.db_type = db_type
            c.note = self.note.text().strip()
            return c
        return Connection.new(
            name=name, environment=env_val, host=host, port=self.port.value(),
            dbname=dbname, user=user, password=self.password.text(),
            db_type=db_type, note=self.note.text().strip(),
        )

    def _on_test(self):
        c = self._collect()
        if not c:
            return
        self.btn_test.setEnabled(False)
        self.test_status.setText("Connecting...")
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


# ── Connections list view ─────────────────────────────────────────────────────

class ConnectionsView(QWidget):
    changed = Signal()

    def __init__(self, store: ConnectionStore, parent=None):
        super().__init__(parent)
        self.store = store

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        head = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("Connections")
        t.setObjectName("PageTitle")
        s = QLabel("Define database connections for transfers. Passwords are encrypted on this machine.")
        s.setObjectName("PageSub")
        s.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(s)
        head.addLayout(col)
        head.addStretch()

        btn_envs = QPushButton("Environments")
        btn_envs.setObjectName("Ghost")
        btn_envs.clicked.connect(self._manage_envs)
        head.addWidget(btn_envs, alignment=Qt.AlignTop)

        add = QPushButton("+ New Connection")
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        head.addWidget(add, alignment=Qt.AlignTop)
        root.addLayout(head)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Env", "Type", "Name", "Connection", "User", "Actions"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Stretch)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(56)
        root.addWidget(self.table)

        self.empty = QLabel("No connections defined yet. Click '+ New Connection' to add one.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("color:#5A6478; padding:40px;")
        root.addWidget(self.empty)

        self.refresh()

    def _manage_envs(self):
        dlg = ManageEnvironmentsDialog(self)
        dlg.exec()
        self.changed.emit()

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
        tag.setStyleSheet(f"color:{env_color(c.env)}; font-weight:700; font-size:12px;")
        lay.addWidget(tag)
        lay.addStretch()
        return w

    def _add_row(self, c: Connection):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setCellWidget(r, 0, self._env_cell(c))

        db_label = QLabel("PG" if c.db_type == "postgresql" else "MY")
        db_label.setAlignment(Qt.AlignCenter)
        color = "#3D63DD" if c.db_type == "postgresql" else "#E57D00"
        db_label.setStyleSheet(
            f"background:{color}20; color:{color}; border-radius:6px; "
            f"padding:2px 8px; font-weight:700; font-size:11px;"
        )
        wrap = QWidget()
        wl = QHBoxLayout(wrap)
        wl.setContentsMargins(6, 4, 6, 4)
        wl.addWidget(db_label)
        self.table.setCellWidget(r, 1, wrap)

        self.table.setItem(r, 2, QTableWidgetItem(c.name))
        self.table.setItem(r, 3, QTableWidgetItem(c.masked_summary()))
        self.table.setItem(r, 4, QTableWidgetItem(c.user))

        act = QWidget()
        lay = QHBoxLayout(act)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)
        edit = QPushButton("Edit")
        edit.setObjectName("Ghost")
        edit.clicked.connect(lambda _, cc=c: self._edit(cc))
        dele = QPushButton("Delete")
        dele.setObjectName("Danger")
        dele.clicked.connect(lambda _, cc=c: self._delete(cc))
        lay.addWidget(edit)
        lay.addWidget(dele)
        self.table.setCellWidget(r, 5, act)

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
            self, "Delete?",
            f"Delete connection '{c.name}'?",
        ) == QMessageBox.Yes:
            self.store.remove(c.id)
            self.refresh()
            self.changed.emit()

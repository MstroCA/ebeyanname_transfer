# -*- coding: utf-8 -*-
"""Profile management: list, add, edit, delete transfer profiles."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QAbstractItemView, QPlainTextEdit,
)

from ..core.profiles import ProfileStore, TransferProfile
from .widgets import Card


class ProfileDialog(QDialog):
    def __init__(self, parent=None, profile: TransferProfile | None = None):
        super().__init__(parent)
        self.setWindowTitle("Transfer Profile")
        self.setMinimumWidth(440)
        self._profile = profile

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(14)

        title = QLabel("Transfer Profile")
        title.setObjectName("SectionTitle")
        root.addWidget(title)

        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(12)

        self.name = QLineEdit()
        self.name.setPlaceholderText("e.g. Order Records")
        self.root_table = QLineEdit()
        self.root_table.setPlaceholderText("e.g. order")
        self.pk_column = QLineEdit()
        self.pk_column.setPlaceholderText("Primary key column (usually id)")
        self.pk_column.setText("id")
        self.fk_column = QLineEdit()
        self.fk_column.setPlaceholderText("e.g. order_id")
        self.description = QLineEdit()
        self.description.setPlaceholderText("Optional description")

        def lbl(t):
            l = QLabel(t)
            l.setObjectName("FieldLabel")
            return l

        rows = [
            ("Name *", self.name),
            ("Root Table *", self.root_table),
            ("PK Column", self.pk_column),
            ("FK Column *", self.fk_column),
            ("Description", self.description),
        ]
        for i, (t, w) in enumerate(rows):
            grid.addWidget(lbl(t), i, 0, Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(w, i, 1)
        root.addLayout(grid)

        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save")
        save.setObjectName("Primary")
        save.clicked.connect(self._on_save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        root.addLayout(btns)

        if profile:
            self._fill(profile)

    def _fill(self, p: TransferProfile):
        self.name.setText(p.name)
        self.root_table.setText(p.root_table)
        self.pk_column.setText(p.pk_column)
        self.fk_column.setText(p.fk_column)
        self.description.setText(p.description)

    def _on_save(self):
        name = self.name.text().strip()
        rt = self.root_table.text().strip()
        fk = self.fk_column.text().strip()
        if not all([name, rt, fk]):
            QMessageBox.warning(self, "Missing fields", "Name, Root Table and FK Column are required.")
            return
        if self._profile and not self._profile.is_builtin:
            self._profile.name = name  # type: ignore[misc]
            self._profile.root_table = rt  # type: ignore[misc]
            self._profile.pk_column = self.pk_column.text().strip() or "id"  # type: ignore[misc]
            self._profile.fk_column = fk  # type: ignore[misc]
            self._profile.description = self.description.text().strip()  # type: ignore[misc]
            self.result_profile = self._profile
        else:
            self.result_profile = TransferProfile.new(
                name=name, root_table=rt,
                fk_column=fk,
                pk_column=self.pk_column.text().strip() or "id",
                description=self.description.text().strip(),
            )
        self.accept()


class ProfilesView(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.store = ProfileStore()

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        head = QHBoxLayout()
        col = QVBoxLayout()
        t = QLabel("Profiles")
        t.setObjectName("PageTitle")
        s = QLabel("Save reusable table + FK column configurations. Built-in profiles cannot be deleted.")
        s.setObjectName("PageSub")
        s.setWordWrap(True)
        col.addWidget(t)
        col.addWidget(s)
        head.addLayout(col)
        head.addStretch()
        add = QPushButton("+ New Profile")
        add.setObjectName("Primary")
        add.clicked.connect(self._add)
        head.addWidget(add, alignment=Qt.AlignTop)
        root.addLayout(head)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Root Table", "FK Column", "Description", "Actions"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.Stretch)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setDefaultSectionSize(50)
        root.addWidget(self.table)

        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for p in self.store.all():
            self._add_row(p)

    def _add_row(self, p: TransferProfile):
        r = self.table.rowCount()
        self.table.insertRow(r)

        name_item = QTableWidgetItem(p.name)
        if p.is_builtin:
            name_item.setForeground(self.table.palette().mid())
        self.table.setItem(r, 0, name_item)
        self.table.setItem(r, 1, QTableWidgetItem(p.root_table or "—"))
        self.table.setItem(r, 2, QTableWidgetItem(p.fk_column or "—"))
        self.table.setItem(r, 3, QTableWidgetItem(p.description))

        act = QWidget()
        lay = QHBoxLayout(act)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(6)

        if not p.is_builtin:
            edit = QPushButton("Edit")
            edit.setObjectName("Ghost")
            edit.clicked.connect(lambda _, pp=p: self._edit(pp))
            dele = QPushButton("Delete")
            dele.setObjectName("Danger")
            dele.clicked.connect(lambda _, pp=p: self._delete(pp))
            lay.addWidget(edit)
            lay.addWidget(dele)
        else:
            tag = QLabel("Built-in")
            tag.setStyleSheet("color:#8A93A6; font-size:11px;")
            lay.addWidget(tag)
        self.table.setCellWidget(r, 4, act)

    def _add(self):
        dlg = ProfileDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.store.add(dlg.result_profile)
            self.refresh()
            self.changed.emit()

    def _edit(self, p: TransferProfile):
        dlg = ProfileDialog(self, profile=p)
        if dlg.exec() == QDialog.Accepted:
            self.store.update(dlg.result_profile)
            self.refresh()
            self.changed.emit()

    def _delete(self, p: TransferProfile):
        if QMessageBox.question(
            self, "Delete?", f"Delete profile '{p.name}'?"
        ) == QMessageBox.Yes:
            self.store.remove(p.id)
            self.refresh()
            self.changed.emit()

package io.recordrelay.ui.panels

import com.intellij.ui.components.JBScrollPane
import io.recordrelay.core.TransferProfile
import io.recordrelay.store.ProfileStore
import io.recordrelay.ui.dialogs.ProfileDialog
import java.awt.*
import javax.swing.*
import javax.swing.table.DefaultTableModel
import javax.swing.table.DefaultTableCellRenderer

class ProfilesPanel(
    private val store: ProfileStore,
    private val onChanged: () -> Unit
) : JPanel(BorderLayout()) {

    private val tableModel = object : DefaultTableModel(arrayOf("Name", "Root Table", "FK Column", "Description", "Type"), 0) {
        override fun isCellEditable(row: Int, column: Int) = false
    }
    private val table = JTable(tableModel)
    private var profiles: List<TransferProfile> = emptyList()

    init {
        border = BorderFactory.createEmptyBorder(12, 12, 12, 12)

        val header = JPanel(BorderLayout())
        val titleLbl = JLabel("Transfer Profiles")
        titleLbl.font = titleLbl.font.deriveFont(Font.BOLD, 15f)
        val descLbl = JLabel("Save reusable table + FK configurations. Built-in profiles cannot be deleted.")
        descLbl.foreground = Color(0x5A, 0x64, 0x78)
        val titleCol = JPanel(BorderLayout())
        titleCol.add(titleLbl, BorderLayout.NORTH)
        titleCol.add(descLbl, BorderLayout.SOUTH)
        header.add(titleCol, BorderLayout.WEST)

        val btnPanel = JPanel(FlowLayout(FlowLayout.RIGHT, 6, 0))
        val addBtn = JButton("+ New Profile")
        addBtn.background = Color(0x3D, 0x63, 0xDD)
        addBtn.foreground = Color.WHITE
        addBtn.isBorderPainted = false
        addBtn.isOpaque = true
        addBtn.addActionListener { addProfile() }
        val editBtn = JButton("Edit")
        editBtn.addActionListener { editSelected() }
        val deleteBtn = JButton("Delete")
        deleteBtn.background = Color(0xE5, 0x48, 0x4D)
        deleteBtn.foreground = Color.WHITE
        deleteBtn.isBorderPainted = false
        deleteBtn.isOpaque = true
        deleteBtn.addActionListener { deleteSelected() }
        btnPanel.add(editBtn)
        btnPanel.add(deleteBtn)
        btnPanel.add(addBtn)
        header.add(btnPanel, BorderLayout.EAST)
        header.border = BorderFactory.createEmptyBorder(0, 0, 8, 0)

        table.rowHeight = 36

        // grey out built-in rows
        val renderer = object : DefaultTableCellRenderer() {
            override fun getTableCellRendererComponent(
                tbl: JTable, value: Any?, selected: Boolean, focus: Boolean, row: Int, col: Int
            ): java.awt.Component {
                val c = super.getTableCellRendererComponent(tbl, value, selected, focus, row, col)
                if (row < profiles.size && profiles[row].isBuiltin && !selected) {
                    c.foreground = Color(0x8A, 0x93, 0xA6)
                } else if (!selected) {
                    c.foreground = tbl.foreground
                }
                return c
            }
        }
        for (i in 0..4) table.columnModel.getColumn(i).cellRenderer = renderer

        add(header, BorderLayout.NORTH)
        add(JBScrollPane(table), BorderLayout.CENTER)

        refresh()
    }

    private fun refresh() {
        profiles = store.loadAll()
        tableModel.rowCount = 0
        profiles.forEach { p ->
            tableModel.addRow(arrayOf(
                p.name,
                p.rootTable.ifEmpty { "—" },
                p.fkColumn.ifEmpty { "—" },
                p.description,
                if (p.isBuiltin) "Built-in" else "Custom"
            ))
        }
    }

    private fun selectedProfile(): TransferProfile? {
        val row = table.selectedRow
        return if (row >= 0 && row < profiles.size) profiles[row] else null
    }

    private fun addProfile() {
        val dlg = ProfileDialog(SwingUtilities.getWindowAncestor(this))
        dlg.isVisible = true
        if (dlg.result != null) {
            store.add(dlg.result!!)
            refresh()
            onChanged()
        }
    }

    private fun editSelected() {
        val p = selectedProfile() ?: return
        if (p.isBuiltin) {
            JOptionPane.showMessageDialog(this, "Built-in profiles cannot be edited.")
            return
        }
        val dlg = ProfileDialog(SwingUtilities.getWindowAncestor(this), existing = p)
        dlg.isVisible = true
        if (dlg.result != null) {
            store.update(dlg.result!!)
            refresh()
            onChanged()
        }
    }

    private fun deleteSelected() {
        val p = selectedProfile() ?: return
        if (p.isBuiltin) {
            JOptionPane.showMessageDialog(this, "Built-in profiles cannot be deleted.")
            return
        }
        val confirm = JOptionPane.showConfirmDialog(this, "Delete profile '${p.name}'?", "Delete", JOptionPane.YES_NO_OPTION)
        if (confirm == JOptionPane.YES_OPTION) {
            store.remove(p.id)
            refresh()
            onChanged()
        }
    }
}


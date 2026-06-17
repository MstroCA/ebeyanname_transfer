package io.recordrelay.ui.panels

import com.intellij.ui.components.JBScrollPane
import io.recordrelay.core.Connection
import io.recordrelay.core.TransferEngine
import io.recordrelay.store.ConnectionStore
import io.recordrelay.ui.dialogs.ConnectionDialog
import kotlinx.coroutines.*
import kotlinx.coroutines.swing.Swing
import java.awt.*
import javax.swing.*
import javax.swing.table.DefaultTableModel

class ConnectionsPanel(
    private val store: ConnectionStore,
    private val onChanged: () -> Unit
) : JPanel(BorderLayout()) {

    private val tableModel = object : DefaultTableModel(arrayOf("Env", "Type", "Name", "Host:Port/DB", "User"), 0) {
        override fun isCellEditable(row: Int, column: Int) = false
    }
    private val table = JTable(tableModel)
    private var connections: List<Connection> = emptyList()
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    init {
        border = BorderFactory.createEmptyBorder(12, 12, 12, 12)

        val header = JPanel(BorderLayout())
        val titleLbl = JLabel("Database Connections")
        titleLbl.font = titleLbl.font.deriveFont(Font.BOLD, 15f)
        header.add(titleLbl, BorderLayout.WEST)

        val btnPanel = JPanel(FlowLayout(FlowLayout.RIGHT, 6, 0))
        val addBtn = JButton("+ New Connection")
        addBtn.background = Color(0x3D, 0x63, 0xDD)
        addBtn.foreground = Color.WHITE
        addBtn.isBorderPainted = false
        addBtn.isOpaque = true
        addBtn.addActionListener { addConnection() }

        val editBtn = JButton("Edit")
        editBtn.addActionListener { editSelected() }

        val deleteBtn = JButton("Delete")
        deleteBtn.background = Color(0xE5, 0x48, 0x4D)
        deleteBtn.foreground = Color.WHITE
        deleteBtn.isBorderPainted = false
        deleteBtn.isOpaque = true
        deleteBtn.addActionListener { deleteSelected() }

        val testBtn = JButton("Test")
        testBtn.addActionListener { testSelected() }

        btnPanel.add(testBtn)
        btnPanel.add(editBtn)
        btnPanel.add(deleteBtn)
        btnPanel.add(addBtn)
        header.add(btnPanel, BorderLayout.EAST)
        header.border = BorderFactory.createEmptyBorder(0, 0, 8, 0)

        table.rowHeight = 36
        table.columnModel.getColumn(0).preferredWidth = 100
        table.columnModel.getColumn(1).preferredWidth = 80
        table.columnModel.getColumn(2).preferredWidth = 160
        table.columnModel.getColumn(3).preferredWidth = 200
        table.columnModel.getColumn(4).preferredWidth = 100

        add(header, BorderLayout.NORTH)
        add(JBScrollPane(table), BorderLayout.CENTER)

        refresh()
    }

    private fun refresh() {
        connections = store.loadAll()
        tableModel.rowCount = 0
        connections.forEach { c ->
            tableModel.addRow(arrayOf(
                c.environment.label,
                c.dbType.displayName,
                c.name,
                c.maskedSummary(),
                c.user
            ))
        }
    }

    private fun selectedConnection(): Connection? {
        val row = table.selectedRow
        return if (row >= 0 && row < connections.size) connections[row] else null
    }

    private fun addConnection() {
        val dlg = ConnectionDialog(SwingUtilities.getWindowAncestor(this))
        dlg.isVisible = true
        if (dlg.result != null) {
            store.add(dlg.result!!)
            refresh()
            onChanged()
        }
    }

    private fun editSelected() {
        val conn = selectedConnection() ?: run {
            JOptionPane.showMessageDialog(this, "Please select a connection to edit.")
            return
        }
        val dlg = ConnectionDialog(SwingUtilities.getWindowAncestor(this), existing = conn)
        dlg.isVisible = true
        if (dlg.result != null) {
            store.update(dlg.result!!)
            refresh()
            onChanged()
        }
    }

    private fun deleteSelected() {
        val conn = selectedConnection() ?: return
        val confirm = JOptionPane.showConfirmDialog(
            this, "Delete connection '${conn.name}'?", "Delete", JOptionPane.YES_NO_OPTION
        )
        if (confirm == JOptionPane.YES_OPTION) {
            store.remove(conn.id)
            refresh()
            onChanged()
        }
    }

    private fun testSelected() {
        val conn = selectedConnection() ?: run {
            JOptionPane.showMessageDialog(this, "Please select a connection to test.")
            return
        }
        val statusLbl = JOptionPane.getRootFrame()
        scope.launch {
            val (ok, msg) = TransferEngine.testConnection(conn)
            withContext(Dispatchers.Swing) {
                val icon = if (ok) JOptionPane.INFORMATION_MESSAGE else JOptionPane.ERROR_MESSAGE
                JOptionPane.showMessageDialog(this@ConnectionsPanel, msg, "Connection Test", icon)
            }
        }
    }
}


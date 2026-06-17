package io.recordrelay.ui.dialogs

import com.intellij.ui.components.JBPasswordField
import com.intellij.ui.components.JBTextField
import io.recordrelay.core.Connection
import io.recordrelay.core.DbType
import io.recordrelay.core.Environment
import io.recordrelay.core.TransferEngine
import kotlinx.coroutines.*
import kotlinx.coroutines.swing.Swing
import java.awt.*
import java.util.UUID
import javax.swing.*

class ConnectionDialog(
    owner: Window?,
    private val existing: Connection? = null
) : JDialog(owner, if (existing == null) "New Connection" else "Edit Connection", ModalityType.APPLICATION_MODAL) {

    var result: Connection? = null

    private val nameField = JBTextField()
    private val envCombo = JComboBox(Environment.DEFAULTS.map { "${it.label} (${it.name})" }.toTypedArray())
    private val dbTypeCombo = JComboBox(DbType.values())
    private val hostField = JBTextField()
    private val portSpinner = JSpinner(SpinnerNumberModel(5432, 1, 65535, 1))
    private val dbNameField = JBTextField()
    private val userField = JBTextField()
    private val passwordField = JBPasswordField()
    private val noteField = JBTextField()
    private val testStatusLbl = JLabel(" ")
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    init {
        defaultCloseOperation = DISPOSE_ON_CLOSE
        setSize(500, 480)
        setLocationRelativeTo(owner)
        isResizable = false

        dbTypeCombo.renderer = ListCellRenderer<DbType> { _, value, _, _, _ ->
            JLabel(value?.displayName ?: "")
        }
        dbTypeCombo.addActionListener {
            val dt = dbTypeCombo.selectedItem as? DbType ?: DbType.POSTGRESQL
            portSpinner.value = dt.defaultPort
        }

        val panel = JPanel(GridBagLayout())
        panel.border = BorderFactory.createEmptyBorder(16, 16, 16, 16)
        val gbc = GridBagConstraints().apply {
            insets = Insets(5, 6, 5, 6)
            fill = GridBagConstraints.HORIZONTAL
        }

        fun addRow(label: String, comp: JComponent, row: Int) {
            gbc.gridx = 0; gbc.gridy = row; gbc.weightx = 0.0
            panel.add(JLabel("$label:"), gbc)
            gbc.gridx = 1; gbc.weightx = 1.0
            panel.add(comp, gbc)
        }

        addRow("Name *", nameField, 0)
        addRow("Environment", envCombo, 1)
        addRow("DB Type", dbTypeCombo, 2)
        addRow("Host *", hostField, 3)
        addRow("Port", portSpinner, 4)
        addRow("Database *", dbNameField, 5)
        addRow("User *", userField, 6)
        addRow("Password", passwordField, 7)
        addRow("Note", noteField, 8)

        gbc.gridx = 0; gbc.gridy = 9; gbc.gridwidth = 2; gbc.weightx = 1.0
        panel.add(testStatusLbl, gbc)

        val btnPanel = JPanel(FlowLayout(FlowLayout.RIGHT, 6, 0))
        val testBtn = JButton("Test Connection")
        testBtn.addActionListener { testConnection(testBtn) }
        val cancelBtn = JButton("Cancel")
        cancelBtn.addActionListener { dispose() }
        val saveBtn = JButton("Save")
        saveBtn.background = Color(0x3D, 0x63, 0xDD)
        saveBtn.foreground = Color.WHITE
        saveBtn.isBorderPainted = false
        saveBtn.isOpaque = true
        saveBtn.addActionListener { doSave() }
        btnPanel.add(testBtn)
        btnPanel.add(cancelBtn)
        btnPanel.add(saveBtn)

        gbc.gridy = 10; gbc.insets = Insets(10, 6, 0, 6)
        panel.add(btnPanel, gbc)

        contentPane.add(panel)

        existing?.let { fill(it) }
    }

    private fun fill(c: Connection) {
        nameField.text = c.name
        val envIdx = Environment.DEFAULTS.indexOfFirst { it.name.equals(c.environmentName, ignoreCase = true) }
        if (envIdx >= 0) envCombo.selectedIndex = envIdx
        dbTypeCombo.selectedItem = c.dbType
        hostField.text = c.host
        portSpinner.value = c.port
        dbNameField.text = c.dbname
        userField.text = c.user
        passwordField.text = c.password
        noteField.text = c.note
    }

    private fun collect(): Connection? {
        val name = nameField.text.trim()
        val host = hostField.text.trim()
        val db = dbNameField.text.trim()
        val user = userField.text.trim()
        if (name.isEmpty() || host.isEmpty() || db.isEmpty() || user.isEmpty()) {
            JOptionPane.showMessageDialog(this, "Name, Host, Database and User are required.")
            return null
        }
        val envIdx = envCombo.selectedIndex
        val envName = if (envIdx >= 0) Environment.DEFAULTS[envIdx].name else "LOCAL"
        val dbType = dbTypeCombo.selectedItem as? DbType ?: DbType.POSTGRESQL
        return Connection(
            id = existing?.id ?: UUID.randomUUID().toString(),
            name = name,
            environmentName = envName,
            host = host,
            port = portSpinner.value as Int,
            dbname = db,
            user = user,
            password = String(passwordField.password),
            dbType = dbType,
            note = noteField.text.trim()
        )
    }

    private fun testConnection(btn: JButton) {
        val conn = collect() ?: return
        btn.isEnabled = false
        testStatusLbl.text = "Connecting..."
        testStatusLbl.foreground = Color(0x5A, 0x64, 0x78)
        scope.launch {
            val (ok, msg) = TransferEngine.testConnection(conn)
            withContext(Dispatchers.Swing) {
                btn.isEnabled = true
                testStatusLbl.text = if (ok) "✓ $msg" else "✕ $msg"
                testStatusLbl.foreground = if (ok) Color(0x30, 0xA4, 0x6C) else Color(0xE5, 0x48, 0x4D)
            }
        }
    }

    private fun doSave() {
        val conn = collect() ?: return
        result = conn
        dispose()
    }
}

package io.recordrelay.ui.panels

import com.intellij.ui.components.JBLabel
import com.intellij.ui.components.JBScrollPane
import com.intellij.ui.components.JBTextField
import io.recordrelay.core.*
import io.recordrelay.store.ConnectionStore
import io.recordrelay.store.ProfileStore
import kotlinx.coroutines.*
import kotlinx.coroutines.swing.Swing
import java.awt.*
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import javax.swing.*
import javax.swing.text.SimpleAttributeSet
import javax.swing.text.StyleConstants

class TransferPanel(
    private val connectionStore: ConnectionStore,
    private val profileStore: ProfileStore
) : JPanel(BorderLayout()) {

    private val profileCombo = JComboBox<String>()
    private val srcCombo = JComboBox<String>()
    private val tgtCombo = JComboBox<String>()
    private val dirBanner = JLabel("Select source and target connections.")
    private val rootTableField = JBTextField()
    private val pkColumnField = JBTextField("id")
    private val fkColumnField = JBTextField()
    private val recordIdField = JBTextField()
    private val createdByField = JBTextField()
    private val fieldOverridesField = JBTextField()
    private val skipDeleteCheck = JCheckBox("Keep existing data in target")
    private val dryRunCheck = JCheckBox("Dry run — preview only, no writes")
    private val progressBar = JProgressBar(0, 100)
    private val startBtn = JButton("Start Transfer")
    private val cancelBtn = JButton("Cancel")
    private val logPane = JTextPane()

    private var connections: List<io.recordrelay.core.Connection> = emptyList()
    private var profiles: List<io.recordrelay.core.TransferProfile> = emptyList()
    private var currentJob: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private val ts get() = LocalDateTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss"))

    init {
        border = BorderFactory.createEmptyBorder(16, 16, 16, 16)
        add(buildTopPanel(), BorderLayout.NORTH)
        add(buildLogPanel(), BorderLayout.CENTER)
        add(buildActionPanel(), BorderLayout.SOUTH)

        startBtn.addActionListener { startTransfer() }
        cancelBtn.addActionListener { currentJob?.cancel(); appendLog("warn", "Cancellation requested...") }
        cancelBtn.isEnabled = false

        srcCombo.addActionListener { validateDirection() }
        tgtCombo.addActionListener { validateDirection() }
        profileCombo.addActionListener { onProfileSelected() }
        dryRunCheck.addActionListener { updateStartButton() }

        reloadConnections()
        reloadProfiles()
    }

    private fun buildTopPanel(): JPanel {
        val panel = JPanel()
        panel.layout = BoxLayout(panel, BoxLayout.Y_AXIS)
        panel.border = BorderFactory.createEmptyBorder(0, 0, 8, 0)

        // Profile row
        val profileRow = JPanel(FlowLayout(FlowLayout.LEFT, 4, 4))
        profileRow.add(JBLabel("Profile:"))
        profileCombo.preferredSize = Dimension(280, 28)
        profileRow.add(profileCombo)
        val saveProfileBtn = JButton("Save as Profile")
        saveProfileBtn.addActionListener { saveAsProfile() }
        profileRow.add(saveProfileBtn)
        panel.add(profileRow)

        // Source → Target row
        val endpointsRow = JPanel(GridLayout(1, 3, 8, 0))
        endpointsRow.add(buildComboCard("SOURCE", srcCombo))
        val arrowLbl = JBLabel("→", SwingConstants.CENTER)
        arrowLbl.font = Font(arrowLbl.font.name, Font.BOLD, 22)
        endpointsRow.add(arrowLbl)
        endpointsRow.add(buildComboCard("TARGET", tgtCombo))
        panel.add(endpointsRow)

        // Direction banner
        dirBanner.horizontalAlignment = SwingConstants.CENTER
        dirBanner.border = BorderFactory.createEmptyBorder(6, 0, 6, 0)
        dirBanner.font = dirBanner.font.deriveFont(Font.BOLD)
        panel.add(dirBanner)

        // Parameters grid
        val paramPanel = JPanel(GridBagLayout())
        paramPanel.border = BorderFactory.createTitledBorder("Transfer Parameters")
        val gbc = GridBagConstraints().apply {
            insets = Insets(4, 6, 4, 6)
            fill = GridBagConstraints.HORIZONTAL
        }

        fun addRow(label: String, field: JComponent, row: Int, col: Int = 0) {
            gbc.gridx = col * 2; gbc.gridy = row; gbc.weightx = 0.0
            paramPanel.add(JBLabel("$label:"), gbc)
            gbc.gridx = col * 2 + 1; gbc.weightx = 1.0
            paramPanel.add(field, gbc)
        }

        rootTableField.emptyText.text = "e.g. beyanname, order, invoice"
        fkColumnField.emptyText.text = "e.g. order_id, beyanname_id"
        recordIdField.emptyText.text = "Record ID value (e.g. 42)"
        createdByField.emptyText.text = "Optional — override created_by"
        fieldOverridesField.emptyText.text = """Optional JSON {"col": "value"}"""

        addRow("Root Table *", rootTableField, 0, 0)
        addRow("PK Column", pkColumnField, 0, 1)
        addRow("FK Column *", fkColumnField, 1, 0)
        addRow("Record ID *", recordIdField, 1, 1)
        addRow("created_by", createdByField, 2, 0)
        addRow("Field Overrides", fieldOverridesField, 2, 1)

        gbc.gridx = 0; gbc.gridy = 3; gbc.weightx = 0.5; gbc.gridwidth = 2
        paramPanel.add(skipDeleteCheck, gbc)
        gbc.gridx = 2; gbc.gridwidth = 2
        paramPanel.add(dryRunCheck, gbc)
        gbc.gridwidth = 1

        panel.add(paramPanel)
        return panel
    }

    private fun buildComboCard(title: String, combo: JComboBox<String>): JPanel {
        val p = JPanel(BorderLayout(4, 4))
        p.border = BorderFactory.createTitledBorder(title)
        p.add(combo, BorderLayout.CENTER)
        return p
    }

    private fun buildLogPanel(): JScrollPane {
        logPane.isEditable = false
        logPane.background = Color(0x0E, 0x17, 0x26)
        logPane.foreground = Color(0xD7, 0xE0, 0xF4)
        logPane.font = Font("Monospaced", Font.PLAIN, 12)
        return JBScrollPane(logPane)
    }

    private fun buildActionPanel(): JPanel {
        progressBar.isStringPainted = true
        progressBar.string = "Ready"

        startBtn.background = Color(0x3D, 0x63, 0xDD)
        startBtn.foreground = Color.WHITE
        startBtn.isBorderPainted = false
        startBtn.isOpaque = true

        val panel = JPanel(BorderLayout(8, 0))
        panel.border = BorderFactory.createEmptyBorder(8, 0, 0, 0)
        panel.add(progressBar, BorderLayout.CENTER)
        val btnPanel = JPanel(FlowLayout(FlowLayout.RIGHT, 6, 0))
        btnPanel.add(cancelBtn)
        btnPanel.add(startBtn)
        panel.add(btnPanel, BorderLayout.EAST)
        return panel
    }

    fun reloadConnections() {
        connections = connectionStore.loadAll()
        val names = connections.map { "${it.name} · ${it.environment.label}" }
        val srcSel = srcCombo.selectedIndex
        val tgtSel = tgtCombo.selectedIndex
        srcCombo.removeAllItems()
        tgtCombo.removeAllItems()
        names.forEach { n ->
            srcCombo.addItem(n)
            tgtCombo.addItem(n)
        }
        if (srcSel >= 0 && srcSel < names.size) srcCombo.selectedIndex = srcSel
        if (tgtSel >= 0 && tgtSel < names.size) tgtCombo.selectedIndex = tgtSel
        validateDirection()
    }

    fun reloadProfiles() {
        profiles = profileStore.loadAll()
        val sel = profileCombo.selectedIndex
        profileCombo.removeAllItems()
        profiles.forEach { profileCombo.addItem(it.name) }
        if (sel >= 0 && sel < profiles.size) profileCombo.selectedIndex = sel
    }

    private fun onProfileSelected() {
        val idx = profileCombo.selectedIndex
        if (idx < 0 || idx >= profiles.size) return
        val p = profiles[idx]
        rootTableField.text = p.rootTable
        pkColumnField.text = p.pkColumn
        fkColumnField.text = p.fkColumn
    }

    private fun validateDirection() {
        val src = selectedSource() ?: run {
            dirBanner.text = "Select source and target connections."
            dirBanner.foreground = Color(0x5A, 0x64, 0x78)
            return
        }
        val tgt = selectedTarget() ?: run {
            dirBanner.text = "Select source and target connections."
            dirBanner.foreground = Color(0x5A, 0x64, 0x78)
            return
        }
        val chk = checkDirection(src.environment, tgt.environment)
        if (chk.allowed) {
            dirBanner.text = "✓ ${chk.reason}"
            dirBanner.foreground = Color(0x1B, 0x6E, 0x45)
        } else {
            dirBanner.text = "⛔ ${chk.reason}"
            dirBanner.foreground = Color(0xA0, 0x1F, 0x23)
        }
        updateStartButton()
    }

    private fun updateStartButton() {
        val src = selectedSource()
        val tgt = selectedTarget()
        val dirOk = if (src != null && tgt != null) checkDirection(src.environment, tgt.environment).allowed else false
        startBtn.isEnabled = dirOk && currentJob?.isActive != true
        if (dryRunCheck.isSelected) {
            startBtn.text = "Preview (Dry Run)"
            startBtn.background = Color(0xF5, 0xA5, 0x24)
        } else {
            startBtn.text = "Start Transfer"
            startBtn.background = Color(0x3D, 0x63, 0xDD)
        }
    }

    private fun selectedSource(): io.recordrelay.core.Connection? {
        val idx = srcCombo.selectedIndex
        return if (idx >= 0 && idx < connections.size) connections[idx] else null
    }

    private fun selectedTarget(): io.recordrelay.core.Connection? {
        val idx = tgtCombo.selectedIndex
        return if (idx >= 0 && idx < connections.size) connections[idx] else null
    }

    private fun saveAsProfile() {
        val rt = rootTableField.text.trim()
        val fk = fkColumnField.text.trim()
        if (rt.isEmpty() || fk.isEmpty()) {
            JOptionPane.showMessageDialog(this, "Root Table and FK Column are required to save a profile.")
            return
        }
        val name = JOptionPane.showInputDialog(this, "Profile name:") ?: return
        if (name.isBlank()) return
        val profile = io.recordrelay.core.TransferProfile(
            name = name.trim(), rootTable = rt,
            pkColumn = pkColumnField.text.trim().ifEmpty { "id" }, fkColumn = fk
        )
        profileStore.add(profile)
        reloadProfiles()
    }

    private fun startTransfer() {
        val src = selectedSource() ?: return
        val tgt = selectedTarget() ?: return
        val rt = rootTableField.text.trim()
        val fk = fkColumnField.text.trim()
        val pk = pkColumnField.text.trim().ifEmpty { "id" }
        val rid = recordIdField.text.trim()
        if (rt.isEmpty() || fk.isEmpty() || rid.isEmpty()) {
            JOptionPane.showMessageDialog(this, "Root Table, FK Column, and Record ID are required.")
            return
        }

        val overridesRaw = fieldOverridesField.text.trim()
        val overrides = mutableMapOf<String, String>()
        if (overridesRaw.isNotEmpty()) {
            try {
                val gson = com.google.gson.Gson()
                val type = object : com.google.gson.reflect.TypeToken<Map<String, String>>() {}.type
                overrides.putAll(gson.fromJson(overridesRaw, type))
            } catch (e: Exception) {
                JOptionPane.showMessageDialog(this, "Field Overrides must be a valid JSON object:\n${e.message}")
                return
            }
        }

        val isDry = dryRunCheck.isSelected
        val confirm = JOptionPane.showConfirmDialog(
            this,
            "${src.name} (${src.environment.label})\n→ ${tgt.name} (${tgt.environment.label})\n\n" +
            "Table: $rt | FK: $fk | Record ID: $rid\n" +
            (if (isDry) "⚡ DRY RUN — no data will be written" else "Data will be written to target") +
            "\n\nContinue?",
            if (isDry) "Confirm Preview" else "Confirm Transfer",
            JOptionPane.YES_NO_OPTION
        )
        if (confirm != JOptionPane.YES_OPTION) return

        logPane.text = ""
        progressBar.value = 0
        progressBar.string = "Starting..."
        startBtn.isEnabled = false
        cancelBtn.isEnabled = true

        val engine = TransferEngine(
            source = src, target = tgt,
            recordId = rid, rootTable = rt, pkColumn = pk, fkColumn = fk,
            fieldOverrides = overrides,
            skipDelete = skipDeleteCheck.isSelected,
            dryRun = isDry,
            onProgress = { level, msg -> SwingUtilities.invokeLater { appendLog(level, msg) } },
            onPercent = { cur, total ->
                SwingUtilities.invokeLater {
                    if (total > 0) {
                        val pct = (cur * 100 / total)
                        progressBar.value = pct
                        progressBar.string = "%d%%  (%d/%d tables)".format(pct, cur, total)
                    }
                }
            }
        )

        currentJob = scope.launch {
            try {
                val summary = engine.run()
                withContext(Dispatchers.Swing) {
                    cancelBtn.isEnabled = false
                    if (summary.fatalError.isNotEmpty()) {
                        progressBar.string = "Error"
                        appendLog("error", "Transfer failed: ${summary.fatalError}")
                    } else {
                        progressBar.value = 100
                        val tag = if (isDry) "[DRY RUN] " else ""
                        val status = if (summary.ok) "completed" else "completed with warnings"
                        progressBar.string = "100% — $tag$status"
                        appendLog("ok",
                            "${tag}Done: ${summary.totalRows} rows, " +
                            "${summary.skippedTables} tables skipped, ${summary.totalErrors} errors.")
                    }
                    updateStartButton()
                }
            } catch (e: DirectionError) {
                withContext(Dispatchers.Swing) {
                    cancelBtn.isEnabled = false
                    appendLog("error", "BLOCKED: ${e.message}")
                    JOptionPane.showMessageDialog(this@TransferPanel, "Direction blocked:\n${e.message}", "Blocked", JOptionPane.ERROR_MESSAGE)
                    updateStartButton()
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Swing) {
                    cancelBtn.isEnabled = false
                    appendLog("error", "Error: ${e.message}")
                    updateStartButton()
                }
            }
        }
    }

    private fun appendLog(level: String, msg: String) {
        val color = when (level) {
            "ok"    -> Color(0x5D, 0xD3, 0x9E)
            "warn"  -> Color(0xF5, 0xC2, 0x6B)
            "error" -> Color(0xF0, 0x8A, 0x8E)
            "step"  -> Color(0x8F, 0xB8, 0xFF)
            else    -> Color(0x9F, 0xB0, 0xD0)
        }
        val prefix = when (level) {
            "ok" -> "✓"; "warn" -> "⚠"; "error" -> "✕"; "step" -> "▸"; else -> "·"
        }
        val doc = logPane.styledDocument

        val tsAttr = SimpleAttributeSet()
        StyleConstants.setForeground(tsAttr, Color(0x5A, 0x64, 0x78))
        doc.insertString(doc.length, "$ts ", tsAttr)

        val msgAttr = SimpleAttributeSet()
        StyleConstants.setForeground(msgAttr, color)
        doc.insertString(doc.length, "$prefix $msg\n", msgAttr)

        logPane.caretPosition = doc.length
    }
}

package io.recordrelay.ui.dialogs

import com.intellij.ui.components.JBTextField
import io.recordrelay.core.TransferProfile
import java.awt.*
import java.util.UUID
import javax.swing.*

class ProfileDialog(
    owner: Window?,
    private val existing: TransferProfile? = null
) : JDialog(owner, if (existing == null) "New Profile" else "Edit Profile", ModalityType.APPLICATION_MODAL) {

    var result: TransferProfile? = null

    private val nameField = JBTextField()
    private val rootTableField = JBTextField()
    private val pkColumnField = JBTextField("id")
    private val fkColumnField = JBTextField()
    private val descriptionField = JBTextField()

    init {
        defaultCloseOperation = DISPOSE_ON_CLOSE
        setSize(460, 320)
        setLocationRelativeTo(owner)
        isResizable = false

        val panel = JPanel(GridBagLayout())
        panel.border = BorderFactory.createEmptyBorder(16, 16, 16, 16)
        val gbc = GridBagConstraints().apply {
            insets = Insets(5, 6, 5, 6)
            fill = GridBagConstraints.HORIZONTAL
        }

        fun addRow(label: String, comp: JComponent, row: Int, placeholder: String = "") {
            if (comp is JBTextField && placeholder.isNotEmpty()) comp.emptyText.text = placeholder
            gbc.gridx = 0; gbc.gridy = row; gbc.weightx = 0.0
            panel.add(JLabel("$label:"), gbc)
            gbc.gridx = 1; gbc.weightx = 1.0
            panel.add(comp, gbc)
        }

        addRow("Name *", nameField, 0, "e.g. Order Records")
        addRow("Root Table *", rootTableField, 1, "e.g. order, beyanname, invoice")
        addRow("PK Column", pkColumnField, 2, "Primary key column (usually id)")
        addRow("FK Column *", fkColumnField, 3, "e.g. order_id, beyanname_id")
        addRow("Description", descriptionField, 4, "Optional description")

        val btnPanel = JPanel(FlowLayout(FlowLayout.RIGHT, 6, 0))
        val cancelBtn = JButton("Cancel")
        cancelBtn.addActionListener { dispose() }
        val saveBtn = JButton("Save")
        saveBtn.background = Color(0x3D, 0x63, 0xDD)
        saveBtn.foreground = Color.WHITE
        saveBtn.isBorderPainted = false
        saveBtn.isOpaque = true
        saveBtn.addActionListener { doSave() }
        btnPanel.add(cancelBtn)
        btnPanel.add(saveBtn)

        gbc.gridx = 0; gbc.gridy = 5; gbc.gridwidth = 2; gbc.insets = Insets(12, 6, 0, 6)
        panel.add(btnPanel, gbc)

        contentPane.add(panel)
        existing?.let { fill(it) }
    }

    private fun fill(p: TransferProfile) {
        nameField.text = p.name
        rootTableField.text = p.rootTable
        pkColumnField.text = p.pkColumn
        fkColumnField.text = p.fkColumn
        descriptionField.text = p.description
    }

    private fun doSave() {
        val name = nameField.text.trim()
        val rt = rootTableField.text.trim()
        val fk = fkColumnField.text.trim()
        if (name.isEmpty() || rt.isEmpty() || fk.isEmpty()) {
            JOptionPane.showMessageDialog(this, "Name, Root Table and FK Column are required.")
            return
        }
        result = TransferProfile(
            id = existing?.id ?: UUID.randomUUID().toString(),
            name = name,
            rootTable = rt,
            pkColumn = pkColumnField.text.trim().ifEmpty { "id" },
            fkColumn = fk,
            description = descriptionField.text.trim(),
            isBuiltin = false
        )
        dispose()
    }
}

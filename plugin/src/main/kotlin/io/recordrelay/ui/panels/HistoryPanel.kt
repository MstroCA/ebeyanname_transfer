package io.recordrelay.ui.panels

import com.google.gson.Gson
import com.google.gson.JsonObject
import com.intellij.ui.components.JBScrollPane
import java.awt.*
import java.io.File
import java.nio.file.Paths
import javax.swing.*
import javax.swing.table.DefaultTableCellRenderer
import javax.swing.table.DefaultTableModel

data class HistoryRecord(
    val timestamp: String,
    val recordId: String,
    val rootTable: String,
    val fkColumn: String,
    val sourceName: String,
    val sourceEnv: String,
    val targetName: String,
    val targetEnv: String,
    val status: String,
    val totalRows: Int,
    val totalErrors: Int,
    val skippedTables: Int,
    val durationSec: Double,
    val dryRun: Boolean,
    val logFile: String,
    val message: String
)

class HistoryPanel : JPanel(BorderLayout()) {

    private val historyFile = File(
        Paths.get(System.getProperty("user.home"), ".recordrelay", "history.jsonl").toString()
    )
    private val tableModel = DefaultTableModel(
        arrayOf("Time", "Source → Target", "Table", "Record ID", "Status", "Rows", "Duration"), 0
    )
    private val table = JTable(tableModel)
    private var records: List<HistoryRecord> = emptyList()

    private val STATUS_COLORS = mapOf(
        "success"   to (Color(0xE6, 0xF6, 0xEC) to Color(0x1B, 0x6E, 0x45)),
        "warning"   to (Color(0xFE, 0xF3, 0xDD) to Color(0xA8, 0x65, 0x0A)),
        "error"     to (Color(0xFE, 0xEB, 0xEC) to Color(0xA0, 0x1F, 0x23)),
        "blocked"   to (Color(0xFE, 0xEB, 0xEC) to Color(0xA0, 0x1F, 0x23)),
        "cancelled" to (Color(0xF4, 0xF6, 0xFB) to Color(0x5A, 0x64, 0x78))
    )

    init {
        border = BorderFactory.createEmptyBorder(12, 12, 12, 12)

        val header = JPanel(BorderLayout())
        val titleLbl = JLabel("Transfer History")
        titleLbl.font = titleLbl.font.deriveFont(Font.BOLD, 15f)
        val refreshBtn = JButton("Refresh")
        refreshBtn.addActionListener { refresh() }
        header.add(titleLbl, BorderLayout.WEST)
        header.add(refreshBtn, BorderLayout.EAST)
        header.border = BorderFactory.createEmptyBorder(0, 0, 8, 0)

        table.rowHeight = 36
        table.columnModel.getColumn(0).preferredWidth = 120
        table.columnModel.getColumn(1).preferredWidth = 260
        table.columnModel.getColumn(2).preferredWidth = 120
        table.columnModel.getColumn(3).preferredWidth = 80
        table.columnModel.getColumn(4).preferredWidth = 90
        table.columnModel.getColumn(5).preferredWidth = 50
        table.columnModel.getColumn(6).preferredWidth = 70

        // Status column renderer
        table.columnModel.getColumn(4).cellRenderer = object : DefaultTableCellRenderer() {
            override fun getTableCellRendererComponent(
                tbl: JTable, value: Any?, selected: Boolean, focus: Boolean, row: Int, col: Int
            ): java.awt.Component {
                val lbl = super.getTableCellRendererComponent(tbl, value, selected, focus, row, col) as JLabel
                if (!selected && row < records.size) {
                    val status = records[row].status
                    val (bg, fg) = STATUS_COLORS[status] ?: (Color.LIGHT_GRAY to Color.BLACK)
                    lbl.background = bg
                    lbl.foreground = fg
                    lbl.isOpaque = true
                    lbl.horizontalAlignment = SwingConstants.CENTER
                    val label = when (status) {
                        "success" -> "Success"; "warning" -> "Warning"; "error" -> "Error"
                        "blocked" -> "Blocked"; "cancelled" -> "Cancelled"; else -> status
                    }
                    lbl.text = label
                }
                return lbl
            }
        }

        add(header, BorderLayout.NORTH)
        add(JBScrollPane(table), BorderLayout.CENTER)

        refresh()
    }

    fun refresh() {
        records = loadHistory()
        tableModel.rowCount = 0
        records.forEach { r ->
            val dry = if (r.dryRun) " [DRY]" else ""
            tableModel.addRow(arrayOf(
                r.timestamp.take(19).replace("T", " "),
                "${r.sourceName} (${r.sourceEnv})  →  ${r.targetName} (${r.targetEnv})",
                r.rootTable + dry,
                r.recordId,
                r.status,
                r.totalRows,
                "${r.durationSec}s"
            ))
        }
    }

    private fun loadHistory(limit: Int = 200): List<HistoryRecord> {
        if (!historyFile.exists()) return emptyList()
        val gson = Gson()
        val records = mutableListOf<HistoryRecord>()
        historyFile.bufferedReader().forEachLine { line ->
            if (line.isBlank()) return@forEachLine
            try {
                val obj = gson.fromJson(line, JsonObject::class.java)
                // handle backward compat: beyanname_id → record_id
                val recordId = when {
                    obj.has("record_id") -> obj.get("record_id").asString
                    obj.has("beyanname_id") -> obj.get("beyanname_id").asString
                    else -> "?"
                }
                records.add(HistoryRecord(
                    timestamp = obj.get("timestamp")?.asString ?: "",
                    recordId = recordId,
                    rootTable = obj.get("root_table")?.asString ?: "beyanname",
                    fkColumn = obj.get("fk_column")?.asString ?: "",
                    sourceName = obj.get("source_name")?.asString ?: "",
                    sourceEnv = obj.get("source_env")?.asString ?: "",
                    targetName = obj.get("target_name")?.asString ?: "",
                    targetEnv = obj.get("target_env")?.asString ?: "",
                    status = obj.get("status")?.asString ?: "",
                    totalRows = obj.get("total_rows")?.asInt ?: 0,
                    totalErrors = obj.get("total_errors")?.asInt ?: 0,
                    skippedTables = obj.get("skipped_tables")?.asInt ?: 0,
                    durationSec = obj.get("duration_sec")?.asDouble ?: 0.0,
                    dryRun = obj.get("dry_run")?.asBoolean ?: false,
                    logFile = obj.get("log_file")?.asString ?: "",
                    message = obj.get("message")?.asString ?: ""
                ))
            } catch (_: Exception) {}
        }
        records.reverse()
        return records.take(limit)
    }
}

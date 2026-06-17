package io.recordrelay.core

import java.sql.Connection as JdbcConnection
import java.sql.DriverManager
import java.sql.ResultSet

data class TableResult(
    val tableName: String,
    val schemaName: String,
    var rowsTransferred: Int = 0,
    var totalRows: Int = 0,
    var skipped: Boolean = false,
    var skipReason: String = "",
    val errors: MutableList<String> = mutableListOf()
)

data class TransferSummary(
    val startedAt: Long,
    var finishedAt: Long = 0L,
    val results: MutableList<TableResult> = mutableListOf(),
    var totalRows: Int = 0,
    var totalErrors: Int = 0,
    var skippedTables: Int = 0,
    var fatalError: String = "",
    val dryRun: Boolean = false
) {
    val ok: Boolean get() = fatalError.isEmpty() && totalErrors == 0
    val durationMs: Long get() = finishedAt - startedAt
}

class DirectionError(message: String) : Exception(message)
class TransferError(message: String) : Exception(message)

class TransferEngine(
    private val source: Connection,
    private val target: Connection,
    private val recordId: String,
    private val rootTable: String,
    private val pkColumn: String,
    private val fkColumn: String,
    private val fieldOverrides: Map<String, String> = emptyMap(),
    private val skipDelete: Boolean = false,
    private val dryRun: Boolean = false,
    private val onProgress: (level: String, message: String) -> Unit = { _, _ -> },
    private val onPercent: (current: Int, total: Int) -> Unit = { _, _ -> },
    private val cancelCheck: () -> Boolean = { false }
) {

    private val dryPrefix = if (dryRun) "[DRY RUN] " else ""

    private fun log(level: String, msg: String) = onProgress(level, "$dryPrefix$msg")

    private fun quote(identifier: String, mysql: Boolean): String =
        if (mysql) "`$identifier`" else "\"$identifier\""

    private fun openConnection(conn: Connection): JdbcConnection {
        Class.forName(conn.driverClass())
        return DriverManager.getConnection(conn.jdbcUrl(), conn.user, conn.password)
    }

    private fun isMysql(conn: Connection) = conn.dbType == DbType.MYSQL

    private fun tablesWithColumn(jdbc: JdbcConnection, colName: String, mysql: Boolean): List<Pair<String, String>> {
        val sql = if (mysql) {
            "SELECT table_schema, table_name FROM information_schema.columns " +
            "WHERE column_name = ? AND table_schema = DATABASE() ORDER BY table_name"
        } else {
            "SELECT table_schema, table_name FROM information_schema.columns " +
            "WHERE column_name = ? AND table_schema NOT IN ('information_schema','pg_catalog') " +
            "ORDER BY table_schema, table_name"
        }
        val result = mutableListOf<Pair<String, String>>()
        jdbc.prepareStatement(sql).use { ps ->
            ps.setString(1, colName)
            ps.executeQuery().use { rs ->
                while (rs.next()) result.add(rs.getString(1) to rs.getString(2))
            }
        }
        return result
    }

    private fun tableColumns(jdbc: JdbcConnection, schema: String, table: String, mysql: Boolean): List<String> {
        val sql = if (mysql) {
            "SELECT column_name FROM information_schema.columns " +
            "WHERE table_schema = DATABASE() AND table_name = ? ORDER BY ordinal_position"
        } else {
            "SELECT column_name FROM information_schema.columns " +
            "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position"
        }
        val result = mutableListOf<String>()
        jdbc.prepareStatement(sql).use { ps ->
            if (mysql) {
                ps.setString(1, table)
            } else {
                ps.setString(1, schema)
                ps.setString(2, table)
            }
            ps.executeQuery().use { rs -> while (rs.next()) result.add(rs.getString(1)) }
        }
        return result
    }

    private fun findSchema(jdbc: JdbcConnection, table: String, preferred: String, mysql: Boolean): String? {
        if (mysql) {
            val sql = "SELECT DATABASE() AS db"
            jdbc.createStatement().use { st ->
                st.executeQuery(sql).use { rs ->
                    if (!rs.next()) return null
                    val db = rs.getString("db") ?: return null
                    jdbc.prepareStatement(
                        "SELECT table_name FROM information_schema.tables " +
                        "WHERE table_schema = DATABASE() AND table_name = ? LIMIT 1"
                    ).use { ps ->
                        ps.setString(1, table)
                        ps.executeQuery().use { rs2 -> return if (rs2.next()) db else null }
                    }
                }
            }
        } else {
            val sql = "SELECT table_schema FROM information_schema.tables " +
                "WHERE table_name = ? AND table_schema NOT IN ('information_schema','pg_catalog') " +
                "ORDER BY CASE WHEN table_schema = ? THEN 0 ELSE 1 END LIMIT 1"
            jdbc.prepareStatement(sql).use { ps ->
                ps.setString(1, table)
                ps.setString(2, preferred)
                ps.executeQuery().use { rs -> return if (rs.next()) rs.getString(1) else null }
            }
        }
    }

    private fun fetchRow(jdbc: JdbcConnection, schema: String, table: String, pkCol: String, pkVal: String, mysql: Boolean): Map<String, Any?>? {
        val q = quote(table, mysql)
        val qPk = quote(pkCol, mysql)
        val sql = if (mysql) "SELECT * FROM $q WHERE $qPk = ?"
                  else       "SELECT * FROM ${quote(schema, false)}.$q WHERE $qPk = ?"
        jdbc.prepareStatement(sql).use { ps ->
            ps.setString(1, pkVal)
            ps.executeQuery().use { rs ->
                if (!rs.next()) return null
                return resultRowToMap(rs)
            }
        }
    }

    private fun fetchChildRows(jdbc: JdbcConnection, schema: String, table: String, fkCol: String, fkVal: String, mysql: Boolean): List<Map<String, Any?>> {
        val q = quote(table, mysql)
        val qFk = quote(fkCol, mysql)
        val sql = if (mysql) "SELECT * FROM $q WHERE $qFk = ?"
                  else       "SELECT * FROM ${quote(schema, false)}.$q WHERE $qFk = ?"
        jdbc.prepareStatement(sql).use { ps ->
            ps.setString(1, fkVal)
            ps.executeQuery().use { rs ->
                val rows = mutableListOf<Map<String, Any?>>()
                while (rs.next()) rows.add(resultRowToMap(rs))
                return rows
            }
        }
    }

    private fun resultRowToMap(rs: ResultSet): Map<String, Any?> {
        val meta = rs.metaData
        val map = LinkedHashMap<String, Any?>()
        for (i in 1..meta.columnCount) map[meta.getColumnName(i)] = rs.getObject(i)
        return map
    }

    private fun deleteRows(jdbc: JdbcConnection, schema: String, table: String, col: String, value: String, mysql: Boolean): Int {
        val q = quote(table, mysql)
        val qc = quote(col, mysql)
        val sql = if (mysql) "DELETE FROM $q WHERE $qc = ?"
                  else       "DELETE FROM ${quote(schema, false)}.$q WHERE $qc = ?"
        jdbc.prepareStatement(sql).use { ps ->
            ps.setString(1, value)
            return ps.executeUpdate()
        }
    }

    private fun insertRow(jdbc: JdbcConnection, schema: String, table: String, columns: List<String>, row: Map<String, Any?>, mysql: Boolean) {
        val qt = quote(table, mysql)
        val qSchema = if (mysql) "" else "${quote(schema, false)}."
        val colStr = columns.joinToString(", ") { quote(it, mysql) }
        val ph = columns.joinToString(", ") { "?" }
        val sql = "INSERT INTO $qSchema$qt ($colStr) VALUES ($ph)"
        jdbc.prepareStatement(sql).use { ps ->
            columns.forEachIndexed { i, col ->
                ps.setObject(i + 1, row[col])
            }
            ps.executeUpdate()
        }
    }

    private fun matchColumns(srcCols: List<String>, tgtCols: List<String>, tableName: String): List<String> {
        val tgtSet = tgtCols.toSet()
        val srcSet = srcCols.toSet()
        val common = srcCols.filter { it in tgtSet }
        val onlySrc = srcCols.filter { it !in tgtSet }
        val onlyTgt = tgtCols.filter { it !in srcSet }
        if (onlySrc.isNotEmpty()) log("warn", "[$tableName] Columns in source only (skipped): $onlySrc")
        if (onlyTgt.isNotEmpty()) log("warn", "[$tableName] Columns in target only (NULL/DEFAULT): $onlyTgt")
        return common
    }

    private fun applyOverrides(row: Map<String, Any?>): Map<String, Any?> {
        if (fieldOverrides.isEmpty()) return row
        val result = LinkedHashMap(row)
        fieldOverrides.forEach { (col, value) -> if (col in result) result[col] = value }
        return result
    }

    fun run(): TransferSummary {
        val summary = TransferSummary(startedAt = System.currentTimeMillis(), dryRun = dryRun)

        val dirCheck = checkDirection(source.environment, target.environment)
        if (!dirCheck.allowed) throw DirectionError(dirCheck.reason)
        log("info", dirCheck.reason)

        val srcMysql = isMysql(source)
        val tgtMysql = isMysql(target)

        log("step", "Connecting to source (${source.environment.label}): ${source.maskedSummary()}")
        val srcJdbc = try { openConnection(source) } catch (e: Exception) {
            throw TransferError("Source connection failed: ${e.message}")
        }
        log("ok", "Source connection established")

        log("step", "Connecting to target (${target.environment.label}): ${target.maskedSummary()}")
        val tgtJdbc = try { openConnection(target) } catch (e: Exception) {
            srcJdbc.close()
            throw TransferError("Target connection failed: ${e.message}")
        }
        log("ok", "Target connection established")

        tgtJdbc.autoCommit = false

        try {
            val srcSchema = findSchema(srcJdbc, rootTable, "public", srcMysql)
                ?: throw TransferError("Table '$rootTable' not found in source database.")
            log("info", "Schema: $srcSchema")

            val rootRow = fetchRow(srcJdbc, srcSchema, rootTable, pkColumn, recordId, srcMysql)
                ?: throw TransferError("No row in '$rootTable' where $pkColumn = $recordId")
            log("ok", "Root record found ($rootTable.$pkColumn=$recordId)")

            // transfer root row
            val rMain = TableResult(tableName = rootTable, schemaName = srcSchema, totalRows = 1)
            val srcRootCols = tableColumns(srcJdbc, srcSchema, rootTable, srcMysql)
            val tgtSchema = findSchema(tgtJdbc, rootTable, srcSchema, tgtMysql) ?: srcSchema
            val tgtRootCols = tableColumns(tgtJdbc, tgtSchema, rootTable, tgtMysql)
            val commonRoot = matchColumns(srcRootCols, tgtRootCols, rootTable)
            val rootData = applyOverrides(rootRow)

            if (dryRun) {
                log("info", "[$rootTable] Would transfer 1 row (dry run)")
                rMain.rowsTransferred = 1
            } else {
                if (!skipDelete) {
                    val deleted = deleteRows(tgtJdbc, tgtSchema, rootTable, pkColumn, recordId, tgtMysql)
                    if (deleted > 0) log("info", "[$rootTable] Deleted $deleted existing row(s)")
                }
                try {
                    insertRow(tgtJdbc, tgtSchema, rootTable, commonRoot, rootData, tgtMysql)
                    rMain.rowsTransferred = 1
                    log("ok", "[$rootTable] 1 row transferred")
                } catch (e: Exception) {
                    rMain.errors.add(e.message ?: "Insert error")
                    log("error", "[$rootTable] Insert error: ${e.message}")
                }
                tgtJdbc.commit()
            }
            summary.results.add(rMain)

            // child tables
            val allTables = tablesWithColumn(srcJdbc, fkColumn, srcMysql)
            val childTables = allTables.filter { it.second != rootTable }
            log("info", "Found ${childTables.size} child table(s) with column '$fkColumn'")

            childTables.forEachIndexed { idx, (tblSchema, tblName) ->
                if (cancelCheck()) {
                    log("warn", "Transfer cancelled by user.")
                    return@forEachIndexed
                }
                onPercent(idx + 1, childTables.size)
                val r = TableResult(tableName = tblName, schemaName = tblSchema)

                val rows = try {
                    fetchChildRows(srcJdbc, tblSchema, tblName, fkColumn, recordId, srcMysql)
                } catch (e: Exception) {
                    r.skipped = true
                    r.skipReason = "Read error: ${e.message}"
                    log("error", "[$tblName] Read error: ${e.message}")
                    summary.results.add(r)
                    return@forEachIndexed
                }

                if (rows.isEmpty()) {
                    r.skipped = true
                    r.skipReason = "No rows in source"
                    summary.results.add(r)
                    return@forEachIndexed
                }

                r.totalRows = rows.size

                if (dryRun) {
                    log("info", "[$tblName] Would transfer ${rows.size} row(s) (dry run)")
                    r.rowsTransferred = rows.size
                    summary.results.add(r)
                    return@forEachIndexed
                }

                val tgtTblSchema = findSchema(tgtJdbc, tblName, tblSchema, tgtMysql)
                if (tgtTblSchema == null) {
                    r.skipped = true
                    r.skipReason = "Table not found in target (schema drift)"
                    log("warn", "[$tblName] Not in target, skipping")
                    summary.results.add(r)
                    return@forEachIndexed
                }

                val srcChildCols = try { tableColumns(srcJdbc, tblSchema, tblName, srcMysql) } catch (e: Exception) { emptyList() }
                val tgtChildCols = try { tableColumns(tgtJdbc, tgtTblSchema, tblName, tgtMysql) } catch (e: Exception) { emptyList() }

                if (tgtChildCols.isEmpty()) {
                    r.skipped = true
                    r.skipReason = "No columns in target table"
                    summary.results.add(r)
                    return@forEachIndexed
                }

                val commonChild = matchColumns(srcChildCols, tgtChildCols, tblName)
                if (commonChild.isEmpty()) {
                    r.skipped = true
                    r.skipReason = "No common columns"
                    summary.results.add(r)
                    return@forEachIndexed
                }

                if (!skipDelete) {
                    val deleted = deleteRows(tgtJdbc, tgtTblSchema, tblName, fkColumn, recordId, tgtMysql)
                    if (deleted > 0) log("info", "[$tblName] Deleted $deleted existing row(s)")
                }

                rows.forEachIndexed { i, row ->
                    val rowData = applyOverrides(row)
                    try {
                        insertRow(tgtJdbc, tgtTblSchema, tblName, commonChild, rowData, tgtMysql)
                        r.rowsTransferred++
                    } catch (e: Exception) {
                        r.errors.add("Row ${i + 1}: ${e.message}")
                        log("error", "[$tblName] Row ${i + 1}: ${e.message}")
                    }
                }
                tgtJdbc.commit()
                log("ok", "[$tblName] ${r.rowsTransferred}/${rows.size} rows transferred")
                summary.results.add(r)
            }

        } catch (e: Exception) {
            summary.fatalError = e.message ?: "Unknown error"
            log("error", "Fatal error: ${e.message}")
            try { tgtJdbc.rollback() } catch (_: Exception) {}
        } finally {
            try { srcJdbc.close() } catch (_: Exception) {}
            try { tgtJdbc.close() } catch (_: Exception) {}
        }

        summary.results.forEach { r ->
            if (r.skipped) summary.skippedTables++
            else {
                summary.totalRows += r.rowsTransferred
                summary.totalErrors += r.errors.size
            }
        }
        summary.finishedAt = System.currentTimeMillis()
        return summary
    }

    companion object {
        fun testConnection(conn: Connection): Pair<Boolean, String> {
            return try {
                Class.forName(conn.driverClass())
                val jdbc = DriverManager.getConnection(conn.jdbcUrl(), conn.user, conn.password)
                jdbc.createStatement().use { it.executeQuery("SELECT 1") }
                jdbc.close()
                true to "Connection successful."
            } catch (e: Exception) {
                false to (e.message ?: "Connection failed")
            }
        }
    }
}

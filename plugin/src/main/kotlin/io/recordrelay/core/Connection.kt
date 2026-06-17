package io.recordrelay.core

import java.util.UUID

enum class DbType(val displayName: String, val defaultPort: Int, val jdbcPrefix: String) {
    POSTGRESQL("PostgreSQL", 5432, "jdbc:postgresql"),
    MYSQL("MySQL / MariaDB", 3306, "jdbc:mysql");

    companion object {
        fun fromString(s: String): DbType = when (s.lowercase()) {
            "mysql" -> MYSQL
            else    -> POSTGRESQL
        }
    }
}

data class Connection(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val environmentName: String,
    val host: String,
    val port: Int,
    val dbname: String,
    val user: String,
    var password: String = "",
    val dbType: DbType = DbType.POSTGRESQL,
    val note: String = ""
) {
    val environment: Environment get() = Environment.of(environmentName)

    fun jdbcUrl(): String = when (dbType) {
        DbType.POSTGRESQL -> "jdbc:postgresql://$host:$port/$dbname"
        DbType.MYSQL      -> "jdbc:mysql://$host:$port/$dbname?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC"
    }

    fun maskedSummary(): String = "$host:$port/$dbname"

    fun driverClass(): String = when (dbType) {
        DbType.POSTGRESQL -> "org.postgresql.Driver"
        DbType.MYSQL      -> "com.mysql.cj.jdbc.Driver"
    }
}

package io.recordrelay.store

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.reflect.TypeToken
import com.intellij.credentialStore.CredentialAttributes
import com.intellij.credentialStore.Credentials
import com.intellij.ide.passwordSafe.PasswordSafe
import com.intellij.ide.util.PropertiesComponent
import io.recordrelay.core.Connection
import io.recordrelay.core.DbType

private const val STORE_KEY = "io.recordrelay.connections"
private const val SERVICE_NAME = "RecordRelay"

data class ConnectionDto(
    val id: String,
    val name: String,
    val environmentName: String,
    val host: String,
    val port: Int,
    val dbname: String,
    val user: String,
    val dbType: String = "POSTGRESQL",
    val note: String = ""
)

class ConnectionStore {
    private val gson: Gson = GsonBuilder().create()
    private val props = PropertiesComponent.getInstance()

    private fun loadDtos(): MutableList<ConnectionDto> {
        val json = props.getValue(STORE_KEY) ?: return mutableListOf()
        return try {
            val type = object : TypeToken<MutableList<ConnectionDto>>() {}.type
            gson.fromJson(json, type) ?: mutableListOf()
        } catch (_: Exception) {
            mutableListOf()
        }
    }

    private fun saveDtos(dtos: List<ConnectionDto>) {
        props.setValue(STORE_KEY, gson.toJson(dtos))
    }

    private fun loadPassword(connId: String): String {
        val attrs = CredentialAttributes(SERVICE_NAME, connId)
        return PasswordSafe.instance.getPassword(attrs) ?: ""
    }

    private fun savePassword(connId: String, password: String) {
        val attrs = CredentialAttributes(SERVICE_NAME, connId)
        PasswordSafe.instance.set(attrs, Credentials(connId, password))
    }

    private fun removePassword(connId: String) {
        val attrs = CredentialAttributes(SERVICE_NAME, connId)
        PasswordSafe.instance.set(attrs, null)
    }

    private fun dtoToConnection(dto: ConnectionDto): Connection {
        val pwd = loadPassword(dto.id)
        return Connection(
            id = dto.id,
            name = dto.name,
            environmentName = dto.environmentName,
            host = dto.host,
            port = dto.port,
            dbname = dto.dbname,
            user = dto.user,
            password = pwd,
            dbType = DbType.valueOf(dto.dbType.uppercase()),
            note = dto.note
        )
    }

    private fun connectionToDto(conn: Connection): ConnectionDto = ConnectionDto(
        id = conn.id,
        name = conn.name,
        environmentName = conn.environmentName,
        host = conn.host,
        port = conn.port,
        dbname = conn.dbname,
        user = conn.user,
        dbType = conn.dbType.name,
        note = conn.note
    )

    fun loadAll(): List<Connection> = loadDtos().map { dtoToConnection(it) }

    fun getById(id: String): Connection? = loadDtos().find { it.id == id }?.let { dtoToConnection(it) }

    fun add(conn: Connection) {
        val dtos = loadDtos()
        dtos.add(connectionToDto(conn))
        saveDtos(dtos)
        savePassword(conn.id, conn.password)
    }

    fun update(conn: Connection) {
        val dtos = loadDtos()
        val idx = dtos.indexOfFirst { it.id == conn.id }
        if (idx >= 0) {
            dtos[idx] = connectionToDto(conn)
            saveDtos(dtos)
            savePassword(conn.id, conn.password)
        }
    }

    fun remove(id: String) {
        val dtos = loadDtos().filter { it.id != id }
        saveDtos(dtos)
        removePassword(id)
    }
}

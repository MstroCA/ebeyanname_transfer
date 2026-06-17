package io.recordrelay.core

import java.util.UUID

data class TransferProfile(
    val id: String = UUID.randomUUID().toString(),
    val name: String,
    val rootTable: String,
    val pkColumn: String = "id",
    val fkColumn: String,
    val description: String = "",
    val isBuiltin: Boolean = false
) {
    companion object {
        val BUILTINS = listOf(
            TransferProfile(
                id = "__beyanname__",
                name = "Beyanname (Turkish Tax Declaration)",
                rootTable = "beyanname",
                pkColumn = "id",
                fkColumn = "beyanname_id",
                description = "Turkish tax declaration records and all related child tables.",
                isBuiltin = true
            ),
            TransferProfile(
                id = "__order__",
                name = "Order / Invoice",
                rootTable = "order",
                pkColumn = "id",
                fkColumn = "order_id",
                description = "Order record and all related line items.",
                isBuiltin = true
            ),
            TransferProfile(
                id = "__user__",
                name = "User Record",
                rootTable = "user",
                pkColumn = "id",
                fkColumn = "user_id",
                description = "User record and all user-owned data.",
                isBuiltin = true
            ),
            TransferProfile(
                id = "__custom__",
                name = "Custom (Manual)",
                rootTable = "",
                pkColumn = "id",
                fkColumn = "",
                description = "Enter root table and FK column names manually.",
                isBuiltin = true
            )
        )

        val BUILTIN_IDS = BUILTINS.map { it.id }.toSet()
    }
}

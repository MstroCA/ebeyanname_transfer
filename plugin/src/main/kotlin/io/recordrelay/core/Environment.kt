package io.recordrelay.core

data class Environment(val name: String, val rank: Int) {

    val label: String
        get() = when (name.uppercase()) {
            "PROD", "PRODUCTION" -> "Production"
            "STAGING"            -> "Staging"
            "TEST"               -> "Test"
            "QA"                 -> "QA"
            "LOCAL"              -> "Local"
            "DEV", "DEVELOPMENT" -> "Development"
            else                 -> name
        }

    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other is Environment) return name.uppercase() == other.name.uppercase()
        if (other is String) return name.uppercase() == other.uppercase()
        return false
    }

    override fun hashCode(): Int = name.uppercase().hashCode()

    override fun toString(): String = name

    companion object {
        val PROD    = Environment("PROD", 3)
        val STAGING = Environment("STAGING", 2)
        val TEST    = Environment("TEST", 2)
        val QA      = Environment("QA", 2)
        val LOCAL   = Environment("LOCAL", 1)
        val DEV     = Environment("DEV", 1)

        val DEFAULTS = listOf(PROD, STAGING, TEST, QA, LOCAL, DEV)

        fun of(name: String): Environment =
            DEFAULTS.find { it.name.equals(name, ignoreCase = true) }
                ?: Environment(name, 0)
    }
}

data class DirectionCheck(val allowed: Boolean, val reason: String)

fun checkDirection(source: Environment, target: Environment): DirectionCheck {
    if (source.name.equals(target.name, ignoreCase = true))
        return DirectionCheck(false, "Cannot transfer to the same environment (${source.label}).")
    if (source.rank > target.rank)
        return DirectionCheck(true, "${source.label} → ${target.label}: Transfer allowed (data flows downstream).")
    if (source.rank == target.rank)
        return DirectionCheck(false, "${source.label} → ${target.label}: Same-tier transfer not allowed.")
    return DirectionCheck(false, "${source.label} → ${target.label}: BLOCKED — data cannot flow upstream.")
}

fun allowedTargetsFor(source: Environment, allEnvs: List<Environment> = Environment.DEFAULTS): List<Environment> =
    allEnvs.filter { checkDirection(source, it).allowed }

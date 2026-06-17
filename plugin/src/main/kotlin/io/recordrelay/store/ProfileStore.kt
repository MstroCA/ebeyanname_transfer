package io.recordrelay.store

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.reflect.TypeToken
import com.intellij.ide.util.PropertiesComponent
import io.recordrelay.core.TransferProfile

private const val PROFILES_KEY = "io.recordrelay.profiles"

class ProfileStore {
    private val gson: Gson = GsonBuilder().create()
    private val props = PropertiesComponent.getInstance()

    private fun loadUserProfiles(): MutableList<TransferProfile> {
        val json = props.getValue(PROFILES_KEY) ?: return mutableListOf()
        return try {
            val type = object : TypeToken<MutableList<TransferProfile>>() {}.type
            (gson.fromJson(json, type) as? MutableList<TransferProfile>)
                ?.filter { it.id !in TransferProfile.BUILTIN_IDS }
                ?.toMutableList()
                ?: mutableListOf()
        } catch (_: Exception) {
            mutableListOf()
        }
    }

    private fun saveUserProfiles(profiles: List<TransferProfile>) {
        val nonBuiltin = profiles.filter { !it.isBuiltin }
        props.setValue(PROFILES_KEY, gson.toJson(nonBuiltin))
    }

    fun loadAll(): List<TransferProfile> = TransferProfile.BUILTINS + loadUserProfiles()

    fun getById(id: String): TransferProfile? = loadAll().find { it.id == id }

    fun add(profile: TransferProfile) {
        if (profile.id in TransferProfile.BUILTIN_IDS) return
        val profiles = loadUserProfiles()
        profiles.add(profile)
        saveUserProfiles(profiles)
    }

    fun update(profile: TransferProfile) {
        if (profile.id in TransferProfile.BUILTIN_IDS) return
        val profiles = loadUserProfiles()
        val idx = profiles.indexOfFirst { it.id == profile.id }
        if (idx >= 0) {
            profiles[idx] = profile
            saveUserProfiles(profiles)
        }
    }

    fun remove(id: String) {
        if (id in TransferProfile.BUILTIN_IDS) return
        val profiles = loadUserProfiles().filter { it.id != id }
        saveUserProfiles(profiles)
    }
}

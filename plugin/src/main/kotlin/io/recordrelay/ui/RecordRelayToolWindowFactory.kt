package io.recordrelay.ui

import com.intellij.openapi.project.Project
import com.intellij.openapi.wm.ToolWindow
import com.intellij.openapi.wm.ToolWindowFactory
import com.intellij.ui.content.ContentFactory
import com.intellij.ui.components.JBTabbedPane
import io.recordrelay.store.ConnectionStore
import io.recordrelay.store.ProfileStore
import io.recordrelay.ui.panels.ConnectionsPanel
import io.recordrelay.ui.panels.HistoryPanel
import io.recordrelay.ui.panels.ProfilesPanel
import io.recordrelay.ui.panels.TransferPanel
import javax.swing.JPanel

class RecordRelayToolWindowFactory : ToolWindowFactory {

    override fun createToolWindowContent(project: Project, toolWindow: ToolWindow) {
        val connectionStore = ConnectionStore()
        val profileStore = ProfileStore()

        val tabs = JBTabbedPane()

        val transferPanel = TransferPanel(connectionStore, profileStore)
        val connectionsPanel = ConnectionsPanel(connectionStore) {
            transferPanel.reloadConnections()
        }
        val profilesPanel = ProfilesPanel(profileStore) {
            transferPanel.reloadProfiles()
        }
        val historyPanel = HistoryPanel()

        tabs.addTab("Transfer", transferPanel)
        tabs.addTab("Connections", connectionsPanel)
        tabs.addTab("Profiles", profilesPanel)
        tabs.addTab("History", historyPanel)

        tabs.addChangeListener {
            when (tabs.selectedIndex) {
                3 -> historyPanel.refresh()
            }
        }

        val content = ContentFactory.getInstance().createContent(tabs, "", false)
        toolWindow.contentManager.addContent(content)
    }
}

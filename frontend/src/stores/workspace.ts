import { ref } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'paperai:workspace-ui'
const defaults = { sidebarCollapsed: false, agentDrawerOpen: false, activePanels: {} as Record<string, string> }

const restore = () => {
  if (typeof localStorage === 'undefined') return { ...defaults, activePanels: {} }
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return { sidebarCollapsed: Boolean(value.sidebarCollapsed), agentDrawerOpen: Boolean(value.agentDrawerOpen), activePanels: value.activePanels && typeof value.activePanels === 'object' ? value.activePanels : {} }
  } catch { return { ...defaults, activePanels: {} } }
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const initial = restore()
  const sidebarCollapsed = ref(initial.sidebarCollapsed)
  const agentDrawerOpen = ref(initial.agentDrawerOpen)
  const activePanels = ref<Record<string, string>>(initial.activePanels)
  const persist = () => { if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, JSON.stringify({ sidebarCollapsed: sidebarCollapsed.value, agentDrawerOpen: agentDrawerOpen.value, activePanels: activePanels.value })) }
  const activePanel = (projectId: string) => activePanels.value[projectId] || 'research-brief'
  const setActivePanel = (projectId: string, panel: string) => { activePanels.value = { ...activePanels.value, [projectId]: panel }; persist() }
  const setSidebarCollapsed = (value: boolean) => { sidebarCollapsed.value = value; persist() }
  const setAgentDrawerOpen = (value: boolean) => { agentDrawerOpen.value = value; persist() }
  return { sidebarCollapsed, agentDrawerOpen, activePanels, activePanel, setActivePanel, setSidebarCollapsed, setAgentDrawerOpen }
})

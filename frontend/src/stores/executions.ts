import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { approveExecution, cancelExecution, listExecutionEvents, listProjectExecutions, listUserExecutions, pauseExecution, resumeExecution, streamExecutionEvents, type AgentEvent, type AgentExecution } from '@/api/executions'

const terminalStatuses = new Set<AgentExecution['status']>(['completed', 'failed', 'cancelled'])

export const useExecutionsStore = defineStore('executions', () => {
  const byProject = ref<Record<string, AgentExecution[]>>({})
  const globalExecutions = ref<AgentExecution[]>([])
  const eventsByExecution = ref<Record<string, AgentEvent[]>>({})
  const loadingProjects = ref<Record<string, boolean>>({})
  const streamControllers = new Map<string, AbortController>()
  const allExecutions = computed(() => {
    const unique = new Map<string, AgentExecution>()
    globalExecutions.value.forEach(item => unique.set(item.id, item))
    Object.values(byProject.value).flat().forEach(item => unique.set(item.id, item))
    return [...unique.values()].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))
  })
  const runningCount = computed(() => allExecutions.value.filter(item => ['queued', 'running', 'waiting_user', 'paused'].includes(item.status)).length)
  const projectExecutions = (projectId: string) => byProject.value[projectId] || []
  const executionEvents = (executionId: string) => eventsByExecution.value[executionId] || []
  const loadProject = async (projectId: string) => {
    loadingProjects.value = { ...loadingProjects.value, [projectId]: true }
    try { byProject.value = { ...byProject.value, [projectId]: (await listProjectExecutions(projectId)).items || [] } }
    finally { loadingProjects.value = { ...loadingProjects.value, [projectId]: false } }
  }
  const loadGlobal = async () => { globalExecutions.value = (await listUserExecutions()).items || [] }
  const loadEvents = async (executionId: string) => { eventsByExecution.value = { ...eventsByExecution.value, [executionId]: (await listExecutionEvents(executionId)).items || [] } }
  const stopStream = (executionId: string) => { streamControllers.get(executionId)?.abort(); streamControllers.delete(executionId) }
  const startStream = async (projectId: string, executionId: string) => {
    stopStream(executionId)
    const controller = new AbortController()
    streamControllers.set(executionId, controller)
    const known = executionEvents(executionId)
    const after = known.reduce((latest, event) => Math.max(latest, event.seq), 0)
    try {
      await streamExecutionEvents(executionId, after, event => {
        const current = executionEvents(executionId)
        if (!current.some(item => item.seq === event.seq)) eventsByExecution.value = { ...eventsByExecution.value, [executionId]: [...current, event] }
      }, controller.signal)
      await Promise.all([loadProject(projectId), loadGlobal()])
    } catch (error) {
      if (!controller.signal.aborted) throw error
    } finally {
      if (streamControllers.get(executionId) === controller) streamControllers.delete(executionId)
    }
  }
  const act = async (projectId: string, executionId: string, action: 'pause' | 'resume' | 'cancel' | 'approve') => {
    if (action === 'pause') await pauseExecution(executionId)
    if (action === 'resume') await resumeExecution(executionId)
    if (action === 'cancel') await cancelExecution(executionId)
    if (action === 'approve') await approveExecution(executionId)
    await Promise.all([loadProject(projectId), loadGlobal()])
  }
  const shouldStream = (execution: AgentExecution) => !terminalStatuses.has(execution.status)
  return { byProject, globalExecutions, eventsByExecution, loadingProjects, allExecutions, runningCount, projectExecutions, executionEvents, loadProject, loadGlobal, loadEvents, startStream, stopStream, shouldStream, act }
})

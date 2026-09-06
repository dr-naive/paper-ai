import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getExecution, respondExecution, approveExecution, cancelExecution, createResearchExecution, createWritingExecution, getExecutionEvaluation, getExecutionTrace, listExecutionEvents, listProjectExecutions, listUserExecutions, pauseExecution, resumeExecution, streamExecutionEvents, type AgentEvent, type AgentExecution, type ExecutionEvaluation, type ExecutionTraceReport, type ResearchExecutionCreate, type WritingExecutionCreate } from '@/api/executions'

const streamStopStatuses = new Set<AgentExecution['status']>(['waiting_user', 'blocked', 'paused', 'completed', 'partial', 'failed', 'cancelled'])

export const useExecutionsStore = defineStore('executions', () => {
  const byProject = ref<Record<string, AgentExecution[]>>({})
  const globalExecutions = ref<AgentExecution[]>([])
  const eventsByExecution = ref<Record<string, AgentEvent[]>>({})
  const tracesByExecution = ref<Record<string, ExecutionTraceReport>>({})
  const evaluationsByExecution = ref<Record<string, ExecutionEvaluation>>({})
  const loadingProjects = ref<Record<string, boolean>>({})
  const streamControllers = new Map<string, AbortController>()
  const allExecutions = computed(() => {
    const unique = new Map<string, AgentExecution>()
    globalExecutions.value.forEach(item => unique.set(item.id, item))
    Object.values(byProject.value).flat().forEach(item => unique.set(item.id, item))
    return [...unique.values()].sort((left, right) => Date.parse(right.updated_at) - Date.parse(left.updated_at))
  })
  const runningCount = computed(() => allExecutions.value.filter(item => ['pending', 'queued', 'running', 'retrying', 'waiting_user', 'paused'].includes(item.status)).length)
  const projectExecutions = (projectId: string) => byProject.value[projectId] || []
  const executionEvents = (executionId: string) => eventsByExecution.value[executionId] || []
  const executionTrace = (executionId: string) => tracesByExecution.value[executionId] || null
  const executionEvaluation = (executionId: string) => evaluationsByExecution.value[executionId] || null
  const upsert = (execution: AgentExecution) => {
    globalExecutions.value = [execution, ...globalExecutions.value.filter(item => item.id !== execution.id)]
    if (execution.project_id) {
      const current = projectExecutions(execution.project_id)
      byProject.value = { ...byProject.value, [execution.project_id]: [execution, ...current.filter(item => item.id !== execution.id)] }
    }
  }
  const loadProject = async (projectId: string) => {
    loadingProjects.value = { ...loadingProjects.value, [projectId]: true }
    try { byProject.value = { ...byProject.value, [projectId]: (await listProjectExecutions(projectId)).items || [] } }
    finally { loadingProjects.value = { ...loadingProjects.value, [projectId]: false } }
  }
  const loadGlobal = async () => { globalExecutions.value = (await listUserExecutions()).items || [] }
  const loadEvents = async (executionId: string) => { eventsByExecution.value = { ...eventsByExecution.value, [executionId]: (await listExecutionEvents(executionId)).items || [] } }
  const loadTrace = async (executionId: string) => {
    const [trace, evaluation] = await Promise.all([getExecutionTrace(executionId), getExecutionEvaluation(executionId)])
    tracesByExecution.value = { ...tracesByExecution.value, [executionId]: trace }
    evaluationsByExecution.value = { ...evaluationsByExecution.value, [executionId]: evaluation }
  }
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
        if (event.type === 'progress_changed' || event.type.startsWith('execution_')) void getExecution(executionId).then(upsert).catch(() => undefined)
        const execution = allExecutions.value.find(item => item.id === executionId)
        if (execution && event.stage) upsert({ ...execution, current_stage: event.stage, updated_at: event.timestamp })
      }, controller.signal)
      await Promise.all([loadProject(projectId), loadGlobal(), loadTrace(executionId)])
    } catch (error) {
      if (!controller.signal.aborted) throw error
    } finally {
      if (streamControllers.get(executionId) === controller) streamControllers.delete(executionId)
    }
  }
  const act = async (projectId: string, executionId: string, action: 'pause' | 'resume' | 'cancel' | 'approve') => {
    let updated: AgentExecution | undefined
    if (action === 'pause') updated = await pauseExecution(executionId)
    if (action === 'resume') updated = await resumeExecution(executionId)
    if (action === 'cancel') updated = await cancelExecution(executionId)
    if (action === 'approve') updated = await approveExecution(executionId)
    if (updated) upsert(updated)
    await Promise.all([loadProject(projectId), loadGlobal()])
    if (action === 'resume') void startStream(projectId, executionId)
  }
  const respond = async (executionId: string, selectedResultIds: string[]) => {
    const execution = await respondExecution(executionId, selectedResultIds)
    upsert(execution)
    if (execution.project_id) void startStream(execution.project_id, executionId)
  }
  const createWriting = async (projectId: string, data: WritingExecutionCreate) => {
    const execution = await createWritingExecution(projectId, data)
    upsert(execution)
    eventsByExecution.value = { ...eventsByExecution.value, [execution.id]: [] }
    return execution
  }
  const createResearch = async (projectId: string, data: ResearchExecutionCreate) => {
    const execution = await createResearchExecution(projectId, data)
    upsert(execution)
    eventsByExecution.value = { ...eventsByExecution.value, [execution.id]: [] }
    return execution
  }
  const shouldStream = (execution: AgentExecution) => !streamStopStatuses.has(execution.status)
  return { byProject, globalExecutions, eventsByExecution, tracesByExecution, evaluationsByExecution, loadingProjects, allExecutions, runningCount, projectExecutions, executionEvents, executionTrace, executionEvaluation, loadProject, loadGlobal, loadEvents, loadTrace, startStream, stopStream, shouldStream, act, respond, createWriting, createResearch }
})

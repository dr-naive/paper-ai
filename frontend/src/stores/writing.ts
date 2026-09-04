import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { WritingGenerationProposal, WritingRewriteProposal } from '@/api/documents'

export interface WritingEditorContext {
  selectionFrom: number
  selectionTo: number
  selectedText: string
  selectedCharacterCount: number
  currentHeading: string
  sectionPath: string[]
  nearbyText: string
}

export type WritingProposal = WritingRewriteProposal | WritingGenerationProposal
export type WritingAgentStatus = 'idle' | 'generating' | 'ready' | 'error'

export interface WritingAgentMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
}

const emptyContext = (): WritingEditorContext => ({
  selectionFrom: 0,
  selectionTo: 0,
  selectedText: '',
  selectedCharacterCount: 0,
  currentHeading: '正文开头',
  sectionPath: [],
  nearbyText: '',
})

export const useWritingStore = defineStore('writing', () => {
  const projectId = ref('')
  const documentId = ref('')
  const revisionId = ref('')
  const editorContext = ref<WritingEditorContext>(emptyContext())
  const outlinePanelCollapsed = ref(false)
  const agentPanelCollapsed = ref(false)
  const messages = ref<WritingAgentMessage[]>([])
  const activeProposal = ref<WritingProposal | null>(null)
  const requestStatus = ref<WritingAgentStatus>('idle')
  const requestStage = ref('')
  const requestError = ref('')

  const hasSelection = computed(() => editorContext.value.selectedCharacterCount > 0)

  const clearAgent = () => {
    messages.value = []
    activeProposal.value = null
    requestStatus.value = 'idle'
    requestStage.value = ''
    requestError.value = ''
  }

  const setWorkspace = (nextProjectId: string, nextDocumentId = '', nextRevisionId = '') => {
    projectId.value = nextProjectId
    documentId.value = nextDocumentId
    revisionId.value = nextRevisionId
    editorContext.value = emptyContext()
    clearAgent()
  }
  const setEditorContext = (context: WritingEditorContext) => { editorContext.value = context }
  const setRevision = (id: string) => { revisionId.value = id }
  const appendMessage = (message: WritingAgentMessage) => { messages.value = [...messages.value, message] }
  const setProposal = (proposal: WritingProposal | null) => { activeProposal.value = proposal }
  const startRequest = (stage: string) => {
    requestStatus.value = 'generating'
    requestStage.value = stage
    requestError.value = ''
    activeProposal.value = null
  }
  const finishRequest = (proposal: WritingProposal) => {
    activeProposal.value = proposal
    requestStatus.value = 'ready'
    requestStage.value = '已准备好建议'
    requestError.value = ''
  }
  const failRequest = (message: string) => {
    requestStatus.value = 'error'
    requestStage.value = ''
    requestError.value = message
  }
  const markApplied = () => {
    activeProposal.value = null
    requestStatus.value = 'ready'
    requestStage.value = '建议已应用'
    requestError.value = ''
  }
  const setOutlinePanelCollapsed = (value: boolean) => { outlinePanelCollapsed.value = value }
  const setAgentPanelCollapsed = (value: boolean) => { agentPanelCollapsed.value = value }
  const clear = () => {
    projectId.value = ''
    documentId.value = ''
    revisionId.value = ''
    editorContext.value = emptyContext()
    clearAgent()
    outlinePanelCollapsed.value = false
    agentPanelCollapsed.value = false
  }

  return {
    projectId,
    documentId,
    revisionId,
    editorContext,
    messages,
    activeProposal,
    requestStatus,
    requestStage,
    requestError,
    outlinePanelCollapsed,
    agentPanelCollapsed,
    hasSelection,
    setWorkspace,
    setEditorContext,
    setRevision,
    appendMessage,
    setProposal,
    startRequest,
    finishRequest,
    failRequest,
    markApplied,
    clearAgent,
    setOutlinePanelCollapsed,
    setAgentPanelCollapsed,
    clear,
  }
})

<template>
  <section class="writing-v2" :class="{ 'agent-collapsed': writingStore.agentPanelCollapsed, 'outline-collapsed': writingStore.outlinePanelCollapsed }" aria-label="正式论文写作工作区">
    <WritingOutlinePanel
      :documents="documents"
      :active-document-id="activeDocument?.id"
      :outline="outline"
      :current-heading="writingStore.editorContext.currentHeading"
      :loading="loading"
      :collapsed="writingStore.outlinePanelCollapsed"
      @create-document="createNewDocument"
      @open-document="openDocument"
      @add-section="addSection"
      @focus-heading="focusHeading"
      @toggle="writingStore.setOutlinePanelCollapsed(!writingStore.outlinePanelCollapsed)"
    />

    <main class="editor-column">
      <div v-if="!activeDocument" class="editor-empty">
        <h3>开始正式论文写作</h3>
        <p>正文将保存为可回溯 revision，研究产物仍保留在原来的 Artifact 区域。</p>
        <a-button type="primary" @click="createNewDocument">新建论文文档</a-button>
      </div>
      <template v-else>
        <header class="document-header">
          <input v-model="documentTitle" aria-label="文档标题" @change="titleDirty = true" />
          <div class="document-meta" aria-live="polite">
            <span class="revision-version">v{{ revisionVersion }}</span>
            <span class="save-state" :class="{ 'save-state-error': saveError }">{{ saveError || saveStateLabel }}</span>
          </div>
          <div class="document-actions">
            <a-button :loading="auditing" @click="runCitationAudit">引用检查</a-button>
            <a-button type="primary" :loading="saving" :disabled="!editor" @click="saveRevision()">保存版本</a-button>
          </div>
        </header>
        <div v-if="editor" class="editor-toolbar" role="toolbar" aria-label="文本格式">
          <select class="heading-select" aria-label="文本样式" :value="currentHeadingLevel" @change="changeHeading">
            <option value="paragraph">正文</option>
            <option value="1">标题 1</option>
            <option value="2">标题 2</option>
            <option value="3">标题 3</option>
          </select>
          <span class="toolbar-divider" role="separator" aria-hidden="true"></span>
          <button type="button" class="toolbar-icon-button" :class="{ active: editor.isActive('bold') }" aria-label="粗体" title="粗体" @click="editor.chain().focus().toggleBold().run()"><IconBold aria-hidden="true" /></button>
          <button type="button" class="toolbar-icon-button" :class="{ active: editor.isActive('italic') }" aria-label="斜体" title="斜体" @click="editor.chain().focus().toggleItalic().run()"><IconItalic aria-hidden="true" /></button>
          <button type="button" class="toolbar-icon-button" :class="{ active: editor.isActive('blockquote') }" aria-label="引用" title="引用" @click="editor.chain().focus().toggleBlockquote().run()"><IconQuote aria-hidden="true" /></button>
          <button type="button" class="toolbar-icon-button" :class="{ active: editor.isActive('bulletList') }" aria-label="列表" title="列表" @click="editor.chain().focus().toggleBulletList().run()"><IconList aria-hidden="true" /></button>
          <span class="toolbar-divider" role="separator" aria-hidden="true"></span>
          <button type="button" class="toolbar-icon-button" :disabled="!editor.can().chain().focus().undo().run()" aria-label="撤销" title="撤销" @click="editor.chain().focus().undo().run()"><IconUndo aria-hidden="true" /></button>
          <button type="button" class="toolbar-icon-button" :disabled="!editor.can().chain().focus().redo().run()" aria-label="重做" title="重做" @click="editor.chain().focus().redo().run()"><IconRedo aria-hidden="true" /></button>
        </div>
        <div class="editor-paper"><editor-content :editor="editor || undefined" class="editor-surface" /></div>
        <section v-if="citationAudit" class="audit-panel" aria-live="polite">
          <header><strong>引用检查</strong><span>{{ citationAudit.citation_count }} 个引用 · {{ citationAudit.linked_evidence_count }} 个已绑定证据</span><a-button size="mini" @click="citationAudit = null">关闭</a-button></header>
          <p v-if="citationAudit.passed && !citationAudit.issue_count" class="audit-pass">所有引用均已连接到当前项目的有效证据。</p>
          <ul v-else><li v-for="issue in citationAudit.issues" :key="`${issue.citation_index}-${issue.code}-${issue.claim_excerpt || ''}`" :class="issue.severity"><strong v-if="issue.code === 'unsupported_claim'">Unsupported claim</strong><template v-else>引用 {{ issue.citation_index + 1 }}</template>：{{ issue.message }}<blockquote v-if="issue.claim_excerpt">{{ issue.claim_excerpt }}</blockquote></li></ul>
        </section>
      </template>
    </main>

    <WritingAgentPanel
      :context="writingStore.editorContext"
      :collapsed="writingStore.agentPanelCollapsed"
      :revision-version="revisionVersion"
      :messages="writingStore.messages"
      :proposal="writingStore.activeProposal"
      :request-status="writingStore.requestStatus"
      :request-stage="writingStore.requestStage"
      :request-error="writingStore.requestError"
      :can-submit="agentCanSubmit"
      :replace-disabled="replaceDisabled"
      :replace-disabled-reason="replaceDisabledReason"
      :evidence="evidence"
      :project-id="props.projectId"
      @toggle="writingStore.setAgentPanelCollapsed(!writingStore.agentPanelCollapsed)"
      @submit="submitAgentInstruction"
      @copy="copyProposal"
      @replace="replaceProposal"
      @dismiss="writingStore.setProposal(null)"
    >
      <template #evidence>
        <section v-if="activeDocument" class="evidence-library">
          <header class="evidence-heading"><strong>当前项目已保存证据</strong><span>{{ filteredEvidence.length }} 条</span></header>
          <div class="evidence-content">
            <a-input v-model="evidenceSearch" allow-clear placeholder="搜索证据" />
            <p v-if="!filteredEvidence.length" class="rail-empty">当前项目还没有可用证据。<br />在阅读论文时保存证据，或让写作助手基于已导入论文检索支持内容。</p>
            <article v-for="item in filteredEvidence" :key="item.id">
              <strong>{{ item.source_title }}</strong>
              <span v-if="item.page_number">第 {{ item.page_number }} 页</span>
              <p>{{ item.snippet }}</p>
              <p v-if="item.normalized_claim" class="evidence-claim">支持：{{ item.normalized_claim }}</p>
              <div><a-button size="mini" @click="openEvidence(item)">查看原文</a-button><a-button size="mini" @click="insertCitation(item)">插入引用</a-button></div>
            </article>
          </div>
        </section>
      </template>
    </WritingAgentPanel>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { Editor, EditorContent } from '@tiptap/vue-3'
import { Node, type Editor as CoreEditor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { Message, Modal } from '@arco-design/web-vue'
import { IconBold, IconItalic, IconList, IconQuote, IconRedo, IconUndo } from '@arco-design/web-vue/es/icon'
import { auditCitations, createDocument, createRevision, getDocument, listDocuments, rewriteSelection, updateDocument, type CitationAudit, type WritingCitationMapping, type WritingDocument, type WritingGenerateRequest, type WritingRewriteRequest } from '@/api/documents'
import { listEvidence, type EvidenceItem } from '@/api/projects'
import { useExecutionsStore } from '@/stores/executions'
import { useWritingStore, type WritingProposal } from '@/stores/writing'
import { deriveWritingContext, type WritingOutlineItem } from '@/utils/writingContext'
import { citationPlaceholder, copyTextToClipboard, proposalInlineContent, proposalPlainText, selectionAnchorIsCurrent, type SelectionAnchor } from '@/utils/writingProposal'
import WritingAgentPanel from './WritingAgentPanel.vue'
import WritingOutlinePanel from './WritingOutlinePanel.vue'

const props = defineProps<{ projectId: string }>()
const writingStore = useWritingStore()
const executionStore = useExecutionsStore()
const activeExecutionId = ref('')
const Citation = Node.create({ name: 'citation', group: 'inline', inline: true, atom: true, addAttributes: () => ({ paper_id: { default: null }, citation_key: { default: '' }, evidence_id: { default: null } }), parseHTML: () => [{ tag: 'span[data-citation]' }], renderHTML: ({ HTMLAttributes }) => ['span', { ...HTMLAttributes, 'data-citation': '', class: 'citation-node' }, `[${HTMLAttributes.citation_key}]`] })

const documents = ref<WritingDocument[]>([])
const activeDocument = ref<WritingDocument | null>(null)
const evidence = ref<EvidenceItem[]>([])
const editor = shallowRef<Editor>()
const outline = ref<WritingOutlineItem[]>([])
const loading = ref(false)
const saving = ref(false)
const auditing = ref(false)
const documentTitle = ref('')
const titleDirty = ref(false)
const evidenceSearch = ref('')
const citationAudit = ref<CitationAudit | null>(null)
const revisionVersion = computed(() => activeDocument.value?.current_revision?.version || 1)
const currentHeadingLevel = computed(() => {
  // Keep the native select in sync with Tiptap without introducing editor state.
  editorContentVersion.value
  if (!editor.value) return 'paragraph'
  for (const level of [1, 2, 3]) if (editor.value.isActive('heading', { level })) return String(level)
  return 'paragraph'
})
const saveError = ref('')
const editorContentVersion = ref(0)
const proposalEditorVersion = ref(0)
const saveStateLabel = computed(() => saving.value ? '保存中…' : activeDocument.value ? '已保存' : '')
const filteredEvidence = computed(() => { const query = evidenceSearch.value.toLowerCase(); return evidence.value.filter(item => !query || `${item.source_title} ${item.snippet} ${item.normalized_claim}`.toLowerCase().includes(query)) })
const agentCanSubmit = computed(() => Boolean(activeDocument.value && editor.value && writingStore.requestStatus !== 'generating'))
const citationKeyForNode = (node: { attrs: Record<string, unknown> }, index: number, seen: Set<string>) => {
  const base = String(node.attrs.citation_key || `citation-${index + 1}`).trim() || `citation-${index + 1}`
  let key = base
  let suffix = 2
  while (seen.has(key)) key = `${base}-${suffix++}`
  seen.add(key)
  return key
}
const selectedTextWithCitations = (from: number, to: number) => {
  if (!editor.value || from === to) return { selectedText: '', citations: [] as WritingCitationMapping[] }
  const entries: WritingCitationMapping[] = []
  const seen = new Set<string>()
  editor.value.state.doc.nodesBetween(from, to, node => {
    if (node.type.name !== 'citation') return
    const citationKey = citationKeyForNode(node, entries.length, seen)
    entries.push({
      citation_key: citationKey,
      paper_id: String(node.attrs.paper_id || ''),
      evidence_id: String(node.attrs.evidence_id || ''),
      claim_text: String(node.attrs.claim_text || ''),
    })
  })
  let citationIndex = 0
  const selectedText = editor.value.state.doc.textBetween(from, to, '\n\n', node => {
    if (node.type.name !== 'citation') return ''
    const citation = entries[citationIndex++]
    return citation ? citationPlaceholder(citation.citation_key) : ''
  })
  return { selectedText, citations: entries }
}
const currentSelectionAnchor = computed<SelectionAnchor>(() => ({
  revisionId: activeDocument.value?.current_revision_id || '',
  from: writingStore.editorContext.selectionFrom,
  to: writingStore.editorContext.selectionTo,
  selectedText: selectedTextWithCitations(writingStore.editorContext.selectionFrom, writingStore.editorContext.selectionTo).selectedText,
}))
const replaceDisabled = computed(() => {
  const proposal = writingStore.activeProposal
  if (!proposal || proposal.kind !== 'rewrite') return true
  if (editorContentVersion.value !== proposalEditorVersion.value) return true
  return !selectionAnchorIsCurrent({ revisionId: proposal.base_revision_id, from: proposal.selection.from, to: proposal.selection.to, selectedText: proposal.original_content }, currentSelectionAnchor.value)
})
const replaceDisabledReason = computed(() => replaceDisabled.value ? '正文或选区已发生变化，请重新选择后再次生成建议。' : '')

const syncEditorContext = (instance: CoreEditor | undefined = editor.value) => {
  if (!instance) return
  saveError.value = ''
  const { from, to } = instance.state.selection
  const snapshot = deriveWritingContext(instance.state.doc as unknown as Parameters<typeof deriveWritingContext>[0], from, to)
  outline.value = snapshot.outline
  writingStore.setEditorContext({ selectionFrom: snapshot.selectionFrom, selectionTo: snapshot.selectionTo, selectedText: snapshot.selectedText, selectedCharacterCount: snapshot.selectedCharacterCount, currentHeading: snapshot.currentHeading, sectionPath: snapshot.sectionPath, nearbyText: snapshot.nearbyText })
}
const initializeEditor = (content: Record<string, unknown>) => {
  editor.value?.destroy()
  editorContentVersion.value += 1
  editor.value = new Editor({
    extensions: [StarterKit, Citation],
    content,
    onCreate: ({ editor: instance }) => syncEditorContext(instance),
    onUpdate: ({ editor: instance }) => { editorContentVersion.value += 1; syncEditorContext(instance) },
    onSelectionUpdate: ({ editor: instance }) => syncEditorContext(instance),
  })
}
const load = async () => {
  loading.value = true
  writingStore.setWorkspace(props.projectId)
  try {
    const [docs, evidenceResult] = await Promise.all([listDocuments(props.projectId), listEvidence(props.projectId)])
    documents.value = docs.items || []
    evidence.value = evidenceResult.items || []
    if (documents.value.length) await openDocument(documents.value[0].id)
    else activeDocument.value = null
  } finally { loading.value = false }
}
const openDocument = async (id: string) => {
  const item = await getDocument(id)
  activeDocument.value = item
  documentTitle.value = item.title
  writingStore.setWorkspace(props.projectId, item.id, item.current_revision_id || '')
  initializeEditor(item.current_revision?.content_json || { type: 'doc', content: [] })
  citationAudit.value = null
  saveError.value = ''
}
const createNewDocument = () => Modal.confirm({ title: '新建论文文档', content: '将创建一份独立于旧 WritingArtifact 的正式写作文档。', okText: '新建文档', onOk: async () => { const item = await createDocument(props.projectId, { title: '未命名论文' }); documents.value.unshift(item); await openDocument(item.id) } })
const saveRevision = async (createdBy: 'user' | 'agent' = 'user') => {
  if (!activeDocument.value || !editor.value) return
  saving.value = true
  saveError.value = ''
  try {
    if (titleDirty.value && documentTitle.value.trim()) { await updateDocument(activeDocument.value.id, { title: documentTitle.value.trim() }); activeDocument.value.title = documentTitle.value.trim(); titleDirty.value = false }
    const revision = await createRevision(activeDocument.value.id, { content_json: editor.value.getJSON(), created_by: createdBy })
    activeDocument.value.current_revision = revision
    activeDocument.value.current_revision_id = revision.id
    writingStore.setRevision(revision.id)
    Message.success(`已保存版本 v${revision.version}`)
  } catch (error) {
    saveError.value = '保存失败，请稍后重试。'
    Message.error(saveError.value)
    throw error
  } finally { saving.value = false }
}
const focusHeading = (pos: number) => editor.value?.chain().focus().setTextSelection(pos + 1).scrollIntoView().run()
const addSection = () => editor.value?.chain().focus().insertContent([{ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: '新章节' }] }, { type: 'paragraph' }]).run()
const changeHeading = (event: Event) => {
  if (!editor.value) return
  const value = (event.target as HTMLSelectElement).value
  const chain = editor.value.chain().focus()
  if (value === 'paragraph') chain.setParagraph().run()
  else chain.toggleHeading({ level: Number(value) as 1 | 2 | 3 }).run()
}
const friendlyWritingError = (error: unknown) => {
  const response = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  const detail = typeof response === 'object' && response !== null ? response as { code?: string; message?: string } : { message: typeof response === 'string' ? response : '' }
  const messages: Record<string, string> = {
    NO_IMPORTED_PAPERS: '当前项目还没有已导入且可用于引用的论文。请先到“文献发现”或“项目论文”导入论文。',
    NO_RELEVANT_PAPERS: '当前项目没有已完成解析且适合本次写作的论文，请调整要求或先完成论文解析。',
    NO_SUPPORTING_EVIDENCE: '当前项目已导入论文中没有找到足够证据支持这一写作要求。',
    WRITING_DOCUMENT_CONFLICT: '正文已发生变化，请重新选择后再次生成建议。',
    VERIFICATION_ERROR: '引用验证暂时不可用，建议不会被标记为已验证。',
    GENERATION_ERROR: '段落生成暂时不可用，文档未发生变化。',
    WRITING_REWRITE_ERROR: '改写服务暂时不可用，文档未发生变化。',
  }
  return messages[detail.code || ''] || detail.message || (error instanceof Error ? error.message : '') || '写作建议暂时不可用，请稍后重试。'
}
const submitAgentInstruction = async (instruction: string) => {
  if (!activeDocument.value || !editor.value || writingStore.requestStatus === 'generating') return
  const hasSelection = writingStore.hasSelection
  const baseRevisionId = activeDocument.value.current_revision_id || ''
  const requestEditorVersion = editorContentVersion.value
  writingStore.appendMessage({ id: `user-${Date.now()}`, role: 'user', content: instruction })
  writingStore.startRequest(hasSelection ? '正在准备当前选区的改写建议…' : '正在准备项目论文和证据…')
  try {
    let proposal: WritingProposal
    if (hasSelection) {
      const { selectionFrom, selectionTo } = writingStore.editorContext
      const selected = selectedTextWithCitations(selectionFrom, selectionTo)
      if (!selected.selectedText.trim()) {
        writingStore.failRequest('没有读取到有效选区，请重新选择正文后重试。')
        return
      }
      const payload: WritingRewriteRequest = {
        document_id: activeDocument.value.id,
        instruction,
        selected_text: selected.selectedText,
        selection_from: selectionFrom,
        selection_to: selectionTo,
        section_path: writingStore.editorContext.sectionPath,
        nearby_text: writingStore.editorContext.nearbyText,
        base_revision_id: baseRevisionId,
        citations: selected.citations,
      }
      proposal = await rewriteSelection(props.projectId, payload)
    } else {
      const payload: WritingGenerateRequest = {
        document_id: activeDocument.value.id,
        instruction,
        section_path: writingStore.editorContext.sectionPath,
        nearby_text: writingStore.editorContext.nearbyText,
        citation_style: 'gbt7714',
        base_revision_id: baseRevisionId,
      }
      const execution = await executionStore.createWriting(props.projectId, {
        agent_type: 'writing_generate',
        goal: instruction,
        input: payload,
      })
      activeExecutionId.value = execution.id
      await executionStore.loadEvents(execution.id)
      await executionStore.startStream(props.projectId, execution.id)
      const completed = executionStore.allExecutions.find(item => item.id === execution.id)
      if (completed?.status !== 'completed' || !completed.result_payload?.proposal) {
        throw new Error(completed?.error_message || '写作任务没有返回可用建议。')
      }
      proposal = completed.result_payload.proposal
    }
    writingStore.finishRequest(proposal)
    proposalEditorVersion.value = requestEditorVersion
    writingStore.appendMessage({ id: `assistant-${Date.now()}`, role: 'assistant', content: proposal.status === 'ready' ? '建议已生成，请检查内容和引用后决定是否复制或替换。' : '建议已生成，但有引用需要注意，请查看卡片中的验证状态。' })
  } catch (error) {
    writingStore.failRequest(friendlyWritingError(error))
  }
}
const copyProposal = async () => {
  const proposal = writingStore.activeProposal
  if (!proposal) return
  try {
    await copyTextToClipboard(proposalPlainText(proposal.content))
    Message.success('建议已复制到剪贴板')
  } catch {
    Message.error('复制失败，请检查浏览器剪贴板权限。')
  }
}
const replaceProposal = async () => {
  const proposal = writingStore.activeProposal
  if (!proposal || proposal.kind !== 'rewrite' || !editor.value || replaceDisabled.value) {
    if (proposal?.kind === 'rewrite' && replaceDisabled.value) writingStore.failRequest(replaceDisabledReason.value)
    return
  }
  const { from, to } = proposal.selection
  editor.value.chain().focus().insertContentAt({ from, to }, proposalInlineContent(proposal.content, proposal.citations)).run()
  try {
    await saveRevision('agent')
    writingStore.markApplied()
    writingStore.appendMessage({ id: `assistant-${Date.now()}`, role: 'assistant', content: '已替换选中内容，并保存为新的 revision。你仍可以使用撤销恢复原文。' })
  } catch {
    // saveRevision already surfaces the user-facing save error; keep the proposal available for retry.
  }
}
const runCitationAudit = async () => { if (!activeDocument.value) return; auditing.value = true; try { citationAudit.value = await auditCitations(activeDocument.value.id) } finally { auditing.value = false } }
const insertCitation = (item: EvidenceItem) => editor.value?.chain().focus().insertContent({ type: 'citation', attrs: { paper_id: item.paper_id, evidence_id: item.id, citation_key: `${item.source_title.slice(0, 18)}${item.source_year ? `, ${item.source_year}` : ''}` } }).run()
const openEvidence = (item: EvidenceItem) => window.open(`/paper/${item.paper_id}?project_id=${encodeURIComponent(props.projectId)}`, '_blank', 'noopener')

watch(() => props.projectId, load)
onMounted(load)
onBeforeUnmount(() => {
  if (activeExecutionId.value) executionStore.stopStream(activeExecutionId.value)
  editor.value?.destroy()
  writingStore.clear()
})
</script>

<style scoped>
.writing-v2 { position: relative; display: grid; grid-template-columns: 220px minmax(0, 1fr) 344px; min-height: calc(100vh - 112px); overflow: hidden; background: var(--pa-surface); }
.writing-v2.outline-collapsed { grid-template-columns: 44px minmax(0, 1fr) 344px; }
.writing-v2.agent-collapsed { grid-template-columns: 220px minmax(0, 1fr) 44px; }
.writing-v2.outline-collapsed.agent-collapsed { grid-template-columns: 44px minmax(0, 1fr) 44px; }
.editor-column { min-width: 0; background: var(--pa-surface); }
.editor-empty { padding: 80px 24px; text-align: center; }
.editor-empty p { margin: 8px 0 18px; color: var(--pa-muted); }
.document-header { display: flex; align-items: center; gap: 12px; min-height: 52px; padding: 8px 20px; border-bottom: 1px solid var(--pa-border); }
.document-header input { min-width: 0; flex: 1; border: 1px solid transparent; border-radius: var(--pa-radius-sm); background: transparent; color: var(--pa-ink); font-size: 15px; font-weight: 650; line-height: 32px; }
.document-header input:hover { border-color: var(--pa-border); }
.document-header input:focus { border-color: var(--pa-primary); outline: 0; box-shadow: var(--pa-focus-ring); }
.document-meta { display: flex; align-items: center; gap: 8px; white-space: nowrap; }
.revision-version { color: var(--pa-muted); font-size: 12px; }
.save-state { color: var(--pa-success); font-size: 12px; white-space: nowrap; }.save-state-error { color: var(--pa-danger); }
.document-actions { display: flex; align-items: center; gap: 8px; }
.editor-toolbar { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; min-height: 44px; padding: 6px 20px; border-bottom: 1px solid var(--pa-border); background: var(--pa-surface); }
.heading-select { height: 32px; padding: 0 28px 0 9px; border: 1px solid transparent; border-radius: var(--pa-radius-sm); background: var(--pa-surface); color: var(--pa-text); cursor: pointer; font: inherit; font-size: 12px; }
.heading-select:hover { border-color: var(--pa-border); }
.heading-select:focus-visible,.editor-toolbar button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.toolbar-divider { width: 1px; height: 20px; margin: 0 6px; background: var(--pa-border); }
.toolbar-icon-button { display: inline-grid; place-items: center; width: 32px; height: 32px; padding: 0; border: 1px solid transparent; border-radius: var(--pa-radius-sm); background: transparent; color: var(--pa-text); cursor: pointer; }
.toolbar-icon-button:hover { border-color: var(--pa-border); background: var(--pa-surface-soft); }
.toolbar-icon-button.active { border-color: var(--pa-primary); background: var(--pa-primary-soft); color: var(--pa-primary); }
.toolbar-icon-button:disabled { cursor: not-allowed; opacity: .4; }
.editor-paper { min-height: calc(100vh - 208px); padding: 24px 0 56px; background: var(--pa-bg); }
.editor-surface { width: min(100%, var(--pa-editor-reading-width)); min-height: calc(100vh - 208px); margin: 0 auto; background: var(--pa-surface); box-shadow: var(--pa-shadow-sm); }
.editor-surface :deep(.ProseMirror) { min-height: calc(100vh - 208px); padding: 40px 56px 96px; outline: 0; color: var(--pa-text); font-size: 16px; line-height: 1.78; }
.editor-surface :deep(.ProseMirror h1) { margin: 0 0 24px; color: var(--pa-ink); font-size: 28px; line-height: 1.25; }
.editor-surface :deep(.ProseMirror h2) { margin: 32px 0 14px; color: var(--pa-ink); font-size: 22px; line-height: 1.35; }
.editor-surface :deep(.ProseMirror h3) { margin: 24px 0 10px; color: var(--pa-ink); font-size: 18px; line-height: 1.4; }
.editor-surface :deep(.ProseMirror p) { margin: 0 0 16px; }
.editor-surface :deep(.ProseMirror ul),.editor-surface :deep(.ProseMirror ol) { margin: 0 0 16px; padding-left: 28px; }
.editor-surface :deep(.ProseMirror blockquote) { margin: 20px 0; padding-left: 18px; border-left: 2px solid var(--pa-border-strong); color: var(--pa-muted); }
.editor-surface :deep(.ProseMirror:focus-visible) { box-shadow: inset 0 0 0 2px var(--pa-primary-soft); }
.editor-surface :deep(.citation-node) { padding: 1px 5px; border: 1px solid rgb(177 58 23 / 0.18); border-radius: 4px; background: var(--pa-primary-soft); color: var(--pa-primary); }
.audit-panel { margin: 0 20px 20px; padding: 16px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-md); background: var(--pa-surface-soft); }
.audit-panel header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.audit-panel header span { flex: 1; color: var(--pa-muted); font-size: 12px; }
.audit-panel ul { margin: 10px 0 0; padding-left: 20px; }.audit-panel li { margin-top: 5px; font-size: 12px; }.audit-panel li.error { color: var(--pa-danger); }.audit-panel li.warning { color: var(--pa-warning); }.audit-panel blockquote { margin: 5px 0 0; padding-left: 8px; border-left: 2px solid currentColor; color: var(--pa-text); }.audit-pass { margin: 10px 0 0; color: var(--pa-success); font-size: 12px; }
.evidence-library { margin-top: 0; }.evidence-heading { display: flex; align-items: center; justify-content: space-between; min-height: 36px; color: var(--pa-text); font-size: 12px; }.evidence-heading span { color: var(--pa-muted); }.evidence-content { padding-bottom: 12px; }.rail-empty { margin-top: 10px; color: var(--pa-muted); font-size: 12px; line-height: 1.55; }.evidence-content article { padding: 14px 0; border-bottom: 1px solid var(--pa-border); }.evidence-content article > span { display: block; margin-top: 4px; color: var(--pa-muted); font-size: 11px; }.evidence-content article strong { display: block; margin: 3px 0; color: var(--pa-ink); font-size: 13px; font-weight: 650; }.evidence-content article p { display: -webkit-box; overflow: hidden; margin-top: 8px; font-size: 12px; line-height: 1.5; -webkit-box-orient: vertical; -webkit-line-clamp: 4; }.evidence-content article p.evidence-claim { margin-top: 6px; color: var(--pa-muted); -webkit-line-clamp: 2; }.evidence-content article div { display: flex; gap: 6px; margin-top: 10px; }
@media (min-width: 1024px) and (max-width: 1279px) { .writing-v2 { grid-template-columns: 196px minmax(0, 1fr) 320px; }.writing-v2.outline-collapsed { grid-template-columns: 44px minmax(0, 1fr) 320px; }.writing-v2.agent-collapsed { grid-template-columns: 196px minmax(0, 1fr) 44px; }.writing-v2.outline-collapsed.agent-collapsed { grid-template-columns: 44px minmax(0, 1fr) 44px; } }
@media (min-width: 768px) and (max-width: 1023px) { .writing-v2,.writing-v2.agent-collapsed { display: block; }.writing-v2 > :first-child { display: none; }.writing-v2 :deep(.agent-panel) { position: absolute; z-index: 10; top: 0; right: 0; bottom: 0; width: min(320px, 88vw); box-shadow: var(--pa-shadow-md); }.writing-v2 :deep(.agent-panel.collapsed) { width: 44px; height: 64px; bottom: auto; box-shadow: var(--pa-shadow-sm); }.editor-column { padding-right: 44px; } }
@media (max-width: 767px) { .writing-v2,.writing-v2.agent-collapsed { display: block; }.writing-v2 > :first-child,.writing-v2 :deep(.agent-panel) { display: none; }.document-header { flex-wrap: wrap; padding-inline: 16px; }.document-header input { flex-basis: calc(100% - 48px); }.document-meta { order: 3; }.document-actions { margin-left: auto; }.editor-toolbar { padding-inline: 16px; }.editor-paper { padding-top: 0; }.editor-surface { box-shadow: none; }.editor-surface :deep(.ProseMirror) { padding: 24px 18px 64px; } }
@media (pointer: coarse) { .editor-toolbar button { min-width: 44px; min-height: 44px; }.heading-select { height: 44px; } }
</style>

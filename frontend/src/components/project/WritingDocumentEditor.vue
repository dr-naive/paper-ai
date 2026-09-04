<template>
  <section class="writing-v2" aria-label="Writing V2 编辑器">
    <aside class="document-rail">
      <header><strong>文档</strong><a-button size="mini" @click="createNewDocument">新建文档</a-button></header>
      <button v-for="item in documents" :key="item.id" type="button" :class="{ active: item.id === activeDocument?.id }" @click="openDocument(item.id)"><strong>{{ item.title }}</strong><small>{{ item.status }} · {{ formatTime(item.updated_at) }}</small></button>
      <p v-if="!documents.length && !loading">还没有正式写作文档。</p>
      <div v-if="activeDocument" class="outline"><header><strong>大纲</strong><a-button size="mini" @click="addSection">添加章节</a-button></header><button v-for="heading in outline" :key="heading.pos" type="button" :style="{ paddingLeft: `${8 + (heading.level - 1) * 10}px` }" @click="focusHeading(heading.pos)">{{ heading.text }}</button><p v-if="!outline.length">使用“添加章节”建立论文结构。</p></div>
    </aside>

    <main class="editor-column">
      <div v-if="!activeDocument" class="editor-empty"><h3>开始正式论文写作</h3><p>正文将保存为可回溯 revision，研究产物仍保留在原来的 Artifact 区域。</p><a-button type="primary" @click="createNewDocument">新建论文文档</a-button></div>
      <template v-else>
        <header class="document-header"><input v-model="documentTitle" aria-label="文档标题" @change="titleDirty = true" /><span>v{{ activeDocument.current_revision?.version || 1 }}</span><a-button :loading="auditing" @click="runCitationAudit">引用审计</a-button><a-button type="primary" :loading="saving" :disabled="!editor" @click="saveRevision">保存新版本</a-button></header>
        <div v-if="editor" class="editor-toolbar" role="toolbar" aria-label="文本格式">
          <button type="button" :class="{ active: editor.isActive('heading', { level: 2 }) }" @click="editor.chain().focus().toggleHeading({ level: 2 }).run()">标题</button>
          <button type="button" :class="{ active: editor.isActive('bold') }" @click="editor.chain().focus().toggleBold().run()">粗体</button><button type="button" :class="{ active: editor.isActive('italic') }" @click="editor.chain().focus().toggleItalic().run()">斜体</button><button type="button" @click="editor.chain().focus().toggleBlockquote().run()">引用</button><button type="button" @click="editor.chain().focus().toggleBulletList().run()">列表</button>
          <a-dropdown trigger="click"><button type="button" :disabled="!hasSelection">AI 编辑</button><template #content><a-doption v-for="action in aiActions" :key="action.value" @click="requestAIEdit(action.value)">{{ action.label }}</a-doption></template></a-dropdown>
        </div>
        <editor-content :editor="editor || undefined" class="editor-surface" />
        <section v-if="proposal" class="diff-panel" aria-live="polite"><header><strong>AI 修改建议</strong><span>接受后才会写入编辑器并创建 revision</span></header><div class="diff-columns"><div><label>原文</label><p>{{ proposal.original }}</p></div><div><label for="replacement-text">建议文本</label><textarea id="replacement-text" v-model="proposal.replacement"></textarea></div></div><footer><a-button @click="proposal = null">拒绝修改</a-button><a-button type="primary" @click="acceptProposal">接受并保存版本</a-button></footer></section>
        <section v-if="citationAudit" class="audit-panel" aria-live="polite"><header><strong>引用审计</strong><span>{{ citationAudit.citation_count }} 个引用 · {{ citationAudit.linked_evidence_count }} 个已绑定证据</span><a-button size="mini" @click="citationAudit = null">关闭</a-button></header><p v-if="citationAudit.passed && !citationAudit.issue_count" class="audit-pass">所有引用均已连接到当前项目的有效证据。</p><ul v-else><li v-for="issue in citationAudit.issues" :key="`${issue.citation_index}-${issue.code}-${issue.claim_excerpt || ''}`" :class="issue.severity"><strong v-if="issue.code === 'unsupported_claim'">Unsupported claim</strong><template v-else>引用 {{ issue.citation_index + 1 }}</template>：{{ issue.message }}<blockquote v-if="issue.claim_excerpt">{{ issue.claim_excerpt }}</blockquote></li></ul></section>
      </template>
    </main>

    <aside class="evidence-rail">
      <header><strong>研究证据</strong><span>{{ filteredEvidence.length }}</span></header><a-input v-model="evidenceSearch" allow-clear placeholder="搜索证据" />
      <p v-if="!filteredEvidence.length" class="rail-empty">没有匹配证据。先从论文阅读器保存原文片段。</p>
      <article v-for="item in filteredEvidence" :key="item.id"><span>{{ item.evidence_type }} · p.{{ item.page_number || '?' }}</span><strong>{{ item.source_title }}</strong><p>{{ item.snippet }}</p><div><a-button size="mini" @click="insertCitation(item)">插入引用</a-button><a-button size="mini" @click="openEvidence(item)">打开来源</a-button></div></article>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { Editor, EditorContent } from '@tiptap/vue-3'
import { Node } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { Message, Modal } from '@arco-design/web-vue'
import { auditCitations, createDocument, createRevision, getDocument, listDocuments, proposeAIEdit, updateDocument, type AIEditProposal, type CitationAudit, type WritingDocument } from '@/api/documents'
import { listEvidence, type EvidenceItem } from '@/api/projects'

const props = defineProps<{ projectId: string }>()
const Citation = Node.create({ name: 'citation', group: 'inline', inline: true, atom: true, addAttributes: () => ({ paper_id: { default: null }, citation_key: { default: '' }, evidence_id: { default: null } }), parseHTML: () => [{ tag: 'span[data-citation]' }], renderHTML: ({ HTMLAttributes }) => ['span', { ...HTMLAttributes, 'data-citation': '', class: 'citation-node' }, `[${HTMLAttributes.citation_key}]`] })
const documents = ref<WritingDocument[]>([]), activeDocument = ref<WritingDocument | null>(null), evidence = ref<EvidenceItem[]>([])
const editor = shallowRef<Editor>(), loading = ref(false), saving = ref(false), auditing = ref(false), documentTitle = ref(''), titleDirty = ref(false), evidenceSearch = ref(''), proposal = ref<AIEditProposal | null>(null), citationAudit = ref<CitationAudit | null>(null)
const aiActions = [{ value: 'improve_style', label: '改善学术表达' }, { value: 'make_concise', label: '精简文字' }, { value: 'clarify_argument', label: '澄清论证' }, { value: 'find_evidence', label: '寻找支持证据' }, { value: 'check_claim', label: '检查主张' }]
const hasSelection = computed(() => !!editor.value && editor.value.state.selection.from !== editor.value.state.selection.to)
const filteredEvidence = computed(() => { const query = evidenceSearch.value.toLowerCase(); return evidence.value.filter(item => !query || `${item.source_title} ${item.snippet} ${item.normalized_claim}`.toLowerCase().includes(query)) })
const outline = computed(() => { const rows: Array<{ text: string; level: number; pos: number }> = []; editor.value?.state.doc.descendants((node, pos) => { if (node.type.name === 'heading') rows.push({ text: node.textContent || '未命名标题', level: node.attrs.level, pos }) }); return rows })
const formatTime = (value: string) => new Date(value).toLocaleDateString('zh-CN')
const initializeEditor = (content: Record<string, any>) => { editor.value?.destroy(); editor.value = new Editor({ extensions: [StarterKit, Citation], content }) }
const load = async () => { loading.value = true; try { const [docs, evidenceResult] = await Promise.all([listDocuments(props.projectId), listEvidence(props.projectId)]); documents.value = docs.items || []; evidence.value = evidenceResult.items || []; if (documents.value.length) await openDocument(documents.value[0].id) } finally { loading.value = false } }
const openDocument = async (id: string) => { const item = await getDocument(id); activeDocument.value = item; documentTitle.value = item.title; initializeEditor(item.current_revision?.content_json || { type: 'doc', content: [] }); proposal.value = null; citationAudit.value = null }
const createNewDocument = () => Modal.confirm({ title: '新建论文文档', content: '将创建一份独立于旧 WritingArtifact 的正式写作文档。', okText: '新建文档', onOk: async () => { const item = await createDocument(props.projectId, { title: '未命名论文' }); documents.value.unshift(item); await openDocument(item.id) } })
const saveRevision = async () => { if (!activeDocument.value || !editor.value) return; saving.value = true; try { if (titleDirty.value && documentTitle.value.trim()) { await updateDocument(activeDocument.value.id, { title: documentTitle.value.trim() }); activeDocument.value.title = documentTitle.value.trim(); titleDirty.value = false } const revision = await createRevision(activeDocument.value.id, { content_json: editor.value.getJSON() }); activeDocument.value.current_revision = revision; activeDocument.value.current_revision_id = revision.id; Message.success(`已保存版本 v${revision.version}`) } finally { saving.value = false } }
const focusHeading = (pos: number) => editor.value?.chain().focus().setTextSelection(pos + 1).scrollIntoView().run()
const addSection = () => editor.value?.chain().focus().insertContent([{ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: '新章节' }] }, { type: 'paragraph' }]).run()
const requestAIEdit = async (action: string) => { if (!activeDocument.value || !editor.value) return; const { from, to } = editor.value.state.selection; const selected = editor.value.state.doc.textBetween(from, to, ' '); if (!selected) return; proposal.value = await proposeAIEdit(activeDocument.value.id, { action, selected_text: selected, from_pos: from, to_pos: to }) }
const acceptProposal = async () => { if (!proposal.value || !editor.value) return; editor.value.chain().focus().insertContentAt({ from: proposal.value.range.from, to: proposal.value.range.to }, proposal.value.replacement).run(); proposal.value = null; await saveRevision() }
const runCitationAudit = async () => { if (!activeDocument.value) return; auditing.value = true; try { citationAudit.value = await auditCitations(activeDocument.value.id) } finally { auditing.value = false } }
const insertCitation = (item: EvidenceItem) => editor.value?.chain().focus().insertContent({ type: 'citation', attrs: { paper_id: item.paper_id, evidence_id: item.id, citation_key: `${item.source_title.slice(0, 18)}${item.source_year ? `, ${item.source_year}` : ''}` } }).run()
const openEvidence = (item: EvidenceItem) => window.open(`/paper/${item.paper_id}?project_id=${encodeURIComponent(props.projectId)}`, '_blank', 'noopener')
watch(() => props.projectId, load); onMounted(load); onBeforeUnmount(() => editor.value?.destroy())
</script>

<style scoped>
.writing-v2 { display: grid; grid-template-columns: 210px minmax(420px, 1fr) 280px; min-height: 680px; border: 1px solid var(--pa-border); border-radius: 8px; overflow: hidden; background: var(--pa-surface); }.document-rail,.evidence-rail { padding: 12px; background: var(--pa-surface-soft); }.document-rail { border-right: 1px solid var(--pa-border); }.evidence-rail { border-left: 1px solid var(--pa-border); }.document-rail header,.evidence-rail header,.document-header,.diff-panel header,.diff-panel footer { display: flex; align-items: center; justify-content: space-between; gap: 8px; }.document-rail > button,.outline button { display: flex; width: 100%; flex-direction: column; gap: 3px; margin-top: 8px; padding: 8px; border: 0; border-radius: 6px; background: transparent; color: var(--pa-text); cursor: pointer; text-align: left; }.document-rail > button.active { background: var(--color-primary-light-1); }.document-rail small,.document-rail p,.rail-empty { color: var(--pa-muted); font-size: 11px; }.outline { margin-top: 20px; padding-top: 12px; border-top: 1px solid var(--pa-border); }.outline button { margin-top: 2px; font-size: 12px; }.editor-column { min-width: 0; }.editor-empty { padding: 80px 24px; text-align: center; }.editor-empty p { color: var(--pa-muted); }.document-header { padding: 10px 14px; border-bottom: 1px solid var(--pa-border); }.document-header input { min-width: 0; flex: 1; border: 0; background: transparent; color: var(--pa-text); font-size: 17px; font-weight: 650; }.editor-toolbar { display: flex; flex-wrap: wrap; gap: 4px; padding: 8px 14px; border-bottom: 1px solid var(--pa-border); }.editor-toolbar button { min-height: 32px; padding: 4px 9px; border: 1px solid var(--pa-border); border-radius: 5px; background: var(--pa-surface); color: var(--pa-text); cursor: pointer; }.editor-toolbar button.active { border-color: var(--pa-primary); color: var(--pa-primary); }.editor-surface :deep(.ProseMirror) { min-height: 470px; padding: 24px clamp(20px, 6vw, 72px); outline: 0; color: var(--pa-text); line-height: 1.75; }.editor-surface :deep(.citation-node) { padding: 1px 5px; border-radius: 4px; background: var(--color-primary-light-1); color: var(--pa-primary); }.evidence-rail article { padding: 12px 0; border-bottom: 1px solid var(--pa-border); }.evidence-rail article > span { color: var(--pa-muted); font-size: 11px; }.evidence-rail article strong { display: block; margin: 3px 0; font-size: 12px; }.evidence-rail article p { display: -webkit-box; overflow: hidden; font-size: 12px; line-height: 1.5; -webkit-box-orient: vertical; -webkit-line-clamp: 4; }.evidence-rail article div { display: flex; gap: 6px; }.diff-panel { margin: 0 14px 14px; padding: 14px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--pa-surface-soft); }.diff-panel header span { color: var(--pa-muted); font-size: 12px; }.diff-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }.diff-columns > div { min-width: 0; }.diff-columns label { display: block; margin-bottom: 4px; font-size: 12px; font-weight: 600; }.diff-columns p,.diff-columns textarea { box-sizing: border-box; width: 100%; min-height: 96px; margin: 0; padding: 10px; border: 1px solid var(--pa-border); border-radius: 6px; background: var(--pa-surface); color: var(--pa-text); line-height: 1.5; }.diff-panel footer { justify-content: flex-end; }@media (max-width: 1000px) { .writing-v2 { grid-template-columns: 180px minmax(0, 1fr); }.evidence-rail { grid-column: 1 / -1; border-top: 1px solid var(--pa-border); border-left: 0; } }@media (max-width: 767px) { .writing-v2 { display: block; }.document-rail { border-right: 0; border-bottom: 1px solid var(--pa-border); }.diff-columns { grid-template-columns: 1fr; } }
.audit-panel { margin: 0 14px 14px; padding: 14px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--pa-surface-soft); }
.audit-panel header { display: flex; align-items: center; gap: 10px; }
.audit-panel header span { flex: 1; color: var(--pa-muted); font-size: 12px; }
.audit-panel ul { margin: 10px 0 0; padding-left: 20px; }
.audit-panel li { margin-top: 5px; font-size: 12px; }
.audit-panel li.error { color: var(--pa-danger, #c43d3d); }
.audit-panel li.warning { color: var(--pa-warning, #9a6700); }
.audit-panel blockquote { margin: 5px 0 0; padding-left: 8px; border-left: 2px solid currentColor; color: var(--pa-text); }
.audit-pass { margin: 10px 0 0; color: var(--pa-success, #2d7a46); font-size: 12px; }
</style>

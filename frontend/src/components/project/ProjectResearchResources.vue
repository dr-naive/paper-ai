<template>
  <section :aria-labelledby="`${mode}-resource-title`">
    <div class="resource-toolbar">
      <span :id="`${mode}-resource-title`" class="hint">{{ items.length }} 条{{ mode === 'notes' ? '笔记' : '可追溯证据' }}</span>
      <a-button type="primary" :disabled="mode === 'evidence' && papers.length === 0" @click="modalVisible = true">{{ mode === 'notes' ? '添加研究笔记' : '保存研究证据' }}</a-button>
    </div>
    <a-spin :loading="loading">
      <div v-if="!loading && !items.length" class="empty">
        <h3>{{ mode === 'notes' ? '记录会影响后续研究的内容' : '把论文原文变成可复用证据' }}</h3>
        <p v-if="mode === 'notes'">保存重要发现、研究问题、假设、决定或约束。临时搜索结果无需记入。</p>
        <p v-else>{{ papers.length ? '保存原文片段、页码和它支持的主张，后续写作可直接追溯。' : '先将论文加入项目文档库，再保存带来源的证据。' }}</p>
      </div>
      <ul v-else-if="mode === 'notes'" class="resource-list">
        <li v-for="note in notes" :key="note.id" class="note-row">
          <span class="type-label">{{ noteTypeLabel(note.type) }}</span>
          <div class="copy"><strong v-if="note.title">{{ note.title }}</strong><p>{{ note.content }}</p></div>
          <div class="meta"><span v-if="note.legacy" class="legacy">旧版记忆</span><time>{{ formatTime(note.updated_at) }}</time><a-button v-if="!note.legacy" type="text" status="danger" size="mini" @click="removeNote(note)">删除笔记</a-button></div>
        </li>
      </ul>
      <ul v-else class="resource-list">
        <li v-for="item in evidence" :key="item.id" class="evidence-row">
          <div class="source"><span class="type-label">{{ evidenceTypeLabel(item.evidence_type) }}</span><button type="button" @click="openPaper(item.paper_id)">{{ item.source_title }}<template v-if="item.page_number"> · p.{{ item.page_number }}</template></button></div>
          <blockquote>{{ item.snippet }}</blockquote><p v-if="item.normalized_claim" class="claim"><strong>支持主张：</strong>{{ item.normalized_claim }}</p>
          <a-button type="text" status="danger" size="mini" @click="removeEvidence(item)">删除证据</a-button>
        </li>
      </ul>
    </a-spin>

    <a-modal v-if="mode === 'notes'" v-model:visible="modalVisible" title="添加研究笔记" ok-text="保存笔记" :ok-loading="saving" @ok="saveNote">
      <a-form :model="noteForm" layout="vertical"><a-form-item label="笔记类型" required><a-select v-model="noteForm.type"><a-option v-for="option in noteTypes" :key="option.value" :value="option.value">{{ option.label }}</a-option></a-select></a-form-item><a-form-item label="标题（可选）"><a-input v-model="noteForm.title" placeholder="例如：选择双塔检索作为基线" /></a-form-item><a-form-item label="笔记内容" required><a-textarea v-model="noteForm.content" :auto-size="{ minRows: 3, maxRows: 8 }" placeholder="记录对后续研究有持续价值的内容" /></a-form-item></a-form>
    </a-modal>
    <a-modal v-else v-model:visible="modalVisible" title="保存研究证据" ok-text="保存证据" :ok-loading="saving" @ok="saveEvidence">
      <a-form :model="evidenceForm" layout="vertical"><a-form-item label="来源论文" required><a-select v-model="evidenceForm.paper_id" placeholder="选择项目论文"><a-option v-for="item in papers" :key="item.paper_id" :value="item.paper_id">{{ item.paper?.title || item.paper_id }}</a-option></a-select></a-form-item><a-form-item label="证据类型" required><a-select v-model="evidenceForm.evidence_type"><a-option v-for="option in evidenceTypes" :key="option.value" :value="option.value">{{ option.label }}</a-option></a-select></a-form-item><a-form-item label="原文片段" required><a-textarea v-model="evidenceForm.snippet" :auto-size="{ minRows: 4, maxRows: 10 }" placeholder="粘贴能够独立理解的论文原文" /></a-form-item><a-form-item label="支持的主张"><a-textarea v-model="evidenceForm.normalized_claim" :auto-size="{ minRows: 2, maxRows: 5 }" placeholder="用自己的话说明这段证据支持什么判断" /></a-form-item><a-form-item label="PDF 页码"><a-input-number v-model="evidenceForm.page_number" :min="1" placeholder="可选" /></a-form-item></a-form>
    </a-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Message, Modal } from '@arco-design/web-vue'
import { createEvidence, createResearchNote, deleteEvidence, deleteResearchNote, listEvidence, listResearchNotes, type EvidenceItem, type ProjectPaperItem, type ResearchNoteItem } from '@/api/projects'

const props = defineProps<{ projectId: string; mode: 'notes' | 'evidence'; papers: ProjectPaperItem[] }>()
const emit = defineEmits<{ count: [value: number] }>()
const notes = ref<ResearchNoteItem[]>([]), evidence = ref<EvidenceItem[]>([])
const loading = ref(false), saving = ref(false), modalVisible = ref(false)
const items = computed(() => props.mode === 'notes' ? notes.value : evidence.value)
const noteForm = ref({ type: 'finding', title: '', content: '' })
const evidenceForm = ref<{ paper_id: string; evidence_type: string; snippet: string; normalized_claim: string; page_number?: number }>({ paper_id: '', evidence_type: 'quote', snippet: '', normalized_claim: '' })
const noteTypes = [{ value: 'finding', label: '研究发现' }, { value: 'question', label: '待解决问题' }, { value: 'hypothesis', label: '研究假设' }, { value: 'decision', label: '研究决定' }, { value: 'definition', label: '术语定义' }, { value: 'constraint', label: '现实约束' }, { value: 'preference', label: '用户偏好' }, { value: 'summary', label: '阶段总结' }]
const evidenceTypes = [{ value: 'quote', label: '原文引述' }, { value: 'result', label: '实验结果' }, { value: 'method', label: '方法描述' }, { value: 'definition', label: '术语定义' }, { value: 'limitation', label: '局限' }, { value: 'comparison', label: '比较' }, { value: 'background', label: '研究背景' }]
const noteTypeLabel = (value: string) => noteTypes.find(item => item.value === value)?.label || value
const evidenceTypeLabel = (value: string) => evidenceTypes.find(item => item.value === value)?.label || value
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '未知时间'
const openPaper = (paperId: string) => window.open(`/paper/${paperId}?project_id=${encodeURIComponent(props.projectId)}`, '_blank', 'noopener')
const load = async () => { loading.value = true; try { if (props.mode === 'notes') notes.value = (await listResearchNotes(props.projectId)).items || []; else evidence.value = (await listEvidence(props.projectId)).items || []; emit('count', items.value.length) } catch (error: any) { Message.error(error?.response?.data?.detail || '加载研究资料失败') } finally { loading.value = false } }
const saveNote = async () => { if (!noteForm.value.content.trim()) return Message.warning('笔记内容必填'); saving.value = true; try { await createResearchNote(props.projectId, { ...noteForm.value, content: noteForm.value.content.trim() }); noteForm.value = { type: 'finding', title: '', content: '' }; modalVisible.value = false; await load(); Message.success('笔记已添加') } finally { saving.value = false } }
const saveEvidence = async () => { if (!evidenceForm.value.paper_id || !evidenceForm.value.snippet.trim()) return Message.warning('请选择来源论文并填写原文片段'); saving.value = true; try { await createEvidence(props.projectId, { ...evidenceForm.value, snippet: evidenceForm.value.snippet.trim() }); evidenceForm.value = { paper_id: '', evidence_type: 'quote', snippet: '', normalized_claim: '' }; modalVisible.value = false; await load(); Message.success('研究证据已保存') } finally { saving.value = false } }
const removeNote = (item: ResearchNoteItem) => Modal.confirm({ title: '删除研究笔记？', content: '该笔记将从项目研究资料中移除。', okText: '删除笔记', okButtonProps: { status: 'danger' }, onOk: async () => { await deleteResearchNote(props.projectId, item.id); await load() } })
const removeEvidence = (item: EvidenceItem) => Modal.confirm({ title: '删除研究证据？', content: '删除后，后续笔记和写作将无法继续引用这条证据。', okText: '删除证据', okButtonProps: { status: 'danger' }, onOk: async () => { await deleteEvidence(props.projectId, item.id); await load() } })
watch(() => [props.projectId, props.mode], load)
onMounted(load)
</script>

<style scoped>
.resource-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }.hint,time { color: var(--pa-muted); font-size: 12px; }.empty { padding: 40px 24px; border: 1px solid var(--pa-border); border-radius: 8px; text-align: center; }.empty h3 { margin: 0 0 6px; }.empty p { max-width: 65ch; margin: 0 auto; color: var(--pa-muted); }.resource-list { display: flex; flex-direction: column; gap: 8px; margin: 0; padding: 0; list-style: none; }.note-row,.evidence-row { padding: 14px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--color-bg-2); }.note-row { display: flex; align-items: flex-start; gap: 10px; }.type-label,.legacy { padding: 2px 8px; border-radius: 999px; background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 11px; white-space: nowrap; }.copy { flex: 1; }.copy strong { display: block; margin-bottom: 4px; }.copy p,.claim { max-width: 72ch; margin: 0; line-height: 1.6; }.meta { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }.source { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }.source button { overflow: hidden; border: 0; background: transparent; color: var(--pa-primary); cursor: pointer; text-overflow: ellipsis; white-space: nowrap; }.source button:focus-visible { outline: 2px solid var(--pa-primary); }.evidence-row blockquote { max-width: 72ch; margin: 0 0 10px; padding-left: 12px; border-left: 1px solid var(--pa-border); line-height: 1.65; }.claim { color: var(--pa-muted); }@media (max-width: 767px) { .note-row { flex-wrap: wrap; }.copy { flex-basis: calc(100% - 90px); }.meta { width: 100%; flex-direction: row; align-items: center; }.source { align-items: flex-start; }.source button { white-space: normal; text-align: left; } }
</style>

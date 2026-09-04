<template>
  <section class="writing-studio" aria-label="论文写作编辑器">
    <header class="studio-toolbar">
      <div class="format-tools" aria-label="正文格式">
        <select v-model="blockFormat" aria-label="段落格式" @change="formatBlock">
          <option value="p">正文</option><option value="h1">一级标题</option><option value="h2">二级标题</option><option value="h3">三级标题</option>
        </select>
        <button type="button" title="加粗" aria-label="加粗" @click="command('bold')"><strong>B</strong></button>
        <button type="button" title="斜体" aria-label="斜体" @click="command('italic')"><em>I</em></button>
        <button type="button" title="无序列表" aria-label="无序列表" @click="command('insertUnorderedList')">• 列表</button>
        <button type="button" title="插入引用占位" @click="insertText(' [待引用] ')">引用</button>
      </div>
      <div class="document-tools">
        <span :class="['save-state', { dirty }]">{{ saving ? '保存中' : dirty ? '有未保存修改' : '已保存' }}</span>
        <button type="button" @click="referencesOpen = !referencesOpen">参考文献</button>
        <a-button size="mini" type="primary" :loading="saving" @click="saveDocument">保存正文</a-button>
      </div>
    </header>

    <div :class="['studio-layout', { 'references-closed': !referencesOpen }]">
      <aside class="section-outline" aria-label="论文章节">
        <header><strong>章节</strong><button type="button" aria-label="新增章节" title="新增章节" @click="addSection">＋</button></header>
        <button v-for="section in sections" :key="section.id" type="button" :class="{ active: activeSectionId === section.id }" @click="switchSection(section.id)">{{ section.title }}</button>
        <input v-if="activeSection" v-model="activeSection.title" class="section-title-input" aria-label="当前章节名称" placeholder="章节名称" @input="dirty = true" />
      </aside>

      <main class="document-canvas">
        <input v-model="documentTitle" class="document-title" aria-label="论文标题" placeholder="输入论文标题" @input="dirty = true" />
        <div
          ref="editor"
          class="document-editor"
          contenteditable="true"
          role="textbox"
          aria-multiline="true"
          data-placeholder="从这里开始写作。可以先写观点和结构，缺少的证据稍后补充。"
          @input="onEditorInput"
          @blur="captureSelection"
        ></div>
      </main>

      <aside v-if="referencesOpen" class="reference-panel" aria-label="项目参考文献">
        <header><div><strong>参考文献</strong><span>{{ papers.length }} 篇</span></div><button type="button" aria-label="关闭参考文献" @click="referencesOpen = false">×</button></header>
        <input v-model="paperFilter" aria-label="筛选参考文献" placeholder="筛选标题或作者" />
        <div v-if="filteredPapers.length" class="reference-list">
          <article v-for="item in filteredPapers" :key="item.paper_id">
            <button type="button" class="reference-title" @click="openPaperPreview(item)">{{ item.paper?.title || '未命名论文' }}</button>
            <p>{{ item.paper?.authors || '作者未知' }}<span v-if="item.paper?.publication_year"> · {{ item.paper.publication_year }}</span></p>
            <div><button type="button" @click="insertCitation(item)">插入引用</button><button type="button" @click="openPaperPreview(item)">查看原文</button></div>
          </article>
        </div>
        <p v-else class="reference-empty">项目中还没有可引用论文。</p>
      </aside>
    </div>

    <aside v-if="previewPaper" class="paper-peek" aria-label="论文原文小窗">
      <header><div><strong>{{ previewPaper.paper?.title }}</strong><span>{{ previewPaper.paper?.authors }}</span></div><button type="button" aria-label="关闭论文小窗" @click="closePreview">×</button></header>
      <div class="paper-peek-tools"><input v-model="previewSearch" aria-label="搜索论文正文" placeholder="搜索正文" /><button type="button" :disabled="!activePreviewText" @click="citePreviewText">引用当前段落</button></div>
      <div class="paper-peek-body">
        <button v-for="section in filteredPreviewSections" :key="section.id" type="button" :class="{ active: activePreviewId === section.id }" @click="activePreviewId = section.id">
          <strong>{{ section.section_title }}</strong><span v-if="section.start_page">第 {{ section.start_page }} 页</span><p>{{ section.content }}</p>
        </button>
        <p v-if="previewLoading">正在读取论文正文…</p>
        <p v-else-if="!filteredPreviewSections.length">没有找到匹配正文。</p>
      </div>
    </aside>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { createArtifact, getArtifact, listArtifacts, updateArtifact, type ProjectPaperItem } from '@/api/projects'
import { getPaperSections } from '@/api/paper'

type DraftSection = { id: string; title: string; html: string }
const props = defineProps<{ projectId: string; papers: ProjectPaperItem[] }>()
const emit = defineEmits<{ saved: [] }>()
const editor = ref<HTMLElement | null>(null)
const artifactId = ref('')
const documentTitle = ref('未命名论文')
const sections = ref<DraftSection[]>([{ id: 'introduction', title: '引言', html: '' }])
const activeSectionId = ref('introduction')
const blockFormat = ref('p')
const dirty = ref(false)
const saving = ref(false)
const referencesOpen = ref(true)
const paperFilter = ref('')
const previewPaper = ref<ProjectPaperItem | null>(null)
const previewSections = ref<any[]>([])
const previewLoading = ref(false)
const previewSearch = ref('')
const activePreviewId = ref('')
let savedRange: Range | null = null

const activeSection = computed(() => sections.value.find(item => item.id === activeSectionId.value) || sections.value[0])
const filteredPapers = computed(() => {
  const q = paperFilter.value.trim().toLowerCase()
  return q ? props.papers.filter(item => `${item.paper?.title || ''} ${item.paper?.authors || ''}`.toLowerCase().includes(q)) : props.papers
})
const filteredPreviewSections = computed(() => {
  const q = previewSearch.value.trim().toLowerCase()
  return q ? previewSections.value.filter(item => `${item.section_title || ''} ${item.content || ''}`.toLowerCase().includes(q)) : previewSections.value
})
const activePreviewText = computed(() => previewSections.value.find(item => item.id === activePreviewId.value))

const syncEditor = async () => { await nextTick(); if (editor.value) editor.value.innerHTML = activeSection.value?.html || '' }
const onEditorInput = () => { if (activeSection.value && editor.value) activeSection.value.html = editor.value.innerHTML; dirty.value = true; captureSelection() }
const captureSelection = () => { const selection = window.getSelection(); if (selection?.rangeCount && editor.value?.contains(selection.anchorNode)) savedRange = selection.getRangeAt(0).cloneRange() }
const restoreSelection = () => { if (!savedRange) return; const selection = window.getSelection(); selection?.removeAllRanges(); selection?.addRange(savedRange) }
const command = (name: string) => { editor.value?.focus(); restoreSelection(); document.execCommand(name); onEditorInput() }
const formatBlock = () => { editor.value?.focus(); restoreSelection(); document.execCommand('formatBlock', false, blockFormat.value); onEditorInput() }
const insertText = (text: string) => { editor.value?.focus(); restoreSelection(); document.execCommand('insertText', false, text); onEditorInput() }
const citationKey = (item: ProjectPaperItem) => {
  const author = String(item.paper?.authors || 'source').split(/[,，;]/)[0].trim().split(/\s+/).pop() || 'source'
  return `${author.replace(/[^a-zA-Z0-9\u4e00-\u9fff]/g, '')}${item.paper?.publication_year || ''}`
}
const insertCitation = (item: ProjectPaperItem) => insertText(` [@${citationKey(item)}] `)
const switchSection = async (id: string) => { if (activeSection.value && editor.value) activeSection.value.html = editor.value.innerHTML; activeSectionId.value = id; await syncEditor() }
const addSection = async () => { const id = `section-${Date.now()}`; sections.value.push({ id, title: `新章节 ${sections.value.length + 1}`, html: '' }); activeSectionId.value = id; dirty.value = true; await syncEditor() }

const loadDocument = async () => {
  const result = await listArtifacts(props.projectId, 'outline')
  const item = result.items.find(entry => entry.meta?.workspace_kind === 'writing_document')
  if (!item) return syncEditor()
  const detail = await getArtifact(props.projectId, item.id)
  artifactId.value = detail.id
  documentTitle.value = String(detail.content?.document_title || detail.title || '未命名论文')
  const stored = detail.content?.sections
  if (Array.isArray(stored) && stored.length) sections.value = stored
  activeSectionId.value = String(detail.content?.active_section_id || sections.value[0].id)
  dirty.value = false
  await syncEditor()
}
const saveDocument = async () => {
  if (activeSection.value && editor.value) activeSection.value.html = editor.value.innerHTML
  saving.value = true
  const markdown = sections.value.map(item => `## ${item.title}\n\n${item.html.replace(/<[^>]+>/g, ' ')}`).join('\n\n')
  const payload = { title: documentTitle.value.trim() || '未命名论文', content: { document_title: documentTitle.value, sections: sections.value, active_section_id: activeSectionId.value }, markdown_text: markdown, html_text: sections.value.map(item => `<h2>${item.title}</h2>${item.html}`).join(''), meta: { workspace_kind: 'writing_document', generated_by: 'user' } }
  try {
    if (artifactId.value) await updateArtifact(props.projectId, artifactId.value, payload)
    else artifactId.value = (await createArtifact(props.projectId, { artifact_type: 'outline', status: 'in_progress', ...payload })).id
    dirty.value = false; emit('saved'); Message.success('正文已保存')
  } catch (e: any) { Message.error(e?.response?.data?.detail || '保存正文失败') } finally { saving.value = false }
}

const openPaperPreview = async (item: ProjectPaperItem) => {
  previewPaper.value = item; previewLoading.value = true; previewSections.value = []; activePreviewId.value = ''
  try { const result: any = await getPaperSections(item.paper_id); previewSections.value = result.sections || []; activePreviewId.value = previewSections.value[0]?.id || '' }
  catch { Message.error('读取论文正文失败') } finally { previewLoading.value = false }
}
const closePreview = () => { previewPaper.value = null; previewSections.value = []; previewSearch.value = '' }
const citePreviewText = () => {
  if (!previewPaper.value || !activePreviewText.value) return
  const page = activePreviewText.value.start_page ? `, p. ${activePreviewText.value.start_page}` : ''
  insertText(` [@${citationKey(previewPaper.value)}${page}] `)
  Message.success('已插入当前段落引用')
}
const handleShortcut = (event: KeyboardEvent) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); void saveDocument() }
}
onMounted(() => { void loadDocument(); window.addEventListener('keydown', handleShortcut) })
onBeforeUnmount(() => window.removeEventListener('keydown', handleShortcut))
</script>

<style scoped>
.writing-studio { position: relative; min-height: 680px; border: 1px solid var(--pa-border); border-radius: 8px; background: var(--pa-bg); overflow: hidden; }
.studio-toolbar { display: flex; min-height: 42px; align-items: center; justify-content: space-between; gap: 12px; padding: 5px 8px; border-bottom: 1px solid var(--pa-border); background: var(--pa-surface); }
.format-tools, .document-tools { display: flex; align-items: center; gap: 4px; }
.studio-toolbar button, .studio-toolbar select { min-height: 30px; padding: 0 8px; border: 1px solid transparent; border-radius: 5px; background: transparent; color: var(--pa-text); font: inherit; font-size: 11px; cursor: pointer; }
.studio-toolbar button:hover, .studio-toolbar select:hover { border-color: var(--pa-border); background: var(--pa-surface-soft); }
.studio-toolbar button:focus-visible, .studio-toolbar select:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 1px; }
.save-state { margin-right: 5px; color: var(--pa-muted); font-size: 10px; }
.save-state.dirty { color: var(--pa-primary); }
.studio-layout { display: grid; grid-template-columns: 154px minmax(480px, 1fr) 238px; min-height: 638px; }
.studio-layout.references-closed { grid-template-columns: 154px minmax(480px, 1fr); }
.section-outline { padding: 10px 7px; background: var(--pa-surface-soft); box-shadow: inset -1px 0 var(--pa-border); }
.section-outline header { display: flex; align-items: center; justify-content: space-between; padding: 0 6px 7px; font-size: 11px; }
.section-outline header button { width: 26px; height: 26px; border: 0; border-radius: 4px; background: transparent; cursor: pointer; }
.section-outline > button { display: block; width: 100%; min-height: 32px; padding: 5px 7px; overflow: hidden; border: 0; border-radius: 5px; background: transparent; color: var(--pa-muted); cursor: pointer; font: inherit; font-size: 11px; text-align: left; text-overflow: ellipsis; white-space: nowrap; }
.section-outline > button:hover, .section-outline > button.active { background: var(--pa-surface); color: var(--pa-text); }
.section-title-input { width: calc(100% - 12px); height: 28px; margin: 10px 6px 0; padding: 0 7px; border: 1px solid var(--pa-border); border-radius: 4px; background: var(--pa-surface); color: var(--pa-text); font: inherit; font-size: 10px; }
.document-canvas { width: min(760px, calc(100% - 32px)); min-height: 590px; margin: 22px auto 40px; padding: 54px 64px 80px; border: 1px solid var(--pa-border); background: white; box-shadow: var(--pa-shadow-sm); }
.document-title { width: 100%; margin-bottom: 30px; padding: 0 0 14px; border: 0; border-bottom: 1px solid var(--pa-border); outline: 0; color: var(--pa-text); font: inherit; font-size: 23px; font-weight: 650; }
.document-editor { min-height: 460px; color: #27231f; font-size: 15px; line-height: 1.85; outline: none; }
.document-editor:empty::before { color: var(--pa-muted); content: attr(data-placeholder); }
.document-editor :deep(h1) { font-size: 21px; }.document-editor :deep(h2) { font-size: 18px; }.document-editor :deep(h3) { font-size: 16px; }
.reference-panel { border-left: 1px solid var(--pa-border); background: var(--pa-surface); overflow: hidden; }
.reference-panel > header { display: flex; align-items: center; justify-content: space-between; padding: 10px; border-bottom: 1px solid var(--pa-border); }
.reference-panel header div { display: flex; gap: 7px; font-size: 11px; }.reference-panel header span { color: var(--pa-muted); }
.reference-panel header button { border: 0; background: transparent; cursor: pointer; }
.reference-panel > input { width: calc(100% - 16px); height: 30px; margin: 8px; padding: 0 8px; border: 1px solid var(--pa-border); border-radius: 5px; font: inherit; font-size: 11px; }
.reference-list { max-height: 570px; overflow-y: auto; }
.reference-list article { padding: 9px 10px; border-top: 1px solid var(--pa-border); }
.reference-title { padding: 0; border: 0; background: transparent; color: var(--pa-text); cursor: pointer; font: inherit; font-size: 11px; font-weight: 650; line-height: 1.4; text-align: left; }
.reference-list p { margin: 3px 0 6px; color: var(--pa-muted); font-size: 10px; line-height: 1.35; }
.reference-list article div { display: flex; gap: 8px; }.reference-list article div button { padding: 0; border: 0; background: transparent; color: var(--pa-primary); cursor: pointer; font: inherit; font-size: 10px; }
.reference-empty { padding: 16px; color: var(--pa-muted); font-size: 11px; }
.paper-peek { position: absolute; top: 48px; right: 8px; bottom: 8px; z-index: 3; display: grid; grid-template-rows: auto auto 1fr; width: min(360px, calc(100% - 16px)); border: 1px solid var(--pa-border); border-radius: 7px; background: var(--pa-surface); box-shadow: var(--pa-shadow-md); overflow: hidden; }
.paper-peek > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; padding: 10px 12px; border-bottom: 1px solid var(--pa-border); }.paper-peek header div { min-width: 0; }.paper-peek header strong, .paper-peek header span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }.paper-peek header strong { font-size: 11px; }.paper-peek header span { margin-top: 2px; color: var(--pa-muted); font-size: 9px; }.paper-peek header button { border: 0; background: transparent; cursor: pointer; }
.paper-peek-tools { display: grid; grid-template-columns: 1fr auto; gap: 6px; padding: 7px; border-bottom: 1px solid var(--pa-border); }.paper-peek-tools input { min-width: 0; height: 28px; padding: 0 7px; border: 1px solid var(--pa-border); border-radius: 4px; font-size: 10px; }.paper-peek-tools button { border: 1px solid var(--pa-border); border-radius: 4px; background: var(--pa-surface-soft); font-size: 10px; cursor: pointer; }
.paper-peek-body { padding: 10px 12px; overflow-y: auto; }.paper-peek-body > button { display: block; width: 100%; padding: 9px 0; border: 0; border-bottom: 1px solid var(--pa-border); background: transparent; color: var(--pa-text); cursor: pointer; text-align: left; }.paper-peek-body > button.active { background: var(--pa-surface-soft); }.paper-peek-body strong { font-size: 11px; }.paper-peek-body span { margin-left: 6px; color: var(--pa-muted); font-size: 9px; }.paper-peek-body p { margin: 5px 0 0; color: var(--pa-text); font-size: 11px; line-height: 1.65; white-space: pre-wrap; }
@media (max-width: 900px) { .studio-layout, .studio-layout.references-closed { grid-template-columns: 120px minmax(0, 1fr); }.reference-panel { display: none; }.document-canvas { width: calc(100% - 20px); margin: 10px; padding: 36px 32px 60px; } }
@media (max-width: 640px) { .studio-toolbar { align-items: flex-start; flex-direction: column; }.studio-layout, .studio-layout.references-closed { grid-template-columns: 1fr; }.section-outline { display: flex; gap: 4px; border-right: 0; border-bottom: 1px solid var(--pa-border); overflow-x: auto; }.section-outline header { flex: none; }.section-outline > button { width: auto; flex: none; }.document-canvas { padding: 28px 20px 48px; }.document-editor { font-size: 16px; }.paper-peek { top: 86px; } }
</style>

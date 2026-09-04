<template>
  <section class="topic-explorer" aria-labelledby="external-search-title">
    <header>
      <div><h3 id="external-search-title">查找外部论文</h3><p>直接搜索 arXiv，查看摘要与作者后再决定是否导入。</p></div>
      <span v-if="papers.length">{{ papers.length }} 篇结果</span>
    </header>
    <form class="search-row" @submit.prevent="search">
      <label for="external-paper-query" class="pa-sr-only">论文关键词</label>
      <a-input id="external-paper-query" v-model="query" allow-clear placeholder="输入研究问题、方法或中英文关键词" />
      <a-button html-type="submit" type="primary" :loading="searching" :disabled="query.trim().length < 2">搜索论文</a-button>
    </form>
    <div v-if="error" class="pa-form-error" role="alert">{{ error }}</div>

    <div v-if="searching" class="result-skeleton" aria-label="正在搜索论文">
      <span v-for="i in 4" :key="i"></span>
    </div>
    <div v-else-if="papers.length" class="paper-results">
      <article v-for="paper in papers" :key="paper.arxiv_id" class="candidate-row">
        <label class="candidate-select" :aria-label="`选择 ${paper.title}`">
          <input v-model="selected" type="checkbox" :value="paper.arxiv_id" />
        </label>
        <div class="candidate-main">
          <div class="candidate-title-row">
            <a :href="paper.arxiv_url" target="_blank" rel="noopener noreferrer">{{ paper.title }}</a>
            <span>{{ paper.published?.slice(0, 4) || '年份未知' }}</span>
          </div>
          <p class="candidate-authors">{{ paper.authors?.join(', ') || '作者信息缺失' }}</p>
          <p class="candidate-abstract" :class="{ expanded: expanded.has(paper.arxiv_id) }">{{ paper.abstract || 'arXiv 未返回摘要。' }}</p>
          <div class="candidate-actions">
            <button type="button" @click="toggleAbstract(paper.arxiv_id)">{{ expanded.has(paper.arxiv_id) ? '收起摘要' : '展开摘要' }}</button>
            <a :href="paper.pdf_url" target="_blank" rel="noopener noreferrer">查看 PDF</a>
            <span>arXiv:{{ paper.arxiv_id }}</span>
          </div>
        </div>
        <a-button size="mini" :loading="importing.has(paper.arxiv_id)" @click="importOne(paper)">导入</a-button>
      </article>
      <footer class="result-footer">
        <span>已选择 {{ selected.length }} 篇</span>
        <a-button size="small" type="primary" :disabled="!selected.length" :loading="batchImporting" @click="importSelected">导入所选论文</a-button>
      </footer>
    </div>
    <div v-else-if="searched" class="search-empty">没有找到结果，尝试使用英文方法名、任务名或更具体的关键词。</div>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Message } from '@arco-design/web-vue'
import { importExternalPaper, searchExternalPapers, type ExternalPaperCandidate } from '@/api/projects'

const props = defineProps<{ projectId: string; initialQuery?: string }>()
const emit = defineEmits<{ imported: [] }>()
const query = ref(props.initialQuery || '')
const papers = ref<ExternalPaperCandidate[]>([])
const selected = ref<string[]>([])
const expanded = ref(new Set<string>())
const importing = ref(new Set<string>())
const searching = ref(false)
const searched = ref(false)
const batchImporting = ref(false)
const error = ref('')

watch(() => props.initialQuery, value => {
  if (value && !searching.value) query.value = value
})

const search = async () => {
  if (query.value.trim().length < 2) return
  searching.value = true
  searched.value = true
  error.value = ''
  selected.value = []
  try {
    const result = await searchExternalPapers(props.projectId, query.value.trim(), 10)
    papers.value = result.papers || []
  } catch (e: any) {
    error.value = e?.response?.data?.detail || '外部论文搜索失败，请稍后重试。'
  } finally {
    searching.value = false
  }
}

const toggleAbstract = (id: string) => {
  const next = new Set(expanded.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expanded.value = next
}
const importOne = async (paper: ExternalPaperCandidate, quiet = false) => {
  const next = new Set(importing.value)
  next.add(paper.arxiv_id)
  importing.value = next
  try {
    await importExternalPaper(props.projectId, { arxiv_id: paper.arxiv_id, role: 'related', reading_priority: 3 })
    if (!quiet) Message.success(`《${paper.title}》已进入导入队列`)
    emit('imported')
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || `导入 ${paper.arxiv_id} 失败`)
  } finally {
    const done = new Set(importing.value)
    done.delete(paper.arxiv_id)
    importing.value = done
  }
}
const importSelected = async () => {
  batchImporting.value = true
  const targets = papers.value.filter(paper => selected.value.includes(paper.arxiv_id))
  for (const paper of targets) await importOne(paper, true)
  batchImporting.value = false
  selected.value = []
  Message.success(`${targets.length} 篇论文已提交导入`)
}
</script>

<style scoped>
.topic-explorer { margin-bottom: 20px; }
.topic-explorer > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 10px; }
.topic-explorer h3 { margin: 0 0 3px; font-size: 15px; }
.topic-explorer header p { margin: 0; color: var(--pa-muted); font-size: 12px; }
.topic-explorer header > span { color: var(--pa-muted); font-size: 12px; }
.search-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 8px; }
.pa-form-error { margin-top: 8px; font-size: 12px; }
.result-skeleton { display: grid; gap: 1px; margin-top: 12px; background: var(--pa-border); }
.result-skeleton span { height: 92px; background: var(--pa-surface-soft); }
.paper-results { margin-top: 12px; border: 1px solid var(--pa-border); border-radius: 8px; overflow: hidden; }
.candidate-row { display: grid; grid-template-columns: 24px minmax(0, 1fr) auto; gap: 10px; align-items: start; padding: 12px; border-bottom: 1px solid var(--pa-border); }
.candidate-row:last-of-type { border-bottom: 0; }
.candidate-select { display: grid; min-height: 32px; place-items: center; }
.candidate-title-row { display: flex; align-items: baseline; gap: 8px; }
.candidate-title-row a { color: var(--pa-text); font-size: 13px; font-weight: 650; line-height: 1.35; text-decoration: none; }
.candidate-title-row a:hover { color: var(--pa-primary); text-decoration: underline; }
.candidate-title-row span, .candidate-authors { color: var(--pa-muted); font-size: 11px; }
.candidate-authors { margin: 3px 0 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.candidate-abstract { display: -webkit-box; margin: 0; overflow: hidden; color: var(--pa-text); font-size: 12px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.candidate-abstract.expanded { display: block; }
.candidate-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; margin-top: 7px; color: var(--pa-muted); font-size: 11px; }
.candidate-actions button, .candidate-actions a { padding: 0; border: 0; background: transparent; color: var(--pa-primary); cursor: pointer; font: inherit; text-decoration: none; }
.candidate-actions button:focus-visible, .candidate-actions a:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.result-footer { display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 9px 12px; background: var(--pa-surface-soft); font-size: 12px; }
.search-empty { margin-top: 12px; padding: 20px; border: 1px dashed var(--pa-border); color: var(--pa-muted); font-size: 12px; text-align: center; }
@media (max-width: 700px) {
  .candidate-row { grid-template-columns: 24px minmax(0, 1fr); }
  .candidate-row > .arco-btn { grid-column: 2; justify-self: start; }
  .search-row { grid-template-columns: 1fr; }
  .search-row .arco-btn { min-height: 44px; }
}
</style>

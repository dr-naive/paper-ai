<template>
  <section v-if="status === 'completed'" class="results-section" aria-labelledby="results-title">
    <header class="results-header">
      <div>
        <p class="section-label">Search results</p>
        <h2 id="results-title">找到 {{ resultCount }} 篇符合当前条件的论文</h2>
      </div>
      <div class="result-filters" role="tablist" aria-label="结果筛选">
        <button type="button" role="tab" :aria-selected="filter === 'all'" :class="{ active: filter === 'all' }" @click="$emit('update:filter', 'all')">全部 {{ resultCount }}</button>
        <button type="button" role="tab" :aria-selected="filter === 'favorites'" :class="{ active: filter === 'favorites' }" @click="$emit('update:filter', 'favorites')">已收藏 {{ favoriteCount }}</button>
      </div>
    </header>

    <p v-if="actionError" class="action-error" role="alert">{{ actionError }}</p>

    <div v-if="!resultCount" class="results-empty">
      <h3>没有找到符合当前条件的论文。</h3>
      <p>可以修改年份、语言、领域或文献类型，也可以重新讨论研究需求。</p>
      <div class="empty-actions">
        <a-button type="secondary" @click="$emit('modify')">修改搜索条件</a-button>
        <a-button type="text" @click="$emit('reopen')">重新讨论需求</a-button>
      </div>
    </div>
    <div v-else-if="!papers.length" class="results-empty">
      <h3>当前筛选下还没有已收藏的论文。</h3>
      <p>切换到“全部”查看本次检索结果，再收藏你想保留的论文。</p>
      <a-button type="secondary" @click="$emit('update:filter', 'all')">查看全部结果</a-button>
    </div>
    <div v-else class="paper-grid">
      <PaperResultCard
        v-for="paper in papers"
        :key="paper.result_id"
        :paper="paper"
        :favorite-pending="Boolean(favoritePending[paper.result_id])"
        :import-state="importStates[paper.result_id] || 'idle'"
        :import-message="importMessages[paper.result_id] || ''"
        @details="$emit('details', $event)"
        @toggle-favorite="$emit('toggle-favorite', $event)"
        @download="$emit('download', $event)"
        @import="$emit('import', $event)"
      />
    </div>
  </section>

  <section v-else-if="status === 'failed'" class="results-empty results-error" aria-live="polite">
    <h3>论文搜索服务暂时没有响应。</h3>
    <p>{{ errorMessage || '请稍后重新搜索，或调整检索条件。' }}</p>
    <a-button type="secondary" @click="$emit('retry')">重新搜索</a-button>
  </section>
</template>

<script setup lang="ts">
import type { PaperSearchResult } from '@/api/discovery'
import type { FavoriteFilter, ImportState } from '@/stores/discover'
import PaperResultCard from './PaperResultCard.vue'

defineProps<{
  status: string
  resultCount: number
  favoriteCount: number
  filter: FavoriteFilter
  papers: PaperSearchResult[]
  favoritePending: Record<string, boolean>
  importStates: Record<string, ImportState>
  importMessages: Record<string, string>
  actionError?: string
  errorMessage?: string
}>()

defineEmits<{
  'update:filter': [filter: FavoriteFilter]
  details: [paper: PaperSearchResult]
  'toggle-favorite': [paper: PaperSearchResult]
  download: [paper: PaperSearchResult]
  import: [paper: PaperSearchResult]
  modify: []
  reopen: []
  retry: []
}>()
</script>

<style scoped>
.results-section { min-width: 0; }
.results-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 14px; }
.section-label { margin: 0 0 6px; color: var(--pa-primary-hover); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.results-header h2 { margin: 0; color: var(--pa-ink); font-size: 20px; line-height: 1.35; }
.result-filters { display: flex; gap: 4px; }
.result-filters button { padding: 6px 9px; border: 1px solid transparent; border-radius: 5px; background: transparent; color: var(--pa-muted); cursor: pointer; font: inherit; font-size: 12px; }
.result-filters button:hover, .result-filters button.active { border-color: var(--pa-border); background: var(--pa-surface); color: var(--pa-primary-hover); }
.result-filters button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.paper-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px 18px; }
.results-empty { padding: 52px 24px; border: 1px dashed var(--pa-border); border-radius: 10px; background: var(--pa-surface); text-align: center; }
.results-empty h3 { margin: 0; color: var(--pa-ink); font-size: 18px; }
.results-empty p { max-width: 54ch; margin: 10px auto 20px; color: var(--pa-muted); font-size: 13px; line-height: 1.6; }
.empty-actions { display: flex; justify-content: center; gap: 8px; }
.results-error { border-color: oklch(0.86 0.05 28); background: oklch(0.98 0.012 28); }
.action-error { margin: 0 0 12px; color: var(--pa-danger); font-size: 12px; }
@media (max-width: 900px) { .paper-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) { .results-header { align-items: flex-start; flex-direction: column; gap: 10px; } .empty-actions { align-items: stretch; flex-direction: column; } }
</style>

<template>
  <article class="paper-card">
    <header class="paper-card__header">
      <h3 class="paper-title" :title="paper.title">
        <a v-if="paper.paper_url" :href="paper.paper_url" target="_blank" rel="noopener noreferrer">{{ paper.title }}</a>
        <span v-else>{{ paper.title }}</span>
      </h3>
      <p class="paper-meta">{{ authorLabel }}<span v-if="paper.year"> · {{ paper.year }}</span><span v-if="paper.venue"> · {{ paper.venue }}</span></p>
    </header>

    <section class="paper-abstract" aria-label="论文摘要">
      <p :class="{ 'is-expanded': expanded }">{{ paper.abstract || '暂无摘要' }}</p>
      <button v-if="canExpand" type="button" class="expand-button" :aria-expanded="expanded" @click="expanded = !expanded">{{ expanded ? '收起' : '展开' }}</button>
    </section>

    <section v-if="paper.recommendation_reason" class="recommendation" aria-label="推荐理由">
      <span>为什么推荐</span>
      <p>{{ paper.recommendation_reason }}</p>
    </section>

    <div class="paper-chips" aria-label="论文元数据">
      <span v-if="paper.year" class="metadata-chip">{{ paper.year }}</span>
      <span v-if="paper.language" class="metadata-chip">{{ displayLanguage }}</span>
      <span v-if="paper.publication_type" class="metadata-chip">{{ displayPublicationType }}</span>
      <span v-if="paper.citation_count !== null" class="metadata-chip">被引 {{ paper.citation_count }}</span>
      <span v-for="field in paper.fields.slice(0, 3)" :key="field" class="metadata-chip">{{ field }}</span>
    </div>

    <footer class="paper-actions" aria-label="论文操作">
      <div class="paper-actions__secondary">
        <a-button type="text" size="small" class="action-button" @click="$emit('details', paper)">详情</a-button>
        <a-button type="text" size="small" class="action-button" :loading="favoritePending" :disabled="favoritePending" @click="$emit('toggle-favorite', paper)"><IconStar aria-hidden="true" />{{ paper.is_favorite ? '已收藏' : '收藏' }}</a-button>
        <a-tooltip v-if="!paper.download_available" content="暂无可用下载链接">
          <span class="action-tooltip"><a-button type="text" size="small" class="action-button" disabled aria-label="暂无可用下载链接">下载</a-button></span>
        </a-tooltip>
        <a-button v-else type="text" size="small" class="action-button" @click="$emit('download', paper)">下载</a-button>
      </div>
      <a-tooltip v-if="!paper.import_available" content="暂无可导入的论文全文">
        <span class="action-tooltip paper-actions__import"><a-button type="secondary" size="small" class="action-button" disabled aria-label="暂无可导入的论文全文">导入项目</a-button></span>
      </a-tooltip>
      <a-button v-else :type="importState === 'imported' ? 'secondary' : 'primary'" size="small" class="action-button paper-actions__import" :loading="importState === 'importing'" :disabled="importState === 'importing' || importState === 'imported'" @click="$emit('import', paper)">{{ importLabel === '导入' ? '导入项目' : importLabel }}</a-button>
    </footer>
    <p v-if="importMessage" class="import-message" role="status">{{ importMessage }}</p>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { IconStar } from '@arco-design/web-vue/es/icon'
import type { PaperSearchResult } from '@/api/discovery'
import type { ImportState } from '@/stores/discover'

const props = withDefaults(defineProps<{
  paper: PaperSearchResult
  favoritePending?: boolean
  importState?: ImportState
  importMessage?: string
}>(), {
  favoritePending: false,
  importState: 'idle',
  importMessage: '',
})

defineEmits<{
  details: [paper: PaperSearchResult]
  'toggle-favorite': [paper: PaperSearchResult]
  download: [paper: PaperSearchResult]
  import: [paper: PaperSearchResult]
}>()

const expanded = ref(false)
const abstractText = computed(() => props.paper.abstract || '')
const canExpand = computed(() => abstractText.value.length > 240)
const authorLabel = computed(() => props.paper.authors.length ? props.paper.authors.join(', ') : '作者信息待补充')
const displayLanguage = computed(() => ({ en: '英文', zh: '中文', ja: '日文', ko: '韩文' }[props.paper.language || ''] || props.paper.language || '语言未知'))
const displayPublicationType = computed(() => ({ JournalArticle: '期刊', Conference: '会议', Review: '综述', Dataset: '数据集' }[props.paper.publication_type || ''] || props.paper.publication_type || '文献'))
const importLabel = computed(() => props.importState === 'importing' ? '正在导入…' : props.importState === 'imported' ? '已导入' : '导入')
</script>

<style scoped>
.paper-card { display: flex; min-height: 330px; flex-direction: column; padding: 18px; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface); transition: border-color 180ms ease-out, box-shadow 180ms ease-out; }
.paper-card:hover { border-color: color-mix(in srgb, var(--pa-primary) 38%, var(--pa-border)); box-shadow: var(--pa-shadow-sm); }
.paper-card__header { min-width: 0; }
.paper-title { display: -webkit-box; margin: 0; overflow: hidden; color: var(--pa-ink); font-size: 16px; font-weight: 650; line-height: 1.4; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
.paper-title a { color: inherit; text-decoration: none; }
.paper-title a:hover { color: var(--pa-primary-hover); text-decoration: underline; }
.paper-meta { margin: 7px 0 0; color: var(--pa-muted); font-size: 12px; line-height: 1.5; }
.paper-abstract { position: relative; margin-top: 16px; }
.paper-abstract p { display: -webkit-box; margin: 0; overflow: hidden; color: var(--pa-text); font-size: 13px; line-height: 1.65; -webkit-box-orient: vertical; -webkit-line-clamp: 4; }
.paper-abstract p.is-expanded { display: block; overflow: visible; }
.expand-button { margin-top: 5px; padding: 0; border: 0; background: transparent; color: var(--pa-primary-hover); cursor: pointer; font: inherit; font-size: 12px; }
.expand-button:hover { text-decoration: underline; }
.expand-button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.recommendation { margin-top: 14px; padding: 10px 12px; border: 1px solid color-mix(in srgb, var(--pa-primary) 28%, var(--pa-border)); border-radius: var(--pa-radius-sm); background: var(--pa-surface-soft); }
.recommendation span { color: var(--pa-muted); font-size: 11px; font-weight: 650; }
.recommendation p { margin: 4px 0 0; color: var(--pa-text); font-size: 12px; line-height: 1.55; }
.paper-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: auto; padding-top: 18px; }
.metadata-chip { padding: 4px 7px; border-radius: 4px; background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 11px; line-height: 1.25; }
.paper-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--pa-border); }
.paper-actions__secondary { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.action-button { min-width: 66px; justify-content: center; }
.paper-actions__import { margin-left: auto; }
.action-tooltip { display: inline-flex; }
.import-message { margin: 8px 0 0; color: var(--pa-muted); font-size: 11px; line-height: 1.45; }
@media (max-width: 680px) { .paper-card { min-height: 0; padding: 17px; } .paper-actions { align-items: flex-start; gap: 6px 2px; } .paper-actions__secondary { width: 100%; } .paper-actions__import { margin-left: 0; } .action-button { min-width: 62px; } }
@media (prefers-reduced-motion: reduce) { .paper-card { transition: none; } }
</style>

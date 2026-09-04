<template>
  <a-drawer
    :visible="Boolean(paper)"
    title="论文详情"
    placement="right"
    :width="540"
    :footer="false"
    unmount-on-close
    @cancel="$emit('close')"
  >
    <template v-if="paper">
      <article class="detail-content">
        <h2>{{ paper.title }}</h2>
        <p class="detail-meta">{{ authorLabel }}<span v-if="paper.year"> · {{ paper.year }}</span><span v-if="paper.venue"> · {{ paper.venue }}</span></p>

        <div class="detail-actions" aria-label="论文操作">
          <div class="detail-actions__secondary">
            <a-button type="text" size="small" :loading="favoritePending" :disabled="favoritePending" @click="$emit('toggle-favorite', paper)"><IconStar aria-hidden="true" />{{ paper.is_favorite ? '已收藏' : '收藏' }}</a-button>
            <a-tooltip v-if="!paper.download_available" content="暂无可用下载链接">
              <span class="action-tooltip"><a-button type="text" size="small" disabled aria-label="暂无可用下载链接">下载</a-button></span>
            </a-tooltip>
            <a-button v-else type="text" size="small" @click="$emit('download', paper)">下载</a-button>
          </div>
          <a-tooltip v-if="!paper.import_available" content="暂无可导入的论文全文">
            <span class="action-tooltip detail-actions__import"><a-button type="secondary" size="small" disabled aria-label="暂无可导入的论文全文">导入项目</a-button></span>
          </a-tooltip>
          <a-button v-else :type="importState === 'imported' ? 'secondary' : 'primary'" size="small" class="detail-actions__import" :loading="importState === 'importing'" :disabled="importState === 'importing' || importState === 'imported'" @click="$emit('import', paper)">{{ importLabel === '导入' ? '导入项目' : importLabel }}</a-button>
        </div>
        <p v-if="importMessage" class="import-message" role="status">{{ importMessage }}</p>

        <section class="detail-section">
          <h3>摘要</h3>
          <p class="full-abstract">{{ paper.abstract || '暂无摘要' }}</p>
        </section>
        <section v-if="paper.recommendation_reason" class="detail-section">
          <h3>为什么推荐</h3>
          <p>{{ paper.recommendation_reason }}</p>
        </section>
        <section class="detail-section">
          <h3>基本信息</h3>
          <dl class="metadata-list">
            <div v-if="paper.doi"><dt>DOI</dt><dd>{{ paper.doi }}</dd></div>
            <div v-if="paper.source"><dt>来源</dt><dd>{{ paper.source }}</dd></div>
            <div v-if="paper.language"><dt>语言</dt><dd>{{ paper.language }}</dd></div>
            <div v-if="paper.publication_type"><dt>文献类型</dt><dd>{{ paper.publication_type }}</dd></div>
            <div v-if="paper.citation_count !== null"><dt>被引次数</dt><dd>{{ paper.citation_count }}</dd></div>
            <div v-if="paper.fields.length"><dt>学科领域</dt><dd>{{ paper.fields.join('、') }}</dd></div>
          </dl>
        </section>
        <a v-if="paper.paper_url" class="original-link" :href="paper.paper_url" target="_blank" rel="noopener noreferrer">打开原始页面 <IconLaunch aria-hidden="true" /></a>
      </article>
    </template>
  </a-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { IconLaunch, IconStar } from '@arco-design/web-vue/es/icon'
import type { PaperSearchResult } from '@/api/discovery'
import type { ImportState } from '@/stores/discover'

const props = withDefaults(defineProps<{
  paper: PaperSearchResult | null
  favoritePending?: boolean
  importState?: ImportState
  importMessage?: string
}>(), {
  favoritePending: false,
  importState: 'idle',
  importMessage: '',
})

defineEmits<{
  close: []
  'toggle-favorite': [paper: PaperSearchResult]
  download: [paper: PaperSearchResult]
  import: [paper: PaperSearchResult]
}>()

const authorLabel = computed(() => props.paper?.authors.length ? props.paper.authors.join(', ') : '作者信息待补充')
const importLabel = computed(() => props.importState === 'importing' ? '正在导入…' : props.importState === 'imported' ? '已导入' : '导入')
</script>

<style scoped>
.detail-content { padding-bottom: 28px; }
.detail-content h2 { margin: 0; color: var(--pa-ink); font-size: 21px; line-height: 1.4; }
.detail-meta { margin: 8px 0 0; color: var(--pa-muted); font-size: 13px; line-height: 1.6; }
.detail-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
.detail-actions__secondary { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; }
.detail-actions__import { margin-left: auto; }
.action-tooltip { display: inline-flex; }
.import-message { margin: 9px 0 0; color: var(--pa-muted); font-size: 12px; line-height: 1.5; }
.detail-section { margin-top: 25px; padding-top: 18px; border-top: 1px solid var(--pa-border); }
.detail-section h3 { margin: 0 0 9px; color: var(--pa-ink); font-size: 14px; }
.detail-section p { margin: 0; color: var(--pa-text); font-size: 13px; line-height: 1.7; }
.detail-section .full-abstract { white-space: pre-wrap; font-size: 14px; line-height: 1.7; }
.metadata-list { display: grid; gap: 9px; margin: 0; }
.metadata-list div { display: grid; grid-template-columns: 84px minmax(0, 1fr); gap: 12px; font-size: 12px; line-height: 1.5; }
.metadata-list dt { color: var(--pa-muted); }
.metadata-list dd { min-width: 0; margin: 0; overflow-wrap: anywhere; color: var(--pa-text); }
.original-link { display: inline-flex; gap: 6px; margin-top: 24px; color: var(--pa-primary-hover); font-size: 13px; font-weight: 650; text-decoration: none; }
.original-link:hover { text-decoration: underline; }
</style>

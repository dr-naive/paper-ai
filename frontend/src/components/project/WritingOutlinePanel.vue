<template>
  <aside class="outline-panel" :class="{ collapsed }" aria-label="文档与大纲">
    <header class="panel-heading">
      <button type="button" class="outline-toggle" :aria-label="collapsed ? '展开论文结构' : '收起论文结构'" :aria-expanded="!collapsed" @click="$emit('toggle')">
        <span aria-hidden="true">{{ collapsed ? '›' : '‹' }}</span>
        <strong v-if="!collapsed">文档</strong>
      </button>
      <a-button v-if="!collapsed" size="mini" @click="$emit('create-document')">新建文档</a-button>
    </header>
    <nav v-if="!collapsed" aria-label="写作文档">
      <button
        v-for="item in documents"
        :key="item.id"
        type="button"
        class="document-item"
        :class="{ active: item.id === activeDocumentId }"
        :aria-current="item.id === activeDocumentId ? 'page' : undefined"
        @click="$emit('open-document', item.id)"
      >
        <strong>{{ item.title }}</strong>
        <small>{{ item.status }} · {{ formatTime(item.updated_at) }}</small>
      </button>
    </nav>
    <p v-if="!collapsed && !documents.length && !loading" class="panel-empty">还没有正式写作文档。</p>

    <section v-if="!collapsed && activeDocumentId" class="outline-section">
      <header class="panel-heading">
        <strong>大纲</strong>
        <a-button size="mini" @click="$emit('add-section')">添加章节</a-button>
      </header>
      <nav v-if="outline.length" aria-label="文档大纲">
        <button
          v-for="heading in outline"
          :key="heading.pos"
          type="button"
          class="outline-item"
          :class="{ active: heading.text === currentHeading }"
          :style="{ paddingLeft: `${10 + (heading.level - 1) * 12}px` }"
          :aria-current="heading.text === currentHeading ? 'location' : undefined"
          @click="$emit('focus-heading', heading.pos)"
        >{{ heading.text }}</button>
      </nav>
      <p v-else class="panel-empty">使用“添加章节”建立论文结构。</p>
    </section>
  </aside>
</template>

<script setup lang="ts">
import type { WritingDocument } from '@/api/documents'
import type { WritingOutlineItem } from '@/utils/writingContext'

defineProps<{
  documents: WritingDocument[]
  activeDocumentId?: string
  outline: WritingOutlineItem[]
  currentHeading: string
  loading: boolean
  collapsed: boolean
}>()
defineEmits<{
  toggle: []
  'create-document': []
  'open-document': [id: string]
  'add-section': []
  'focus-heading': [pos: number]
}>()

const formatTime = (value: string) => new Date(value).toLocaleDateString('zh-CN')
</script>

<style scoped>
.outline-panel { min-width: 0; padding: 14px 12px; overflow: auto; border-right: 1px solid var(--pa-border); background: var(--pa-surface-soft); }
.outline-panel.collapsed { padding: 10px 4px; }
.panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.outline-toggle { display: flex; align-items: center; gap: 6px; min-width: 44px; min-height: 44px; padding: 6px; border: 0; border-radius: 6px; background: transparent; color: var(--pa-text); cursor: pointer; text-align: left; }
.outline-toggle:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.collapsed .panel-heading { justify-content: center; }
.collapsed .outline-toggle { justify-content: center; }
.document-item,.outline-item { width: 100%; border: 0; border-radius: 6px; background: transparent; color: var(--pa-text); cursor: pointer; text-align: left; }
.document-item { display: flex; flex-direction: column; gap: 3px; min-height: 44px; margin-top: 8px; padding: 8px; }
.document-item.active,.outline-item.active { background: var(--pa-primary-soft); color: var(--pa-primary-hover); }
.document-item small,.panel-empty { color: var(--pa-muted); font-size: 11px; }
.outline-section { margin-top: 20px; padding-top: 14px; border-top: 1px solid var(--pa-border); }
.outline-item { display: block; min-height: 36px; margin-top: 2px; padding-block: 8px; font-size: 12px; }
.document-item:focus-visible,.outline-item:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.panel-empty { margin-top: 10px; line-height: 1.5; }
</style>

<template>
  <aside class="paper-outline" :class="{ collapsed }" aria-label="论文目录">
    <template v-if="collapsed">
      <button
        type="button"
        class="outline-rail-button"
        aria-label="展开论文目录"
        title="展开目录"
        @click="$emit('update:collapsed', false)"
      >
        <span class="rail-icon" aria-hidden="true">☰</span>
        <span class="rail-label">目录</span>
      </button>
    </template>

    <template v-else>
      <header class="outline-header">
        <div>
          <strong>论文目录</strong>
          <span>{{ flatSections.length }} 个章节</span>
        </div>
        <div class="outline-actions">
          <button
            type="button"
            class="outline-refresh-button"
            :disabled="refreshing"
            aria-label="重新抽取论文目录"
            title="重新抽取目录"
            @click="$emit('refresh')"
          >
            <span :class="{ spinning: refreshing }" aria-hidden="true">↻</span>
          </button>
          <button
            type="button"
            class="outline-collapse-button"
            aria-label="收起论文目录"
            title="收起目录"
            @click="$emit('update:collapsed', true)"
          >
            ‹
          </button>
        </div>
      </header>

      <nav class="outline-scroll" aria-label="章节导航">
        <div v-if="loading" class="outline-skeleton" aria-label="正在加载目录">
          <span v-for="index in 7" :key="index"></span>
        </div>
        <div v-else-if="!tree.length" class="outline-empty">
          <strong>暂未识别到目录</strong>
          <span>仍可使用 PDF 页码导航</span>
        </div>
        <ul v-else class="outline-tree">
          <PaperOutlineNode
            v-for="node in tree"
            :key="node.id"
            :node="node"
            :active-id="activeId"
            :expanded-ids="expandedIds"
            @navigate="handleNavigate"
            @toggle="toggleNode"
          />
        </ul>
      </nav>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PaperOutlineNode, { type OutlineNode } from './PaperOutlineNode.vue'

interface PaperSection {
  id?: string
  title?: string
  section_title?: string
  start_page?: number | string
  order_index?: number
}

const props = defineProps<{
  sections: PaperSection[]
  currentPage: number
  collapsed: boolean
  loading?: boolean
  refreshing?: boolean
}>()

const emit = defineEmits<{
  navigate: [section: OutlineNode]
  refresh: []
  'update:collapsed': [value: boolean]
}>()

const expandedIds = ref(new Set<string>())

const sectionLevel = (title: string) => {
  const numbered = title.match(/^\s*(\d+(?:\.\d+)*)[.)、]?\s+/)
  if (numbered) return Math.min(4, numbered[1].split('.').length)
  const appendix = title.match(/^\s*([A-Z](?:\.\d+)*)[.)、]?\s+/i)
  if (appendix) return Math.min(4, appendix[1].split('.').length)
  if (/^\s*第[一二三四五六七八九十百\d]+章/.test(title)) return 1
  if (/^\s*第[一二三四五六七八九十百\d]+节/.test(title)) return 2
  if (/^\s*[IVXLC]+[.)]\s+/i.test(title)) return 1
  return 1
}

const sectionNumber = (title: string) => (
  title.match(/^\s*((?:\d+|[A-Z])(?:\.\d+)*)[.)、]?(?:\s+|$)/i)?.[1].toUpperCase() || ''
)

const flatSections = computed(() => (
  (props.sections || [])
    .map((section, index) => {
      const title = String(section.section_title || section.title || `第 ${index + 1} 节`).trim()
      const page = Number(section.start_page)
      return {
        id: String(section.id || `${index}:${title}`),
        title,
        startPage: Number.isFinite(page) && page > 0 ? Math.floor(page) : 1,
        level: sectionLevel(title),
        sectionNumber: sectionNumber(title),
        orderIndex: Number(section.order_index ?? index)
      }
    })
    .sort((a, b) => a.orderIndex - b.orderIndex)
))

const tree = computed<OutlineNode[]>(() => {
  const roots: OutlineNode[] = []
  const stack: OutlineNode[] = []

  for (const section of flatSections.value) {
    const node: OutlineNode = { ...section, children: [] }
    while (stack.length && stack[stack.length - 1].level >= node.level) stack.pop()

    const parent = stack[stack.length - 1]
    const parentNumber = parent?.sectionNumber
    const belongsToParent = Boolean(
      parent
      && parentNumber
      && node.sectionNumber?.startsWith(`${parentNumber}.`)
    )

    if (belongsToParent) {
      node.level = Math.min(node.level, stack[stack.length - 1].level + 1)
      stack[stack.length - 1].children.push(node)
    } else {
      node.level = 1
      roots.push(node)
    }
    stack.push(node)
  }

  return roots
})

const allNodeIds = (nodes: OutlineNode[]): string[] => (
  nodes.flatMap(node => [node.id, ...allNodeIds(node.children)])
)

watch(tree, nodes => {
  if (expandedIds.value.size === 0) {
    expandedIds.value = new Set(allNodeIds(nodes))
  }
}, { immediate: true })

const activeId = computed(() => {
  const candidates = flatSections.value.filter(section => section.startPage <= props.currentPage)
  return candidates[candidates.length - 1]?.id || flatSections.value[0]?.id || ''
})

const toggleNode = (id: string) => {
  const next = new Set(expandedIds.value)
  next.has(id) ? next.delete(id) : next.add(id)
  expandedIds.value = next
}

const handleNavigate = (section: OutlineNode) => {
  emit('navigate', section)
}
</script>

<style scoped>
.paper-outline {
  width: 208px;
  min-width: 208px;
  height: 100%;
  border-right: 1px solid var(--pa-border);
  background: var(--pa-surface);
  overflow: hidden;
  transition: width 0.2s cubic-bezier(0.22, 1, 0.36, 1), min-width 0.2s cubic-bezier(0.22, 1, 0.36, 1);
}

.paper-outline.collapsed {
  width: 44px;
  min-width: 44px;
  background: var(--pa-surface-soft);
}

.outline-header {
  display: flex;
  height: 50px;
  align-items: center;
  justify-content: space-between;
  padding: 0 8px 0 12px;
  border-bottom: 1px solid var(--pa-border);
}

.outline-header > div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.outline-header strong {
  color: var(--pa-ink);
  font-size: 12px;
  font-weight: 650;
}

.outline-header span {
  color: var(--pa-muted);
  font-size: 10px;
}

.outline-actions {
  display: flex !important;
  min-width: auto !important;
  flex-direction: row !important;
  gap: 0 !important;
}

.outline-collapse-button,
.outline-refresh-button {
  display: grid;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--pa-text);
  cursor: pointer;
}

.outline-collapse-button {
  font-size: 21px;
}

.outline-refresh-button {
  font-size: 16px;
}

.outline-collapse-button:hover,
.outline-refresh-button:hover:not(:disabled) {
  border-color: var(--pa-border);
  background: var(--pa-bg);
  color: var(--pa-primary);
}

.outline-refresh-button:disabled {
  cursor: wait;
  opacity: 0.55;
}

.spinning {
  animation: outline-spin 0.8s linear infinite;
}

@keyframes outline-spin {
  to { transform: rotate(360deg); }
}

.outline-rail-button {
  display: flex;
  width: 100%;
  height: 100%;
  align-items: center;
  padding-top: 14px;
  border: 0;
  background: transparent;
  color: var(--pa-text);
  cursor: pointer;
  flex-direction: column;
  gap: 9px;
}

.outline-rail-button:hover {
  background: var(--pa-primary-soft);
  color: var(--pa-primary);
}

.rail-icon {
  font-size: 17px;
  line-height: 1;
}

.rail-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  writing-mode: vertical-rl;
}

.outline-scroll {
  height: calc(100% - 50px);
  padding: 6px 5px 12px;
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-gutter: stable;
}

.outline-tree {
  margin: 0;
  padding: 0;
  list-style: none;
}

.outline-empty {
  display: flex;
  min-height: 180px;
  align-items: center;
  justify-content: center;
  padding: 20px;
  color: var(--pa-muted);
  text-align: center;
  flex-direction: column;
  gap: 5px;
}

.outline-empty strong {
  color: var(--pa-text);
  font-size: 12px;
}

.outline-empty span {
  font-size: 11px;
  line-height: 1.5;
}

.outline-skeleton {
  display: flex;
  padding: 8px;
  flex-direction: column;
  gap: 14px;
}

.outline-skeleton span {
  display: block;
  width: 82%;
  height: 11px;
  border-radius: 4px;
  background: var(--pa-surface-soft);
}

.outline-skeleton span:nth-child(2n) { width: 66%; margin-left: 18px; }
.outline-skeleton span:nth-child(3n) { width: 74%; margin-left: 34px; }

.outline-collapse-button:focus-visible,
.outline-refresh-button:focus-visible,
.outline-rail-button:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: -3px;
}

@media (max-width: 1100px) {
  .paper-outline {
    width: 196px;
    min-width: 196px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .paper-outline {
    transition: none;
  }

  .spinning {
    animation: none;
  }
}
</style>

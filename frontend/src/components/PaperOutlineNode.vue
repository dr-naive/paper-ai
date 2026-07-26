<template>
  <li class="outline-node">
    <div
      class="outline-row"
      :class="{ active: activeId === node.id }"
      :style="{ '--outline-depth': node.level - 1 }"
    >
      <button
        v-if="node.children.length"
        type="button"
        class="outline-disclosure"
        :aria-label="isExpanded ? `收起 ${node.title}` : `展开 ${node.title}`"
        :aria-expanded="isExpanded"
        @click.stop="$emit('toggle', node.id)"
      >
        <span aria-hidden="true">{{ isExpanded ? '⌄' : '›' }}</span>
      </button>
      <span v-else class="outline-disclosure-placeholder" aria-hidden="true"></span>

      <button
        type="button"
        class="outline-link"
        :title="`${node.title}，第 ${node.startPage} 页`"
        :aria-current="activeId === node.id ? 'location' : undefined"
        @click="$emit('navigate', node)"
      >
        <span class="outline-title">{{ node.title }}</span>
        <span class="outline-page">{{ node.startPage }}</span>
      </button>
    </div>

    <ul v-if="node.children.length && isExpanded" class="outline-children">
      <PaperOutlineNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :active-id="activeId"
        :expanded-ids="expandedIds"
        @navigate="$emit('navigate', $event)"
        @toggle="$emit('toggle', $event)"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface OutlineNode {
  id: string
  title: string
  startPage: number
  level: number
  sectionNumber?: string
  children: OutlineNode[]
}

const props = defineProps<{
  node: OutlineNode
  activeId: string
  expandedIds: Set<string>
}>()

defineEmits<{
  navigate: [node: OutlineNode]
  toggle: [id: string]
}>()

const isExpanded = computed(() => props.expandedIds.has(props.node.id))
</script>

<style scoped>
.outline-node,
.outline-children {
  margin: 0;
  padding: 0;
  list-style: none;
}

.outline-row {
  display: flex;
  min-height: 30px;
  align-items: center;
  padding-left: calc(3px + var(--outline-depth) * 10px);
  border-radius: 5px;
  color: var(--pa-text);
}

.outline-row:hover {
  background: var(--pa-surface-soft);
}

.outline-row.active {
  background: var(--pa-primary-soft);
  color: var(--pa-primary-hover);
}

.outline-disclosure,
.outline-disclosure-placeholder {
  display: grid;
  width: 22px;
  height: 28px;
  flex: 0 0 22px;
  place-items: center;
}

.outline-disclosure {
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--pa-muted);
  cursor: pointer;
  font-size: 15px;
  line-height: 1;
}

.outline-disclosure:hover {
  background: oklch(0.50 0.16 45 / 0.09);
  color: var(--pa-primary);
}

.outline-link {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 5px;
  align-self: stretch;
  padding: 4px 6px 4px 1px;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.outline-title {
  min-width: 0;
  flex: 1;
  overflow: hidden;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.outline-page {
  min-width: 17px;
  color: var(--pa-muted);
  font-size: 10px;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.outline-row.active .outline-title {
  font-weight: 650;
}

.outline-row.active .outline-page {
  color: var(--pa-primary);
}

.outline-disclosure:focus-visible,
.outline-link:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: -2px;
}
</style>

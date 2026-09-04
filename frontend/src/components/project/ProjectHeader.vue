<template>
  <ProductHeader :context="project.title" :show-brand="false" back-to="/projects" back-label="项目列表">
    <template #navigation>
      <nav class="project-tabs" aria-label="项目导航">
        <RouterLink
          v-for="tab in tabs"
          :key="tab.name"
          :to="{ name: tab.name, params: { projectId: project.id } }"
          class="project-tab"
          :class="{ 'is-active': route.name === tab.name }"
          :aria-current="route.name === tab.name ? 'page' : undefined"
        >
          {{ tab.label }}
        </RouterLink>
      </nav>
    </template>
    <span class="project-topic" :title="project.research_topic">{{ project.research_topic }}</span>
  </ProductHeader>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import type { ResearchProject } from '@/api/projects'
import ProductHeader from '@/components/ProductHeader.vue'

defineProps<{ project: ResearchProject }>()
const route = useRoute()
const tabs = [
  { name: 'ProjectOverview', label: '概览' },
  { name: 'ProjectDiscover', label: '文献发现' },
  { name: 'ProjectPapers', label: '项目论文' },
  { name: 'ProjectWriting', label: '写作' },
] as const
</script>

<style scoped>
.project-tabs {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-left: 4px;
}

.project-tab {
  display: inline-flex;
  min-height: 32px;
  align-items: center;
  padding: 0 9px;
  border-radius: 6px;
  color: var(--pa-muted);
  font-size: 12px;
  text-decoration: none;
  white-space: nowrap;
  transition: color 180ms ease-out, background-color 180ms ease-out;
}

.project-tab:hover,
.project-tab.is-active {
  background: var(--pa-primary-soft);
  color: var(--pa-primary-hover);
}

.project-tab.is-active {
  font-weight: 650;
}

.project-topic {
  display: block;
  overflow: hidden;
  color: var(--pa-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-tabs :focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

@media (max-width: 1120px) {
  .project-topic {
    display: none;
  }
}

@media (max-width: 760px) {
  :deep(.product-header__navigation) {
    width: 100%;
    order: 5;
    margin: 7px 0 0;
    overflow-x: auto;
  }

  .project-tabs {
    margin-left: 0;
  }

  .project-tab {
    min-height: 40px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .project-tab {
    transition: none;
  }
}
</style>

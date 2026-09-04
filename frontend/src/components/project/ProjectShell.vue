<template>
  <div class="project-shell">
    <aside class="global-sidebar" aria-label="全局导航">
      <RouterLink class="sidebar-brand" to="/home" aria-label="返回 PaperAI 首页">
        <BrandMark :size="28" />
      </RouterLink>

      <nav class="global-nav" aria-label="主导航">
        <RouterLink to="/home" class="global-nav__item" active-class="is-active" title="首页">
          <span class="global-nav__icon" aria-hidden="true"><IconHome /></span>
          <span>首页</span>
        </RouterLink>
        <RouterLink to="/projects" class="global-nav__item" active-class="is-active" title="项目">
          <span class="global-nav__icon" aria-hidden="true"><IconApps /></span>
          <span>项目</span>
        </RouterLink>
        <RouterLink to="/library" class="global-nav__item" active-class="is-active" title="独立阅读">
          <span class="global-nav__icon" aria-hidden="true"><IconBook /></span>
          <span>独立阅读</span>
        </RouterLink>
      </nav>

      <div v-if="recentProjects.length" class="recent-projects">
        <p class="sidebar-label">最近项目</p>
        <RouterLink
          v-for="project in recentProjects.slice(0, 5)"
          :key="project.id"
          :class="['recent-project', { 'is-active': isCurrentProject(project.id) }]"
          :to="{ name: 'ProjectOverview', params: { projectId: project.id } }"
          :title="project.title"
        >
          <span class="recent-project__dot" aria-hidden="true"></span>
          <span>{{ project.title }}</span>
        </RouterLink>
      </div>

      <div class="sidebar-footer">
        <RouterLink class="sidebar-footer__link" to="/library">打开论文库</RouterLink>
      </div>
    </aside>

    <div class="project-shell__content">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { IconApps, IconBook, IconHome } from '@arco-design/web-vue/es/icon'
import BrandMark from '@/components/BrandMark.vue'
import type { ResearchProject } from '@/api/projects'

withDefaults(defineProps<{ recentProjects?: ResearchProject[] }>(), {
  recentProjects: () => [],
})

const route = useRoute()
const isCurrentProject = (projectId: string) => String(route.params.projectId || '') === projectId
</script>

<style scoped>
.project-shell {
  display: flex;
  min-height: 100vh;
  background: var(--pa-bg);
}

.global-sidebar {
  position: sticky;
  top: 0;
  display: flex;
  width: var(--pa-sidebar-width);
  height: 100vh;
  flex: 0 0 var(--pa-sidebar-width);
  flex-direction: column;
  border-right: 1px solid var(--pa-border);
  background: var(--pa-surface-soft);
}

.sidebar-brand {
  display: flex;
  min-height: var(--pa-header-height);
  align-items: center;
  padding: 0 16px;
  border-bottom: 1px solid var(--pa-border);
}

.sidebar-brand:focus-visible,
.global-nav__item:focus-visible,
.recent-project:focus-visible,
.sidebar-footer__link:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 3px;
}

.global-nav {
  display: grid;
  gap: var(--pa-space-1);
  padding: var(--pa-space-3) 10px var(--pa-space-2);
}

.global-nav__item {
  display: flex;
  min-height: 40px;
  align-items: center;
  gap: 10px;
  padding: 0 10px;
  border-radius: var(--pa-radius-sm);
  color: var(--pa-muted);
  font-size: 13px;
  text-decoration: none;
  transition: color 180ms ease-out, background-color 180ms ease-out;
}

.global-nav__icon {
  display: inline-flex;
  width: 18px;
  height: 18px;
  flex: 0 0 18px;
  align-items: center;
  justify-content: center;
  color: currentColor;
  line-height: 1;
}

.global-nav__item:hover,
.global-nav__item.is-active {
  background: var(--pa-primary-soft);
  color: var(--pa-primary-hover);
}

.global-nav__item.is-active {
  font-weight: 650;
}

.recent-projects {
  display: grid;
  gap: 3px;
  padding: var(--pa-space-3) 10px 0;
}

.sidebar-label {
  margin: 0 10px 5px;
  color: var(--pa-muted);
  font-size: 11px;
  font-weight: 650;
}

.recent-project {
  display: flex;
  min-height: 32px;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 0 10px;
  overflow: hidden;
  border-radius: var(--pa-radius-sm);
  color: var(--pa-text);
  font-size: 12px;
  text-decoration: none;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-project:hover {
  background: var(--pa-surface-soft);
  color: var(--pa-primary-hover);
}

.recent-project.is-active {
  background: var(--pa-primary-soft);
  color: var(--pa-primary-hover);
  font-weight: 650;
}

.recent-project__dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: var(--pa-primary);
}

.sidebar-footer {
  margin-top: auto;
  padding: 12px 16px 16px;
  border-top: 1px solid var(--pa-border);
}

.sidebar-footer__link {
  color: var(--pa-muted);
  font-size: 12px;
  text-decoration: none;
}

.sidebar-footer__link:hover {
  color: var(--pa-primary-hover);
}

.project-shell__content {
  min-width: 0;
  flex: 1;
}

@media (max-width: 1024px) {
  .global-sidebar {
    width: var(--pa-sidebar-collapsed-width);
    flex-basis: var(--pa-sidebar-collapsed-width);
  }

  .sidebar-brand {
    justify-content: center;
    padding: 0;
  }

  .global-nav {
    padding-inline: 10px;
  }

  .global-nav__item {
    justify-content: center;
    padding-inline: 0;
  }

  .global-nav__item > span:last-child,
  .recent-projects,
  .sidebar-footer {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .global-nav__item {
    transition: none;
  }
}
</style>

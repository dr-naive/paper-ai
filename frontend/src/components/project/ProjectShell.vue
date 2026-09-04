<template>
  <div class="project-shell">
    <aside class="global-sidebar" aria-label="全局导航">
      <RouterLink class="sidebar-brand" to="/home" aria-label="返回 PaperAI 首页">
        <BrandMark :size="28" />
      </RouterLink>

      <nav class="global-nav" aria-label="主导航">
        <RouterLink to="/home" class="global-nav__item" active-class="is-active">
          <span aria-hidden="true">⌂</span>
          <span>首页</span>
        </RouterLink>
        <RouterLink to="/projects" class="global-nav__item" active-class="is-active">
          <span aria-hidden="true">▦</span>
          <span>项目</span>
        </RouterLink>
        <RouterLink to="/library" class="global-nav__item" active-class="is-active">
          <span aria-hidden="true">▤</span>
          <span>独立阅读</span>
        </RouterLink>
      </nav>

      <div v-if="recentProjects.length" class="recent-projects">
        <p class="sidebar-label">最近项目</p>
        <RouterLink
          v-for="project in recentProjects.slice(0, 5)"
          :key="project.id"
          class="recent-project"
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
import BrandMark from '@/components/BrandMark.vue'
import type { ResearchProject } from '@/api/projects'

withDefaults(defineProps<{ recentProjects?: ResearchProject[] }>(), {
  recentProjects: () => [],
})
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
  width: 236px;
  height: 100vh;
  flex: 0 0 236px;
  flex-direction: column;
  border-right: 1px solid var(--pa-border);
  background: var(--pa-surface);
}

.sidebar-brand {
  display: flex;
  min-height: 68px;
  align-items: center;
  padding: 0 20px;
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
  gap: 4px;
  padding: 20px 12px 10px;
}

.global-nav__item {
  display: flex;
  min-height: 40px;
  align-items: center;
  gap: 11px;
  padding: 0 12px;
  border-radius: 7px;
  color: var(--pa-muted);
  font-size: 13px;
  text-decoration: none;
  transition: color 180ms ease-out, background-color 180ms ease-out;
}

.global-nav__item > span:first-child {
  width: 18px;
  color: currentColor;
  font-size: 18px;
  line-height: 1;
  text-align: center;
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
  padding: 16px 12px 0;
}

.sidebar-label {
  margin: 0 12px 7px;
  color: var(--pa-muted);
  font-size: 11px;
  font-weight: 650;
}

.recent-project {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  overflow: hidden;
  border-radius: 6px;
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

.recent-project__dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: var(--pa-primary);
}

.sidebar-footer {
  margin-top: auto;
  padding: 14px 20px 18px;
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

@media (max-width: 860px) {
  .global-sidebar {
    width: 70px;
    flex-basis: 70px;
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

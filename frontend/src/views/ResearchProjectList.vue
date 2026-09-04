<template>
  <div class="project-list-page">
    <ProductHeader context="论文工作台">
      <template #actions><a-button size="small" @click="$router.push('/library')">本地论文库</a-button></template>
    </ProductHeader>

    <main class="project-list-shell">
      <header class="library-header">
        <div class="header-left">
          <h1>论文研究与写作</h1>
          <p>
            {{
              projects.length
                ? `${projects.length} 个项目，从调研到写作全流程管理。`
                : '创建一个研究项目，开始文献调研、写作与投稿管理。'
            }}
          </p>
        </div>
        <a-button type="primary" size="large" @click="showCreateModal = true">新建项目</a-button>
      </header>

      <a-spin :loading="loading">
        <div v-if="!loading && projects.length === 0" class="empty-library">
          <div class="empty-document" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="1.6">
              <path d="M3 7h18M3 12h18M3 17h12" />
            </svg>
          </div>
          <h2>开启你的第一个研究项目</h2>
          <p>从文献调研到论文写作，agent 会帮你管理阅读笔记、生成综述、起草章节。</p>
          <a-button type="primary" @click="showCreateModal = true">新建项目</a-button>
        </div>

        <section v-else class="project-grid" aria-label="项目列表">
          <article
            v-for="p in projects"
            :key="p.id"
            class="project-card"
            role="button"
            tabindex="0"
            @click="openProject(p)"
            @keydown.enter="openProject(p)"
            @keydown.space.prevent="openProject(p)"
          >
            <div class="project-card-header">
              <span class="phase-badge" :class="`phase-${p.phase}`">{{ phaseLabel(p.phase) }}</span>
              <span class="status-label" :class="`status-${p.status}`">{{ statusLabel(p.status) }}</span>
            </div>
            <h3>{{ p.title }}</h3>
            <p class="project-topic">{{ p.research_topic }}</p>
            <p v-if="p.abstract" class="project-abstract">{{ p.abstract }}</p>
            <div class="project-meta">
              <span class="meta-item">
                <span class="meta-num">{{ p.paper_count ?? 0 }}</span> 文档
              </span>
              <span class="meta-item">
                <span class="meta-num">{{ p.artifact_count ?? 0 }}</span> 产物
              </span>
              <span v-if="p.updated_at" class="meta-time">{{ formatTime(p.updated_at) }}</span>
            </div>
            <div class="project-actions" aria-label="打开项目功能">
              <button type="button" @click.stop="openProjectArea(p, 'topic')">选题</button>
              <button type="button" @click.stop="openProjectArea(p, 'reading')">阅读</button>
              <button type="button" class="primary" @click.stop="openProjectArea(p, 'writing')">开始写作</button>
            </div>
          </article>
        </section>
      </a-spin>
    </main>

    <!-- 新建项目 Modal -->
    <a-modal v-model:visible="showCreateModal" title="新建研究项目" @ok="handleCreate" :ok-loading="creating">
      <a-form :model="createForm" layout="vertical">
        <a-form-item field="title" label="项目标题" required>
          <a-input v-model="createForm.title" placeholder="例如:MLLM 伪造检测调研" />
        </a-form-item>
        <a-form-item field="research_topic" label="研究主题" required>
          <a-input v-model="createForm.research_topic" placeholder="一句话描述你的研究方向" />
        </a-form-item>
        <a-form-item field="abstract" label="项目摘要(可选)">
          <a-textarea
            v-model="createForm.abstract"
            placeholder="研究背景、目标、计划阅读的论文范围等"
            :auto-size="{ minRows: 3, maxRows: 6 }"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import ProductHeader from '@/components/ProductHeader.vue'
import {
  listProjects,
  createProject,
  PHASE_LABELS,
  STATUS_LABELS,
  type ResearchProject,
} from '@/api/projects'

const router = useRouter()
const projects = ref<ResearchProject[]>([])
const loading = ref(false)
const showCreateModal = ref(false)
const creating = ref(false)
const createForm = ref({ title: '', research_topic: '', abstract: '' })

const phaseLabel = (phase: string) => PHASE_LABELS[phase] || phase
const statusLabel = (status: string) => STATUS_LABELS[status] || status

const formatTime = (iso: string) => {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = (now.getTime() - d.getTime()) / 1000
    if (diff < 60) return '刚刚'
    if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
    if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
    if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`
    return d.toLocaleDateString('zh-CN')
  } catch {
    return ''
  }
}

const openProject = (p: ResearchProject) => {
  router.push(`/project/${p.id}`)
}

const openProjectArea = (p: ResearchProject, area: 'topic' | 'reading' | 'writing') => {
  router.push({ path: `/project/${p.id}`, query: { area } })
}

const loadProjects = async () => {
  loading.value = true
  try {
    const res = await listProjects({ page: 1, page_size: 50 })
    projects.value = res.items || []
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '加载项目失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!createForm.value.title.trim() || !createForm.value.research_topic.trim()) {
    Message.warning('项目标题和研究主题必填')
    return
  }
  creating.value = true
  try {
    const created = await createProject({
      title: createForm.value.title.trim(),
      research_topic: createForm.value.research_topic.trim(),
      abstract: createForm.value.abstract.trim(),
    })
    Message.success('项目创建成功')
    showCreateModal.value = false
    createForm.value = { title: '', research_topic: '', abstract: '' }
    // 直接跳转到新建项目的工作台
    router.push(`/project/${created.id}`)
  } catch (e: any) {
    Message.error(e?.response?.data?.detail || '创建项目失败')
  } finally {
    creating.value = false
  }
}

onMounted(loadProjects)
</script>

<style scoped>
.project-list-page {
  min-height: 100vh;
  background: var(--color-bg-1);
}
.project-list-shell {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}
.library-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 28px;
}
.header-left h1 {
  margin: 0 0 4px;
  font-size: 24px;
  font-weight: 600;
}
.header-left p {
  margin: 0;
  color: var(--color-text-2);
  font-size: 14px;
}
.empty-library {
  text-align: center;
  padding: 64px 24px;
  background: var(--color-bg-2);
  border-radius: 12px;
  border: 1px dashed var(--color-border-2);
}
.empty-document {
  display: inline-flex;
  width: 56px;
  height: 56px;
  align-items: center;
  justify-content: center;
  border-radius: 14px;
  background: var(--color-fill-2);
  color: var(--color-text-3);
  margin-bottom: 16px;
}
.empty-library h2 {
  margin: 0 0 8px;
  font-size: 18px;
}
.empty-library p {
  margin: 0 0 20px;
  color: var(--color-text-2);
  font-size: 14px;
}
.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.project-card {
  background: var(--color-bg-2);
  border: 1px solid var(--color-border-2);
  border-radius: 12px;
  padding: 20px;
  cursor: pointer;
  transition: transform 180ms ease-out, border-color 180ms ease-out, box-shadow 180ms ease-out;
}
.project-card:hover {
  border-color: rgb(var(--primary-6));
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  transform: translateY(-2px);
}
.project-card:focus-visible {
  outline: 2px solid rgb(var(--primary-6));
  outline-offset: 2px;
}
.project-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.phase-badge {
  display: inline-block;
  padding: 2px 10px;
  font-size: 12px;
  border-radius: 10px;
  font-weight: 500;
  background: var(--color-fill-2);
  color: var(--color-text-2);
}
.phase-badge.phase-research { background: rgba(168, 127, 226, 0.12); color: #8a5cf6; }
.phase-badge.phase-reading { background: rgba(32, 145, 255, 0.12); color: #2091ff; }
.phase-badge.phase-writing { background: rgba(0, 180, 42, 0.12); color: #00b42a; }
.phase-badge.phase-refinement { background: rgba(255, 156, 0, 0.12); color: #ff9c00; }
.phase-badge.phase-archived { background: var(--color-fill-3); color: var(--color-text-3); }
.status-label {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--pa-surface-soft);
  color: var(--pa-muted);
  font-size: 12px;
}
.status-label.status-active { background: oklch(0.95 0.035 145); color: var(--pa-success); }
.status-label.status-paused { background: oklch(0.96 0.04 75); color: oklch(0.48 0.12 65); }
.status-label.status-completed { background: var(--pa-surface-soft); color: var(--pa-muted); }
.project-card h3 {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.project-topic {
  margin: 0 0 8px;
  font-size: 13px;
  color: rgb(var(--primary-6));
  font-weight: 500;
}
.project-abstract {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--color-text-2);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.project-meta {
  display: flex;
  align-items: center;
  gap: 16px;
  font-size: 12px;
  color: var(--color-text-3);
}
.meta-item .meta-num {
  color: var(--color-text-1);
  font-weight: 600;
  margin-right: 2px;
}
.meta-time {
  margin-left: auto;
}
.project-actions { display: flex; gap: 5px; margin-top: 14px; padding-top: 10px; border-top: 1px solid var(--pa-border); }
.project-actions button { min-height: 29px; padding: 0 10px; border: 1px solid var(--pa-border); border-radius: 5px; background: var(--pa-surface); color: var(--pa-text); font: inherit; font-size: 11px; cursor: pointer; }
.project-actions button:hover { border-color: var(--pa-primary); color: var(--pa-primary); }
.project-actions button.primary { margin-left: auto; border-color: var(--pa-primary); background: var(--pa-primary); color: white; }
.project-actions button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }

@media (max-width: 680px) {
  .project-list-shell { padding: 24px 16px 48px; }
  .library-header { align-items: stretch; flex-direction: column; }
  .library-header :deep(.arco-btn) { min-height: 44px; }
  .project-grid { grid-template-columns: 1fr; }
  .project-card { padding: 16px; }
}

@media (prefers-reduced-motion: reduce) {
  .project-card { transition: none; }
}
</style>

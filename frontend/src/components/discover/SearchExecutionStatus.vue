<template>
  <section v-if="visible" class="execution-card" :class="`execution-${status}`" aria-live="polite" aria-labelledby="execution-title">
    <div class="execution-icon" aria-hidden="true">
      <IconExclamationCircle v-if="status === 'failed'" />
      <IconCheck v-else-if="status === 'completed'" />
      <IconLoading v-else />
    </div>
    <div class="execution-copy">
      <p class="section-label">Search execution</p>
      <h2 id="execution-title">{{ title }}</h2>
      <p>{{ message }}</p>
      <p v-if="status === 'completed'" class="execution-meta">
        {{ resultCount }} 篇结果 · {{ searchRounds || 1 }} 轮检索
      </p>
      <p v-if="errorMessage" class="execution-error" role="alert">{{ errorMessage }}</p>
      <ul v-if="warnings.length" class="execution-warnings">
        <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { IconCheck, IconExclamationCircle, IconLoading } from '@arco-design/web-vue/es/icon'

const props = defineProps<{
  status: string
  message: string
  resultCount: number
  searchRounds: number
  warnings: string[]
  errorMessage?: string
}>()

const visible = computed(() => ['searching', 'completed', 'failed'].includes(props.status))
const title = computed(() => ({
  searching: '正在搜索相关论文',
  completed: props.resultCount ? '检索已完成' : '检索完成',
  failed: '检索未完成',
}[props.status] || '检索状态'))
</script>

<style scoped>
.execution-card { display: flex; gap: 14px; padding: 16px 20px; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface); }
.execution-searching { background: var(--pa-surface-soft); }
.execution-failed { border-color: var(--pa-danger); background: var(--pa-danger-soft); }
.execution-icon { display: grid; width: 30px; height: 30px; flex: none; place-items: center; border-radius: 50%; background: var(--pa-primary-soft); color: var(--pa-primary-hover); font-size: 17px; }
.execution-failed .execution-icon { background: var(--pa-danger-soft); color: var(--pa-danger); }
.section-label { margin: 0 0 4px; color: var(--pa-primary-hover); font-size: 10px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.execution-copy h2 { margin: 0; color: var(--pa-ink); font-size: 16px; line-height: 1.35; }
.execution-copy p:not(.section-label) { margin: 5px 0 0; color: var(--pa-muted); font-size: 13px; line-height: 1.55; }
.execution-meta { color: var(--pa-text) !important; font-weight: 600; }
.execution-error { color: var(--pa-danger) !important; }
.execution-warnings { margin: 8px 0 0; padding-left: 18px; color: var(--pa-muted); font-size: 12px; line-height: 1.55; }
</style>

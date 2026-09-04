<template>
  <aside :class="['agent-drawer', { open: workspace.agentDrawerOpen }]" aria-label="研究助手">
    <button type="button" class="drawer-toggle" :aria-expanded="workspace.agentDrawerOpen" @click="workspace.setAgentDrawerOpen(!workspace.agentDrawerOpen)"><span aria-hidden="true">{{ workspace.agentDrawerOpen ? '→' : '←' }}</span><span class="pa-sr-only">{{ workspace.agentDrawerOpen ? '收起研究助手' : '展开研究助手' }}</span></button>
    <template v-if="workspace.agentDrawerOpen">
      <header><div><strong>研究助手</strong><span>{{ contextGroup }}</span></div><span v-if="executionStore.runningCount" class="running">{{ executionStore.runningCount }} 个任务处理中</span></header>
      <section class="context"><span>当前上下文</span><strong>{{ contextLabel }}</strong><p>{{ contextDescription }}</p></section>
      <section class="latest"><span>最近活动</span><p v-if="!latestExecution">还没有 Agent 执行记录。</p><button v-else type="button" @click="emit('activity')"><strong>{{ latestExecution.goal }}</strong><small>{{ statusLabel(latestExecution.status) }} · {{ formatTime(latestExecution.updated_at) }}</small></button></section>
      <section class="suggestions"><span>建议操作</span><button v-for="action in actions" :key="action.prompt" type="button" @click="emit('ask', action.prompt)">{{ action.label }}</button></section>
      <form class="composer" @submit.prevent="submit"><label for="project-agent-question">向研究助手提问</label><a-textarea id="project-agent-question" v-model="question" :auto-size="{ minRows: 3, maxRows: 6 }" placeholder="询问当前项目，或描述下一步任务" /><a-button type="primary" html-type="submit" long :disabled="!question.trim()" :loading="submitting">发送到项目对话</a-button></form>
    </template>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useExecutionsStore } from '@/stores/executions'
import { useWorkspaceStore } from '@/stores/workspace'

const props = defineProps<{ projectId: string; contextGroup: string; contextLabel: string; contextDescription: string; contextPrompt: string; submitting?: boolean }>()
const emit = defineEmits<{ ask: [prompt: string]; activity: [] }>()
const workspace = useWorkspaceStore()
const executionStore = useExecutionsStore()
const question = ref('')
const latestExecution = computed(() => executionStore.projectExecutions(props.projectId)[0])
const actions = computed(() => [
  { label: `处理“${props.contextLabel}”`, prompt: props.contextPrompt },
  { label: '检查证据缺口', prompt: '请检查当前项目的证据覆盖、冲突和缺口，并给出下一步可执行动作。' },
  { label: '总结最近进展', prompt: '请根据当前项目资料和最近执行，概括已完成工作、未解决问题和下一步。' },
])
const statusLabel = (status: string) => ({ queued: '排队中', running: '执行中', waiting_user: '等待确认', paused: '已暂停', completed: '已完成', failed: '失败', cancelled: '已取消' }[status] || status)
const formatTime = (value?: string | null) => value ? new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }) : '未知时间'
const load = () => executionStore.loadProject(props.projectId).catch(() => undefined)
const submit = () => { const prompt = question.value.trim(); if (!prompt) return; emit('ask', prompt); question.value = '' }
watch(() => props.projectId, load)
onMounted(load)
</script>

<style scoped>
.agent-drawer { position: sticky; top: 12px; width: 44px; height: fit-content; min-height: 52px; overflow: hidden; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface); box-shadow: var(--pa-shadow-sm); transition: width 220ms cubic-bezier(.25,1,.5,1); }.agent-drawer.open { width: 340px; }.drawer-toggle { display: grid; width: 42px; height: 42px; place-items: center; margin: 4px; border: 0; border-radius: 6px; background: var(--pa-surface-soft); color: var(--pa-primary); cursor: pointer; font-size: 18px; }.agent-drawer header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; padding: 8px 14px 14px; border-bottom: 1px solid var(--pa-border); }.agent-drawer header div { display: flex; flex-direction: column; gap: 2px; }.agent-drawer header strong { font-size: 16px; }.agent-drawer header span,.context > span,.latest > span,.suggestions > span { color: var(--pa-muted); font-size: 11px; }.running { padding: 3px 7px; border-radius: 999px; background: var(--color-primary-light-1); color: var(--pa-primary) !important; }.context,.latest,.suggestions { padding: 14px; border-bottom: 1px solid var(--pa-border); }.context strong { display: block; margin-top: 5px; font-size: 14px; }.context p,.latest p { margin: 4px 0 0; color: var(--pa-muted); font-size: 12px; line-height: 1.5; }.latest button,.suggestions button { width: 100%; margin-top: 7px; padding: 8px; border: 0; border-radius: 6px; background: var(--pa-surface-soft); color: var(--pa-text); cursor: pointer; text-align: left; }.latest button { display: flex; flex-direction: column; gap: 3px; }.latest small { color: var(--pa-muted); }.suggestions button:hover,.latest button:hover { background: var(--color-primary-light-1); color: var(--pa-primary); }.composer { display: flex; flex-direction: column; gap: 8px; padding: 14px; }.composer label { color: var(--pa-text); font-size: 12px; font-weight: 600; }@media (max-width: 1180px) { .agent-drawer { position: fixed; z-index: 20; right: 12px; bottom: 12px; top: auto; }.agent-drawer.open { width: min(340px, calc(100vw - 24px)); max-height: calc(100vh - 90px); overflow-y: auto; } }@media (prefers-reduced-motion: reduce) { .agent-drawer { transition: none; } }
</style>

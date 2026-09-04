<template>
  <section class="requirement-card" aria-labelledby="requirement-title">
    <div v-if="collapsed" class="requirement-collapsed">
      <div>
        <p class="section-label">当前检索需求</p>
        <p class="collapsed-topic">{{ topic }}</p>
      </div>
      <a-button type="secondary" size="small" @click="$emit('reopen')">重新讨论</a-button>
    </div>

    <template v-else>
      <header class="requirement-heading">
        <div>
          <p class="section-label">Requirement clarification</p>
          <h2 id="requirement-title">与 PaperAI 明确你要找的论文</h2>
          <p>先描述研究主题、对象或关注问题，确认后再开始结构化检索。</p>
        </div>
        <span class="requirement-state" :class="`state-${status}`">{{ stateLabel }}</span>
      </header>

      <div class="message-list" aria-live="polite">
        <div v-for="message in messages" :key="message.id" class="message-row" :class="`message-${message.role}`">
          <p>{{ message.content }}</p>
        </div>
      </div>

      <form class="requirement-composer" @submit.prevent="send">
        <label class="pa-sr-only" for="requirement-input">描述你的研究需求</label>
        <a-textarea
          id="requirement-input"
          v-model="draft"
          :auto-size="{ minRows: 3, maxRows: 6 }"
          :disabled="status === 'searching'"
          placeholder="例如：我想找生成式 AI 对大学生自主学习影响的实证研究"
        />
        <div class="composer-footer">
          <span>可以直接写自然语言，确认后仍可编辑检索条件。</span>
          <a-button type="primary" html-type="submit" :disabled="!draft.trim() || status === 'searching'">整理检索需求</a-button>
        </div>
      </form>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RequirementMessage } from '@/stores/discover'

const props = defineProps<{
  messages: RequirementMessage[]
  status: string
  topic: string
}>()

const emit = defineEmits<{
  send: [content: string]
  reopen: []
}>()

const draft = ref(props.topic)
const collapsed = computed(() => props.status === 'searching' || props.status === 'completed')
const stateLabel = computed(() => ({
  clarifying: '正在明确需求',
  ready_for_search: '已整理检索需求',
  failed: '可以重新讨论',
}[props.status] || '等待输入'))

const send = () => {
  const content = draft.value.trim()
  if (!content) return
  // The parent/store owns the conversation and readiness transition.
  emit('send', content)
  draft.value = ''
}
</script>

<style scoped>
.requirement-card { border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); overflow: hidden; }
.requirement-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 20px; padding: 28px 30px 18px; }
.section-label { margin: 0 0 7px; color: var(--pa-primary-hover); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.requirement-heading h2 { margin: 0; color: var(--pa-ink); font-size: 22px; line-height: 1.3; }
.requirement-heading p:not(.section-label) { margin: 8px 0 0; color: var(--pa-muted); font-size: 14px; line-height: 1.6; }
.requirement-state { flex: none; padding: 5px 9px; border-radius: 999px; background: var(--pa-primary-soft); color: var(--pa-primary-hover); font-size: 12px; }
.state-failed { background: oklch(0.96 0.025 28); color: var(--pa-danger); }
.message-list { display: grid; gap: 10px; max-height: 240px; padding: 8px 30px 20px; overflow: auto; }
.message-row { max-width: 88%; padding: 10px 13px; border-radius: 8px; color: var(--pa-text); font-size: 14px; line-height: 1.6; }
.message-row p { margin: 0; white-space: pre-wrap; }
.message-assistant { justify-self: start; background: var(--pa-surface-soft); }
.message-user { justify-self: end; background: var(--pa-primary-soft); }
.requirement-composer { padding: 0 30px 24px; }
.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 10px; }
.composer-footer span { color: var(--pa-muted); font-size: 12px; }
.requirement-collapsed { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 64px; padding: 12px 18px 12px 22px; }
.requirement-collapsed .section-label { margin-bottom: 3px; }
.collapsed-topic { max-width: 70ch; margin: 0; overflow: hidden; color: var(--pa-text); font-size: 14px; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 680px) {
  .requirement-heading { flex-direction: column; padding: 22px 18px 14px; }
  .message-list, .requirement-composer { padding-left: 18px; padding-right: 18px; }
  .composer-footer { align-items: stretch; flex-direction: column; }
  .composer-footer .arco-btn { width: 100%; }
  .requirement-collapsed { align-items: flex-start; flex-direction: column; padding: 14px 18px; }
}
</style>

<template>
  <aside class="agent-panel" :class="{ collapsed }" aria-label="Writing Agent">
    <button type="button" class="panel-toggle" :aria-label="collapsed ? '展开 Writing Agent' : '收起 Writing Agent'" :aria-expanded="!collapsed" @click="$emit('toggle')">
      <span aria-hidden="true">{{ collapsed ? '‹' : '›' }}</span>
      <span v-if="collapsed" class="vertical-label">Agent</span>
    </button>
    <div v-if="!collapsed" class="agent-content">
      <header class="agent-header">
        <div><span class="eyebrow">写作助手</span><h3>Writing Agent</h3></div>
        <span class="context-status" aria-live="polite">{{ requestStatus === 'generating' ? '处理中' : '上下文已同步' }}</span>
      </header>

      <section class="context-card" aria-label="当前编辑器上下文">
        <span>当前章节</span>
        <strong>{{ context.currentHeading }}</strong>
        <p v-if="context.sectionPath.length" class="section-path">{{ context.sectionPath.join(' / ') }}</p>
        <div class="context-badges">
          <span>{{ context.selectedCharacterCount ? `已选择 ${context.selectedCharacterCount} 字` : '未选择文本' }}</span>
          <span>v{{ revisionVersion }}</span>
        </div>
      </section>

      <div v-if="messages.length" class="agent-conversation" aria-label="写作对话">
        <div v-for="message in messages" :key="message.id" class="agent-message" :class="`message-${message.role}`">
          <span class="message-role">{{ message.role === 'user' ? '你' : 'Agent' }}</span>
          <p>{{ message.content }}</p>
        </div>
      </div>
      <section v-else class="agent-guidance">
        <strong>{{ context.selectedCharacterCount ? '基于选区协作' : '基于当前章节协作' }}</strong>
        <p v-if="context.selectedCharacterCount">描述你希望如何改写选中的内容，正文只有在你确认建议后才会变化。</p>
        <p v-else>描述你要写的一个段落，Agent 只使用当前项目已导入、可检索的论文证据。</p>
      </section>

      <WritingProposalCard
        v-if="proposal"
        :proposal="proposal"
        :evidence="evidence"
        :replace-disabled="replaceDisabled"
        :replace-disabled-reason="replaceDisabledReason"
        :project-id="projectId"
        @copy="$emit('copy')"
        @replace="$emit('replace')"
        @dismiss="$emit('dismiss')"
      />
      <p v-if="requestError" class="agent-error" role="alert">{{ requestError }}</p>
      <p v-if="requestStatus === 'generating'" class="agent-progress" role="status" aria-live="polite">{{ requestStage }}</p>

      <slot />

      <form class="agent-composer" aria-label="向 Writing Agent 提问" @submit.prevent="submitInstruction">
        <label class="pa-sr-only" for="writing-agent-instruction">写作指令</label>
        <textarea id="writing-agent-instruction" v-model="draft" :disabled="!canSubmit || requestStatus === 'generating'" :placeholder="context.selectedCharacterCount ? '例如：润色得更学术，但不要改变原意' : '例如：根据已导入论文写一段研究现状'" rows="3" @keydown.ctrl.enter.prevent="submitInstruction" @keydown.meta.enter.prevent="submitInstruction"></textarea>
        <div class="composer-footer">
          <span>{{ context.selectedCharacterCount ? '改写当前选区' : '生成一个段落' }}</span>
          <button type="submit" :disabled="!canSubmit || requestStatus === 'generating' || !draft.trim()">{{ requestStatus === 'generating' ? '处理中…' : '发送' }}</button>
        </div>
      </form>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { EvidenceItem } from '@/api/projects'
import type { WritingEditorContext, WritingAgentMessage, WritingAgentStatus, WritingProposal } from '@/stores/writing'
import WritingProposalCard from './WritingProposalCard.vue'

const props = defineProps<{
  context: WritingEditorContext
  collapsed: boolean
  revisionVersion: number
  messages: WritingAgentMessage[]
  proposal: WritingProposal | null
  requestStatus: WritingAgentStatus
  requestStage: string
  requestError: string
  canSubmit: boolean
  replaceDisabled: boolean
  replaceDisabledReason: string
  evidence: EvidenceItem[]
  projectId: string
}>()
const emit = defineEmits<{ toggle: []; submit: [instruction: string]; copy: []; replace: []; dismiss: [] }>()

const draft = ref('')
const submitInstruction = () => {
  const instruction = draft.value.trim()
  if (!instruction || !props.canSubmit || props.requestStatus === 'generating') return
  draft.value = ''
  // The parent owns the API call and request state. This component only owns draft input.
  emit('submit', instruction)
}
</script>

<style scoped>
.agent-panel { position: relative; min-width: 0; border-left: 1px solid var(--pa-border); background: var(--pa-surface-soft); }
.agent-panel.collapsed { width: 44px; }
.panel-toggle { position: absolute; z-index: 2; top: 6px; left: -18px; display: grid; place-items: center; min-width: 36px; min-height: 36px; border: 1px solid var(--pa-border); border-radius: 18px; background: var(--pa-surface); color: var(--pa-text); cursor: pointer; box-shadow: var(--pa-shadow-sm); }
.panel-toggle::before { position: absolute; inset: -4px; content: ''; }
.panel-toggle:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.vertical-label { margin-top: 6px; writing-mode: vertical-rl; color: var(--pa-muted); font-size: 11px; letter-spacing: .08em; }
.collapsed .panel-toggle { position: static; margin: 6px 4px; border-radius: 6px; }
.agent-content { display: flex; flex-direction: column; height: 100%; min-height: calc(100vh - 52px); padding: 12px; overflow: auto; }
.agent-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }.eyebrow { color: var(--pa-primary); font-size: 9px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; } h3 { margin-top: 1px; font-size: 15px; }
.context-status { padding: 4px 7px; border: 1px solid var(--pa-border); border-radius: 999px; color: var(--pa-success); background: var(--pa-surface); font-size: 10px; white-space: nowrap; }
.context-card,.agent-guidance { margin-top: 10px; padding: 9px; border: 1px solid var(--pa-border); border-radius: 6px; background: var(--pa-surface); }.context-card > span { color: var(--pa-muted); font-size: 10px; }.context-card > strong { display: block; margin-top: 2px; color: var(--pa-ink); font-size: 12px; }.section-path { margin-top: 3px; color: var(--pa-muted); font-size: 10px; line-height: 1.4; }.context-badges { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }.context-badges span { padding: 3px 6px; border-radius: 4px; background: var(--pa-primary-soft); color: var(--pa-primary-hover); font-size: 9px; }
.agent-guidance strong { font-size: 12px; }.agent-guidance p { margin-top: 4px; color: var(--pa-muted); font-size: 11px; line-height: 1.5; }
.agent-conversation { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }.agent-message { padding: 9px 10px; border-radius: 7px; font-size: 12px; line-height: 1.55; }.message-user { align-self: flex-end; max-width: 92%; background: var(--pa-primary-soft); }.message-assistant { align-self: stretch; border: 1px solid var(--pa-border); background: var(--pa-surface); }.message-role { display: block; margin-bottom: 3px; color: var(--pa-muted); font-size: 10px; font-weight: 650; }.agent-message p { white-space: pre-wrap; }
.agent-error { margin-top: 12px; padding: 9px 10px; border: 1px solid oklch(0.75 0.12 28); border-radius: 6px; background: oklch(0.97 0.025 28); color: var(--pa-danger); font-size: 12px; line-height: 1.5; }.agent-progress { margin-top: 12px; color: var(--pa-primary-hover); font-size: 12px; }
.agent-composer { position: sticky; bottom: 0; margin-top: auto; padding-top: 10px; background: var(--pa-surface-soft); }.agent-composer textarea { display: block; width: 100%; min-height: 68px; resize: vertical; padding: 7px 8px; border: 1px solid var(--pa-border); border-radius: 5px; background: var(--pa-surface); color: var(--pa-text); font: inherit; font-size: 11px; line-height: 1.45; }.agent-composer textarea:focus { border-color: var(--pa-primary); outline: 0; box-shadow: var(--pa-focus-ring); }.agent-composer textarea:disabled { cursor: not-allowed; opacity: .6; }.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin-top: 5px; color: var(--pa-muted); font-size: 9px; }.composer-footer button { min-height: 32px; padding: 4px 12px; border: 1px solid var(--pa-primary); border-radius: 4px; background: var(--pa-primary); color: white; cursor: pointer; font-size: 11px; }.composer-footer button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }.composer-footer button:disabled { cursor: not-allowed; opacity: .55; }
@media (max-width: 767px) { .agent-content { min-height: 0; } }
@media (pointer: coarse) { .panel-toggle { min-width: 44px; min-height: 44px; } }
</style>

<template>
  <aside class="agent-panel" :class="{ collapsed }" aria-label="Writing Agent">
    <button type="button" class="panel-toggle" :aria-label="collapsed ? '展开 Writing Agent' : '收起 Writing Agent'" :aria-expanded="!collapsed" @click="$emit('toggle')">
      <IconLeft v-if="collapsed" aria-hidden="true" />
      <IconRight v-else aria-hidden="true" />
      <span v-if="collapsed" class="vertical-label">助手</span>
    </button>
    <div v-if="!collapsed" class="agent-content">
      <header class="agent-header">
        <h3>写作助手</h3>
        <span class="context-status" aria-live="polite">{{ requestStatus === 'generating' ? '处理中' : '上下文已同步' }}</span>
      </header>

      <nav class="agent-tabs" role="tablist" aria-label="写作助手面板">
        <button type="button" role="tab" :aria-selected="activeTab === 'assistant'" :class="{ active: activeTab === 'assistant' }" @click="activeTab = 'assistant'">写作助手</button>
        <button type="button" role="tab" :aria-selected="activeTab === 'evidence'" :class="{ active: activeTab === 'evidence' }" @click="activeTab = 'evidence'">证据 <span class="tab-count">{{ evidence.length }}</span></button>
      </nav>

      <section v-if="activeTab === 'assistant'" class="assistant-panel">
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
            <span class="message-role">{{ message.role === 'user' ? '你' : '助手' }}</span>
            <p>{{ message.content }}</p>
          </div>
        </div>
        <section v-else class="agent-guidance">
          <strong>{{ context.selectedCharacterCount ? '基于选区协作' : '基于当前章节协作' }}</strong>
          <p v-if="context.selectedCharacterCount">描述你希望如何改写选中的内容，正文只有在你确认建议后才会变化。</p>
          <p v-else>描述你要写的一个段落，助手只使用当前项目已导入、可检索的论文证据。</p>
        </section>

        <section class="quick-actions" aria-labelledby="quick-actions-title">
          <header><strong id="quick-actions-title">快速操作</strong></header>
          <div class="quick-action-grid">
            <button v-for="action in quickActions" :key="action.label" type="button" :disabled="!canSubmit || requestStatus === 'generating'" @click="runQuickAction(action.instruction)">{{ action.label }}</button>
          </div>
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
      </section>

      <section v-else class="evidence-panel" aria-label="项目证据">
        <slot name="evidence">
          <p class="evidence-empty">{{ evidence.length ? '当前项目已保存证据' : '当前项目还没有可用证据' }}</p>
        </slot>
      </section>

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
import { computed, ref } from 'vue'
import type { EvidenceItem } from '@/api/projects'
import type { WritingEditorContext, WritingAgentMessage, WritingAgentStatus, WritingProposal } from '@/stores/writing'
import WritingProposalCard from './WritingProposalCard.vue'
import { IconLeft, IconRight } from '@arco-design/web-vue/es/icon'

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
const activeTab = ref<'assistant' | 'evidence'>('assistant')
const quickActions = computed(() => props.context.selectedCharacterCount ? [
  { label: '学术化润色', instruction: '将选中文字润色为更正式、准确的学术表达，保持原有事实、含义和引用关系，不增加无法验证的新事实。' },
  { label: '精简表达', instruction: '精简选中文字，删除重复和冗余表达，保持原有论点、事实和引用关系不变。' },
  { label: '增强论证', instruction: '增强选中文字的论证连贯性和学术表达；如果需要新增事实性主张，只能使用当前项目已导入论文中的可验证证据。' },
  { label: '保留原意重写', instruction: '在不改变核心含义、事实和引用关系的前提下，重新组织选中文字，使表达更清晰、更自然。' },
] : [
  { label: '根据证据续写一段', instruction: '根据当前章节上下文和项目中已导入、可检索的论文证据，续写一个学术段落。不要编造无法验证的引用。' },
  { label: '整理本节论证结构', instruction: '根据当前章节内容，整理这一节的论证结构，并给出接下来适合写作的一个段落方向。不要直接改写正文。' },
  { label: '查找支持当前章节的证据', instruction: '查找项目中已导入论文里最适合支持当前章节的证据，并基于这些证据生成一个可用于当前章节的段落建议。' },
  { label: '检查当前章节缺少支持的主张', instruction: '检查当前章节上下文中哪些关键主张可能缺少项目论文证据支持，并生成一个包含可验证引用的补充段落建议。' },
])
const submitInstruction = () => {
  const instruction = draft.value.trim()
  if (!instruction || !props.canSubmit || props.requestStatus === 'generating') return
  draft.value = ''
  // The parent owns the API call and request state. This component only owns draft input.
  emit('submit', instruction)
}
const runQuickAction = (instruction: string) => {
  if (!props.canSubmit || props.requestStatus === 'generating') return
  draft.value = ''
  emit('submit', instruction)
}
</script>

<style scoped>
.agent-panel { position: relative; min-width: 0; border-left: 1px solid var(--pa-border); background: var(--pa-surface-soft); }
.agent-panel.collapsed { width: 44px; }
.panel-toggle { position: absolute; z-index: 2; top: 10px; left: -18px; display: grid; place-items: center; min-width: 36px; min-height: 36px; border: 1px solid var(--pa-border); border-radius: 18px; background: var(--pa-surface); color: var(--pa-text); cursor: pointer; box-shadow: var(--pa-shadow-sm); }
.panel-toggle::before { position: absolute; inset: -4px; content: ''; }
.panel-toggle:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.vertical-label { margin-top: 6px; writing-mode: vertical-rl; color: var(--pa-muted); font-size: 11px; letter-spacing: .08em; }
.collapsed .panel-toggle { position: static; margin: 10px 4px; border-radius: var(--pa-radius-sm); }
.agent-content { display: flex; flex-direction: column; height: 100%; min-height: calc(100vh - 112px); padding: 16px 18px 18px; overflow: auto; }
.agent-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }.agent-header h3 { margin: 0; color: var(--pa-ink); font-size: 16px; font-weight: 650; }
.context-status { padding: 4px 8px; border: 1px solid var(--pa-border); border-radius: 999px; color: var(--pa-success); background: var(--pa-surface); font-size: 11px; white-space: nowrap; }
.agent-tabs { display: flex; gap: 18px; margin-top: 16px; border-bottom: 1px solid var(--pa-border); }
.agent-tabs button { position: relative; min-height: 34px; padding: 0 0 9px; border: 0; background: transparent; color: var(--pa-muted); cursor: pointer; font: inherit; font-size: 13px; }
.agent-tabs button::after { position: absolute; right: 0; bottom: -1px; left: 0; height: 2px; background: transparent; content: ''; }
.agent-tabs button.active { color: var(--pa-primary); font-weight: 650; }.agent-tabs button.active::after { background: var(--pa-primary); }.agent-tabs button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }.tab-count { margin-left: 4px; color: var(--pa-muted); font-size: 11px; font-weight: 400; }
.assistant-panel,.evidence-panel { min-height: 0; }.context-card,.agent-guidance { margin-top: 16px; padding: 12px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-md); background: var(--pa-surface); }.context-card > span { color: var(--pa-muted); font-size: 11px; }.context-card > strong { display: block; margin-top: 4px; color: var(--pa-ink); font-size: 13px; font-weight: 650; }.section-path { margin-top: 4px; color: var(--pa-muted); font-size: 11px; line-height: 1.45; }.context-badges { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }.context-badges span { padding: 4px 7px; border-radius: var(--pa-radius-sm); background: var(--pa-primary-soft); color: var(--pa-primary-hover); font-size: 11px; }
.agent-guidance strong { color: var(--pa-ink); font-size: 13px; }.agent-guidance p { margin-top: 6px; color: var(--pa-muted); font-size: 12px; line-height: 1.55; }
.agent-conversation { display: flex; flex-direction: column; gap: 10px; margin-top: 16px; }.agent-message { padding: 10px 12px; border-radius: var(--pa-radius-md); font-size: 12px; line-height: 1.55; }.message-user { align-self: flex-end; max-width: 92%; background: var(--pa-primary-soft); }.message-assistant { align-self: stretch; border: 1px solid var(--pa-border); background: var(--pa-surface); }.message-role { display: block; margin-bottom: 4px; color: var(--pa-muted); font-size: 11px; font-weight: 650; }.agent-message p { white-space: pre-wrap; }
.quick-actions { margin-top: 16px; }.quick-actions > header { margin-bottom: 8px; color: var(--pa-muted); font-size: 11px; font-weight: 650; }.quick-action-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }.quick-action-grid button { min-height: 36px; padding: 7px 9px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-sm); background: var(--pa-surface); color: var(--pa-text); cursor: pointer; font: inherit; font-size: 12px; line-height: 1.35; text-align: left; }.quick-action-grid button:hover:not(:disabled) { border-color: var(--pa-primary); color: var(--pa-primary-hover); }.quick-action-grid button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }.quick-action-grid button:disabled { cursor: not-allowed; opacity: .55; }
.agent-error { margin-top: 16px; padding: 10px 12px; border: 1px solid var(--pa-danger); border-radius: var(--pa-radius-md); background: var(--pa-danger-soft); color: var(--pa-danger); font-size: 12px; line-height: 1.5; }.agent-progress { margin-top: 16px; color: var(--pa-primary-hover); font-size: 12px; }
.evidence-panel { padding-top: 16px; }.evidence-empty { color: var(--pa-muted); font-size: 12px; line-height: 1.55; }
.agent-composer { position: sticky; bottom: 0; margin-top: auto; padding-top: 16px; background: var(--pa-surface-soft); }.agent-composer textarea { display: block; width: 100%; min-height: 80px; resize: vertical; padding: 10px 11px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-md); background: var(--pa-surface); color: var(--pa-text); font: inherit; font-size: 12px; line-height: 1.5; }.agent-composer textarea:focus { border-color: var(--pa-primary); outline: 0; box-shadow: var(--pa-focus-ring); }.agent-composer textarea:disabled { cursor: not-allowed; opacity: .6; }.composer-footer { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 8px; color: var(--pa-muted); font-size: 11px; }.composer-footer button { min-height: 36px; padding: 6px 14px; border: 1px solid var(--pa-primary); border-radius: var(--pa-radius-sm); background: var(--pa-primary); color: white; cursor: pointer; font-size: 12px; }.composer-footer button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }.composer-footer button:disabled { cursor: not-allowed; opacity: .55; }
@media (max-width: 320px) { .quick-action-grid { grid-template-columns: 1fr; } }
@media (max-width: 767px) { .agent-content { min-height: 0; padding-inline: 16px; } }
@media (pointer: coarse) { .panel-toggle { min-width: 44px; min-height: 44px; } }
</style>

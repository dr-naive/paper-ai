<template>
  <div class="project-chat-page">
    <ProductHeader :context="project?.title || '项目对话'" :back-to="`/project/${projectId}`" back-label="项目工作台" />
    <main class="chat-shell">
      <header class="chat-heading">
        <div><span>研究项目 Agent</span><h1>{{ project?.title || '加载项目中' }}</h1></div>
        <p>这里不依赖单篇论文。Agent 可以先检索外部文献，再逐步建立项目文档库、研究证据和论文草稿。</p>
      </header>

      <section ref="messageList" class="message-list" aria-live="polite" aria-label="项目对话消息">
        <div v-if="!loading && messages.length === 0" class="chat-empty">
          <h2>从研究题材开始</h2>
          <p>描述你关心的问题、已有条件和时间范围。也可以直接使用工作台自动带入的下一步指令。</p>
        </div>
        <template v-for="message in messages" :key="message.id">
          <article class="message" :class="`role-${message.role}`">
            <span>{{ message.role === 'user' ? '你' : 'PaperAI' }}</span>
            <div
              v-if="message.role === 'assistant' && message.text"
              class="message-body markdown-answer"
              v-html="renderMarkdown(message.text)"
            />
            <p v-else>{{ message.text || (message.streaming ? '正在思考…' : '') }}</p>
            <div v-if="message.citations?.length" class="message-citations">
              <router-link v-for="citation in message.citations" :key="citationKey(citation)" :to="citationLink(citation)">
                {{ citation.paper_title || citation.title || citation.source_id || '查看来源' }}<template v-if="citation.page"> · 第 {{ citation.page }} 页</template>
              </router-link>
            </div>
          </article>
        </template>
      </section>

      <footer class="composer">
        <div v-if="statusText" class="stream-status">{{ statusText }}</div>
        <a-textarea
          ref="inputRef"
          v-model="question"
          :auto-size="{ minRows: 3, maxRows: 8 }"
          :disabled="sending || loading"
          placeholder="例如：帮我了解这个题材，检索代表性论文并建立领域地图"
          @keydown.ctrl.enter.prevent="sendQuestion"
        />
        <div class="composer-actions">
          <span>Ctrl + Enter 发送</span>
          <a-button type="primary" :loading="sending" :disabled="!question.trim() || loading" @click="sendQuestion">发送给 Agent</a-button>
        </div>
      </footer>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import ProductHeader from '@/components/ProductHeader.vue'
import { renderMarkdown } from '@/utils/markdown'
import { createProjectSession, getProject, type ResearchProject } from '@/api/projects'
import { getSessionMessages, streamAskInSession } from '@/api/paper'

type ChatItem = { id: string; role: 'user' | 'assistant'; text: string; citations?: any[]; streaming?: boolean }
const route = useRoute()
const projectId = computed(() => String(route.params.id || ''))
const project = ref<ResearchProject | null>(null)
const sessionId = ref('')
const messages = ref<ChatItem[]>([])
const question = ref('')
const loading = ref(true)
const sending = ref(false)
const statusText = ref('')
const messageList = ref<HTMLElement | null>(null)
const inputRef = ref<any>(null)

const scrollToBottom = async () => {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}
const citationKey = (item: any) => `${item.paper_id || ''}:${item.page || ''}:${item.source_id || item.title || ''}`
const citationLink = (item: any) => ({ path: `/paper/${item.paper_id}`, query: item.page ? { page: item.page } : undefined })

const load = async () => {
  loading.value = true
  try {
    project.value = await getProject(projectId.value)
    const requestedSession = String(route.query.session || '')
    sessionId.value = requestedSession || (await createProjectSession(projectId.value, `${project.value.title} 对话`)).id
    const history = await getSessionMessages(sessionId.value)
    messages.value = (history.messages || []).flatMap((item: any) => [
      { id: `${item.id}-q`, role: 'user' as const, text: item.question || '' },
      { id: `${item.id}-a`, role: 'assistant' as const, text: item.answer || '', citations: item.citations || [] },
    ])
    question.value = String(route.query.prompt || '')
    await scrollToBottom()
    inputRef.value?.focus?.()
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || error?.message || '加载项目对话失败')
  } finally {
    loading.value = false
  }
}

const sendQuestion = async () => {
  const text = question.value.trim()
  if (!text || sending.value || !sessionId.value) return
  const stamp = Date.now().toString()
  messages.value.push({ id: `${stamp}-q`, role: 'user', text })
  const answer: ChatItem = { id: `${stamp}-a`, role: 'assistant', text: '', citations: [], streaming: true }
  messages.value.push(answer)
  question.value = ''
  sending.value = true
  statusText.value = 'Agent 正在分析项目上下文'
  await scrollToBottom()
  try {
    await streamAskInSession(sessionId.value, text, false, {
      onStatus: data => { statusText.value = data.message || data.stage || '处理中' },
      onDelta: delta => { answer.text += delta; scrollToBottom() },
      onCitations: items => { answer.citations = items },
      onDone: data => {
        if (!answer.text && data?.answer) answer.text = data.answer
        answer.citations = data?.citations || answer.citations
      },
    })
  } catch (error: any) {
    answer.text ||= `请求失败：${error?.message || '请稍后重试'}`
    Message.error(error?.message || 'Agent 回答失败')
  } finally {
    answer.streaming = false
    sending.value = false
    statusText.value = ''
    await scrollToBottom()
  }
}

onMounted(load)
</script>

<style scoped>
.project-chat-page { min-height: 100vh; background: var(--pa-bg); color: var(--pa-text); }
.chat-shell { display: grid; grid-template-rows: auto minmax(320px, 1fr) auto; width: min(960px, calc(100% - 32px)); min-height: calc(100vh - 112px); margin: 24px auto; border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); overflow: hidden; }
.chat-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 32px; padding: 20px 24px; border-bottom: 1px solid var(--pa-border); }
.chat-heading span { color: var(--pa-primary); font-size: 12px; font-weight: 600; }
.chat-heading h1 { margin: 4px 0 0; font-size: 20px; }
.chat-heading p { max-width: 56ch; margin: 0; color: var(--pa-muted); line-height: 1.6; }
.message-list { padding: 24px; overflow-y: auto; }
.chat-empty { max-width: 560px; margin: 64px auto; text-align: center; }
.chat-empty h2 { margin: 0 0 8px; font-size: 20px; }
.chat-empty p { margin: 0; color: var(--pa-muted); line-height: 1.65; }
.message { max-width: 78%; margin-bottom: 20px; }
.message > span { display: block; margin-bottom: 5px; color: var(--pa-muted); font-size: 12px; }
.message > p { margin: 0; padding: 12px 14px; border-radius: 10px; background: var(--pa-surface-soft); line-height: 1.7; white-space: pre-wrap; }
.role-user { margin-left: auto; }
.role-user > span { text-align: right; }
.role-user > p { background: var(--color-primary-light-1); }
.message-body { margin: 0; padding: 14px 16px; border-radius: 10px; background: var(--pa-surface-soft); color: var(--pa-text); line-height: 1.72; overflow-wrap: anywhere; }
.markdown-answer :deep(p) { max-width: 72ch; margin: 0 0 10px; }
.markdown-answer :deep(p:last-child) { margin-bottom: 0; }
.markdown-answer :deep(h2), .markdown-answer :deep(h3), .markdown-answer :deep(h4) { margin: 20px 0 8px; color: var(--pa-text); line-height: 1.4; text-wrap: balance; }
.markdown-answer :deep(h2:first-child), .markdown-answer :deep(h3:first-child) { margin-top: 0; }
.markdown-answer :deep(h2) { font-size: 18px; }
.markdown-answer :deep(h3) { font-size: 16px; }
.markdown-answer :deep(h4) { font-size: 14px; }
.markdown-answer :deep(ul), .markdown-answer :deep(ol) { margin: 8px 0 14px; padding-left: 24px; }
.markdown-answer :deep(li) { margin: 5px 0; }
.markdown-answer :deep(a) { color: var(--pa-primary); font-weight: 600; text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 3px; }
.markdown-answer :deep(a:hover) { color: var(--color-primary-7); }
.markdown-answer :deep(a:focus-visible) { border-radius: 2px; outline: 2px solid var(--pa-primary); outline-offset: 3px; }
.markdown-answer :deep(table) { width: 100%; min-width: 680px; border-collapse: collapse; font-size: 13px; }
.markdown-answer :deep(th), .markdown-answer :deep(td) { padding: 10px 12px; border: 1px solid var(--pa-border); text-align: left; vertical-align: top; }
.markdown-answer :deep(th) { background: var(--pa-surface); font-weight: 650; white-space: nowrap; }
.markdown-answer :deep(tr:nth-child(even) td) { background: var(--pa-bg); }
.markdown-answer :deep(.table-responsive), .markdown-answer { overflow-x: auto; }
.markdown-answer :deep(code) { padding: 2px 5px; border-radius: 4px; background: var(--pa-surface); font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .92em; }
.markdown-answer :deep(hr) { margin: 20px 0; border: 0; border-top: 1px solid var(--pa-border); }
.message-citations { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.message-citations a { padding: 4px 8px; border: 1px solid var(--pa-border); border-radius: 6px; color: var(--pa-primary); font-size: 12px; text-decoration: none; }
.message-citations a:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.composer { padding: 16px 20px; border-top: 1px solid var(--pa-border); background: var(--pa-surface); }
.stream-status { margin-bottom: 8px; color: var(--pa-muted); font-size: 12px; }
.composer-actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 10px; }
.composer-actions span { color: var(--pa-muted); font-size: 12px; }
@media (max-width: 767px) {
  .chat-shell { width: 100%; min-height: calc(100vh - 64px); margin: 0; border-right: 0; border-left: 0; border-radius: 0; }
  .chat-heading { flex-direction: column; gap: 8px; padding: 16px; }
  .message-list { padding: 16px; }
  .message { max-width: 92%; }
  .composer { padding: 12px 16px; }
  .composer-actions .arco-btn { min-height: 44px; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; } }
</style>

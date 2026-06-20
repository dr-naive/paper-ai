<template>
  <div class="qa-page">
    <div class="header">
      <a-button @click="$router.push(`/paper/${id}`)">返回阅读</a-button>
      <h2>论文问答</h2>
    </div>
    <div class="qa-container">
      <div class="qa-content">
        <div v-for="qa in qaHistory" :key="qa.id" class="qa-item">
          <div class="question"><div class="avatar"></div><div class="content"><div class="label">问题</div><div class="text">{{ qa.question }}</div></div></div>
          <div class="answer"><div class="avatar">🤖</div><div class="content"><div class="label">回答</div><a-tag :color="getIntColor(qa.intent)">{{ qa.intent }}</a-tag><div class="text markdown-answer" v-html="renderMarkdown(qa.answer)"></div></div></div>
        </div>
      </div>
      <div class="input-area">
        <a-textarea v-model="question" placeholder="请输入您关于这篇论文的问题" :auto-size="{ minRows: 2, maxRows: 4 }" />
        <div class="input-actions">
          <div class="quick-questions">
            <a-tag v-for="q in quickQuestions" :key="q" clickable @click="question = q">{{ q }}</a-tag>
          </div>
          <a-button type="primary" :loading="loading" @click="handleAsk">提问</a-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { getPaper, askPaperQuestion } from '@/api/paper'
import { renderMarkdown } from '@/utils/markdown'

const route = useRoute()
const id = route.params.id as string
const loading = ref(false)
const paper = ref<any>(null)
const question = ref('')
const qaHistory = ref<any[]>([])
const quickQuestions = ['这篇论文的主要贡献是什么？', '论文使用的主要方法是什么？', '实验结果如何？', '论文的创新性有哪些？']

const loadPaper = async () => { try { paper.value = await getPaper(id) } catch (error) { } }

const handleAsk = async () => {
  if (!question.value.trim()) { Message.warning('请输入问题'); return }
  loading.value = true
  try {
    const response = await askPaperQuestion(id, question.value)
    qaHistory.value.push({ id: response.qa_id, question: question.value, answer: response.answer, intent: response.intent, confidence: response.confidence, sources: response.sources })
    question.value = ''
    Message.success('回答已生成')
  } catch (error) { } finally { loading.value = false }
}

const getIntColor = (intent: string) => {
  const colors: Record<string, string> = { concept: 'green', method: 'blue', experiment: 'orange', code: 'purple', general: 'gray' }
  return colors[intent] || 'gray'
}

onMounted(() => { loadPaper() })
</script>

<style scoped>
.qa-page { height: 100vh; display: flex; flex-direction: column; background: #f5f5f5; }
.header { display: flex; align-items: center; padding: 12px 24px; background: white; border-bottom: 1px solid #e5e6eb; }
.header h2 { flex: 1; text-align: center; margin: 0; }
.qa-container { flex: 1; display: flex; overflow: hidden; }
.qa-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.qa-list { flex: 1; overflow-y: auto; padding: 24px; }
.qa-item { margin-bottom: 24px; }
.question, .answer { display: flex; gap: 12px; margin-bottom: 16px; }
.avatar { width: 40px; height: 40px; border-radius: 50%; background: #f0f0f0; display: flex; align-items: center; justify-content: center; font-size: 20px; }
.content { flex: 1; }
.label { font-size: 12px; color: #999; margin-bottom: 4px; }
.text { padding: 16px; background: white; border-radius: 8px; line-height: 1.6; }
.question .text { background: #f5f5f5; }
.markdown-answer { overflow-x: auto; overflow-wrap: anywhere; }
.markdown-answer :deep(p) { margin: 0 0 10px; }
.markdown-answer :deep(ul), .markdown-answer :deep(ol) { margin: 6px 0 10px; padding-left: 24px; }
.markdown-answer :deep(li) { margin: 4px 0; }
.markdown-answer :deep(table) { width: max-content; min-width: 100%; border-collapse: collapse; font-size: 13px; }
.markdown-answer :deep(th), .markdown-answer :deep(td) { padding: 8px 10px; border: 1px solid #d9dde5; white-space: nowrap; text-align: left; }
.markdown-answer :deep(th) { background: #f2f3f5; }
.markdown-answer :deep(tr:nth-child(even) td) { background: #fafbfc; }
.input-area { padding: 24px; background: white; border-top: 1px solid #e5e6eb; }
.input-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 12px; }
.quick-questions { display: flex; gap: 8px; flex-wrap: wrap; }
</style>

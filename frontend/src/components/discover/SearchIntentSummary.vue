<template>
  <section class="intent-card" aria-labelledby="intent-title">
    <div class="card-heading">
      <div>
        <p class="section-label">Search intent</p>
        <h2 id="intent-title">搜索需求</h2>
      </div>
      <span v-if="disabled" class="intent-lock">搜索进行中</span>
    </div>

    <label for="intent-topic">自然语言检索需求</label>
    <a-textarea
      id="intent-topic"
      :model-value="intent.topic"
      :disabled="disabled"
      :auto-size="{ minRows: 3, maxRows: 6 }"
      @update:model-value="updateTopic"
    />

    <div class="intent-grid">
      <div class="field-block field-block--wide">
        <label for="intent-question">研究问题（可选）</label>
        <a-textarea
          id="intent-question"
          :model-value="intent.research_question || ''"
          :disabled="disabled"
          :auto-size="{ minRows: 2, maxRows: 4 }"
          placeholder="希望比较、解释或验证什么？"
          @update:model-value="updateQuestion"
        />
      </div>
      <div class="field-block">
        <label for="intent-keywords">关键词</label>
        <a-input id="intent-keywords" :model-value="intent.keywords.join(', ')" :disabled="disabled" placeholder="用逗号分隔" @update:model-value="updateKeywords" />
      </div>
      <div class="field-block">
        <label for="intent-methods">方法 / 技术方向</label>
        <a-input id="intent-methods" :model-value="intent.preferred_methods.join(', ')" :disabled="disabled" placeholder="用逗号分隔" @update:model-value="updateMethods" />
      </div>
      <div class="field-block">
        <label for="intent-contexts">研究对象 / 场景</label>
        <a-input id="intent-contexts" :model-value="intent.target_contexts.join(', ')" :disabled="disabled" placeholder="用逗号分隔" @update:model-value="updateContexts" />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { SearchIntent } from '@/api/discovery'

defineProps<{
  intent: SearchIntent
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:intent': [value: Partial<SearchIntent>]
}>()

const splitTerms = (value: string) => value.split(/[,，]/).map(item => item.trim()).filter(Boolean)
const updateTopic = (value: string) => emit('update:intent', { topic: value })
const updateQuestion = (value: string) => emit('update:intent', { research_question: value.trim() || null })
const updateKeywords = (value: string) => emit('update:intent', { keywords: splitTerms(value) })
const updateMethods = (value: string) => emit('update:intent', { preferred_methods: splitTerms(value) })
const updateContexts = (value: string) => emit('update:intent', { target_contexts: splitTerms(value) })

</script>

<style scoped>
.intent-card { padding: 24px 26px 26px; border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); }
.card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.section-label { margin: 0 0 6px; color: var(--pa-primary-hover); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.card-heading h2 { margin: 0; color: var(--pa-ink); font-size: 19px; line-height: 1.3; }
.intent-lock { padding: 4px 8px; border-radius: 999px; background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 12px; }
label { display: block; margin-bottom: 7px; color: var(--pa-text); font-size: 12px; font-weight: 650; }
.intent-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; margin-top: 16px; }
.field-block--wide { grid-column: 1 / -1; }
@media (max-width: 680px) { .intent-card { padding: 20px 18px; } .intent-grid { grid-template-columns: 1fr; gap: 14px; } .field-block--wide { grid-column: auto; } }
</style>

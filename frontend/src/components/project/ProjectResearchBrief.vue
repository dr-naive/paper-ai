<template>
  <a-spin :loading="loading">
    <div v-if="!artifact" class="empty-state">
      <h3>先把模糊兴趣变成可执行调研任务</h3>
      <p>让研究助手区分已知背景、用户约束和待验证假设，并产出中英文关键词、检索式、纳入排除标准与选题评价准则。</p>
      <a-button type="primary" @click="emit('clarify')">和研究助手澄清题材</a-button>
    </div>
    <article v-else class="research-document" aria-label="研究任务书">
      <header><div><span>当前版本 v{{ artifact.version }}</span><h2>{{ artifact.title }}</h2><p><strong>{{ content.topic }}</strong></p><p>{{ content.objective }}</p></div><a-button size="small" @click="emit('open', artifact)">查看完整产物</a-button></header>
      <div v-if="content.seed_keywords.length" class="keywords"><a-tag v-for="keyword in content.seed_keywords" :key="keyword">{{ keyword }}</a-tag></div>
      <div class="columns"><section><h3>已知背景</h3><ul><li v-for="item in content.known_context" :key="item">{{ item }}</li></ul><p v-if="!content.known_context.length" class="muted">尚无用户确认的背景。</p></section><section><h3>现实约束</h3><ul><li v-for="item in content.constraints" :key="item">{{ item }}</li></ul><p v-if="!content.constraints.length" class="muted">尚未明确资源与时间约束。</p></section></div>
      <section><h3>待确认与待验证</h3><ul><li v-for="item in content.unknowns" :key="item">{{ item }}</li></ul><p v-if="!content.unknowns.length" class="muted">当前没有登记的未知项。</p></section>
      <section><h3>可执行检索式</h3><ol class="queries"><li v-for="query in content.search_queries" :key="query"><code>{{ query }}</code></li></ol></section>
      <div class="columns"><section><h3>纳入标准</h3><ul><li v-for="item in content.inclusion_criteria" :key="item">{{ item }}</li></ul></section><section><h3>排除标准</h3><ul><li v-for="item in content.exclusion_criteria" :key="item">{{ item }}</li></ul></section></div>
      <section><h3>选题评价准则</h3><ul><li v-for="item in content.evaluation_criteria" :key="item">{{ item }}</li></ul></section>
    </article>
  </a-spin>
</template>

<script setup lang="ts">
import type { ResearchBriefContent, WritingArtifactItem } from '@/api/projects'
defineProps<{ artifact: WritingArtifactItem | null; content: ResearchBriefContent; loading: boolean }>()
const emit = defineEmits<{ clarify: []; open: [artifact: WritingArtifactItem] }>()
</script>

<style scoped>
.empty-state { max-width: 680px; margin: 0 auto; padding: 48px 24px; color: var(--pa-muted); text-align: center; }.empty-state h3 { margin: 0 0 8px; color: var(--pa-text); font-size: 20px; }.empty-state p { margin: 0 0 20px; line-height: 1.7; }.research-document { display: flex; flex-direction: column; gap: 24px; }.research-document header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }.research-document header span { color: var(--pa-muted); font-size: 12px; }.research-document h2 { margin: 4px 0 8px; font-size: 24px; }.research-document header p { max-width: 72ch; margin: 0; color: var(--pa-muted); line-height: 1.7; }.research-document section h3 { margin: 0 0 12px; font-size: 17px; }.research-document ul { margin: 0; padding-left: 22px; }.research-document li { margin: 6px 0; line-height: 1.55; }.keywords { display: flex; flex-wrap: wrap; gap: 8px; }.columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; }.queries { display: grid; gap: 8px; margin: 0; padding-left: 24px; }.queries li { padding: 10px 12px; border-bottom: 1px solid var(--pa-border); }.queries code { white-space: normal; overflow-wrap: anywhere; color: var(--pa-text); }.muted { color: var(--pa-muted); }@media (max-width: 767px) { .research-document header { flex-direction: column; }.columns { grid-template-columns: 1fr; } }
</style>

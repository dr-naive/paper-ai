<template>
  <article class="proposal-card" :data-proposal-status="proposal.status" aria-label="AI 写作建议">
    <header class="proposal-header">
      <div>
        <strong>AI 建议</strong>
        <span class="proposal-kind">{{ proposal.kind === 'rewrite' ? '选区改写' : '段落草稿' }}</span>
      </div>
      <button type="button" class="proposal-dismiss" aria-label="关闭写作建议" @click="$emit('dismiss')"><IconClose aria-hidden="true" /></button>
    </header>

    <div class="proposal-status" :class="`status-${proposal.status}`" role="status">
      <IconCheck v-if="proposal.status === 'ready'" aria-hidden="true" />
      <IconExclamationCircle v-else-if="proposal.status === 'partially_verified'" aria-hidden="true" />
      <IconCloseCircle v-else aria-hidden="true" />
      <span>{{ statusLabel }}</span>
    </div>

    <p class="proposal-text"> <template v-for="(segment, index) in segments" :key="`${segment.type}-${index}`"><span v-if="segment.type === 'text'">{{ segment.text }}</span><button v-else type="button" class="citation-token" :class="`citation-${segment.citation?.status || 'unsupported'}`" :aria-label="`查看引用 ${segment.text} 的证据详情`" @click="toggleCitation(segment.text)">{{ citationLabel(segment.text) }}</button></template></p>

    <section v-if="activeCitation" class="citation-detail" aria-live="polite">
      <header><strong>{{ activeCitation.citation_key }}</strong><button type="button" aria-label="关闭证据详情" @click="activeCitation = null"><IconClose aria-hidden="true" /></button></header>
      <p class="citation-source">{{ sourceTitle(activeCitation) }}<template v-if="sourcePage(activeCitation)"> · 第 {{ sourcePage(activeCitation) }} 页</template></p>
      <p v-if="activeCitation.evidence_snippet" class="citation-snippet">{{ activeCitation.evidence_snippet }}</p>
      <p v-if="normalizedClaim(activeCitation)" class="citation-normalized-claim">规范化主张：{{ normalizedClaim(activeCitation) }}</p>
      <p class="citation-claim">主张：{{ activeCitation.claim_text || activeCitation.original_claim }}</p>
      <p class="citation-reason">{{ statusLabelFor(activeCitation.status) }}：{{ activeCitation.reason }}</p>
      <a v-if="activeCitation.paper_id" :href="paperHref(activeCitation.paper_id)" target="_blank" rel="noopener">查看论文来源</a>
    </section>

    <section v-if="citations.length" class="citation-list" aria-label="建议中的引用">
      <h4>引用</h4>
      <button v-for="citation in citations" :key="citation.citation_key" type="button" class="citation-row" @click="toggleCitation(citation.citation_key)">
        <span class="citation-row-key">{{ citationLabel(citation.citation_key) }}</span>
        <span class="citation-row-source">{{ sourceTitle(citation) }}</span>
        <span class="citation-row-status" :class="`status-${citation.status}`">
          <IconCheck v-if="citation.status === 'verified'" aria-hidden="true" />
          <IconExclamationCircle v-else-if="citation.status === 'weak'" aria-hidden="true" />
          <IconCloseCircle v-else aria-hidden="true" />
          {{ statusLabelFor(citation.status) }}
        </span>
      </button>
    </section>

    <ul v-if="proposal.warnings.length" class="proposal-warnings" aria-label="写作建议提醒">
      <li v-for="warning in proposal.warnings" :key="warning">{{ warning }}</li>
    </ul>

    <footer class="proposal-actions">
      <button v-if="proposal.kind === 'rewrite'" type="button" class="proposal-primary" :disabled="replaceDisabled" :title="replaceDisabled ? replaceDisabledReason : undefined" @click="$emit('replace')">替换选中内容</button>
      <button type="button" class="proposal-secondary" @click="$emit('copy')">复制</button>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { CitationVerificationResult, WritingGenerationProposal, WritingRewriteProposal } from '@/api/documents'
import type { EvidenceItem } from '@/api/projects'
import { proposalSegments } from '@/utils/writingProposal'
import { projectReaderPath } from '@/router/reader'
import { IconCheck, IconClose, IconCloseCircle, IconExclamationCircle } from '@arco-design/web-vue/es/icon'

const props = defineProps<{
  proposal: WritingRewriteProposal | WritingGenerationProposal
  evidence: EvidenceItem[]
  replaceDisabled: boolean
  replaceDisabledReason: string
  projectId: string
}>()
defineEmits<{ copy: []; replace: []; dismiss: [] }>()

const activeCitationKey = ref('')
const citations = computed(() => props.proposal.citations || [])
const segments = computed(() => proposalSegments(props.proposal.content, citations.value))
const activeCitation = computed(() => citations.value.find(item => item.citation_key === activeCitationKey.value) || null)
const statusLabelFor = (status: CitationVerificationResult['status']) => ({ verified: '已验证', weak: '证据较弱', unsupported: '不支持' }[status])
const statusLabel = computed(() => props.proposal.status === 'ready' ? '引用已验证' : props.proposal.status === 'partially_verified' ? '部分引用证据较弱' : '存在未支持引用')
const citationLabel = (key: string) => {
  const index = citations.value.findIndex(item => item.citation_key === key)
  return `[${index >= 0 ? index + 1 : key}]`
}
const toggleCitation = (key: string) => { activeCitationKey.value = activeCitationKey.value === key ? '' : key }
const sourceTitle = (citation: CitationVerificationResult) => {
  const evidence = props.evidence.find(item => item.id === citation.evidence_id)
  return evidence?.source_title || `论文 ${citation.paper_id}`
}
const sourcePage = (citation: CitationVerificationResult) => props.evidence.find(item => item.id === citation.evidence_id)?.page_number
const normalizedClaim = (citation: CitationVerificationResult) => props.evidence.find(item => item.id === citation.evidence_id)?.normalized_claim || ''
const paperHref = (paperId: string) => projectReaderPath(props.projectId, paperId)
</script>

<style scoped>
.proposal-card { margin-top: 16px; padding: 16px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-md); background: var(--pa-surface); box-shadow: var(--pa-shadow-sm); }
.proposal-header,.citation-detail header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.proposal-header strong { display: block; color: var(--pa-ink); font-size: 14px; font-weight: 650; }.proposal-kind { display: block; margin-top: 3px; color: var(--pa-muted); font-size: 12px; }
.proposal-dismiss,.citation-detail header button { display: inline-grid; place-items: center; min-width: 32px; min-height: 32px; border: 0; border-radius: var(--pa-radius-sm); background: transparent; color: var(--pa-muted); cursor: pointer; }
.proposal-dismiss:hover,.citation-detail header button:hover { background: var(--pa-primary-soft); color: var(--pa-primary-hover); }
.proposal-dismiss:focus-visible,.citation-detail header button:focus-visible,.citation-token:focus-visible,.citation-row:focus-visible,.proposal-actions button:focus-visible { outline: 2px solid var(--pa-primary); outline-offset: 2px; }
.proposal-status { display: inline-flex; align-items: center; gap: 6px; margin-top: 14px; padding: 5px 9px; border-radius: 999px; background: var(--pa-success-soft); color: var(--pa-success); font-size: 11px; }
.proposal-status.status-partially_verified { background: var(--pa-warning-soft); color: var(--pa-warning); }
.proposal-status.status-verification_failed { background: var(--pa-danger-soft); color: var(--pa-danger); }
.proposal-text { margin: 14px 0; color: var(--pa-text); font-size: 14px; line-height: 1.75; white-space: pre-wrap; }
.citation-token { display: inline; padding: 1px 4px; border: 1px solid var(--pa-border); border-radius: 4px; background: var(--pa-primary-soft); color: var(--pa-primary-hover); cursor: pointer; font: inherit; }
.citation-token.citation-weak { border-color: var(--pa-warning); background: var(--pa-warning-soft); color: var(--pa-warning); }
.citation-token.citation-unsupported { border-color: var(--pa-danger); background: var(--pa-danger-soft); color: var(--pa-danger); }
.citation-detail { margin: 10px 0; padding: 12px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-sm); background: var(--pa-surface-soft); font-size: 12px; line-height: 1.55; }
.citation-source { margin-top: 5px; font-weight: 650; }.citation-snippet,.citation-normalized-claim,.citation-claim,.citation-reason { margin-top: 7px; color: var(--pa-text); }.citation-reason { color: var(--pa-muted); }.citation-detail a { display: inline-block; margin-top: 8px; color: var(--pa-primary-hover); }
.citation-list { margin-top: 12px; }.citation-list h4 { margin-bottom: 6px; color: var(--pa-muted); font-size: 12px; font-weight: 650; }
.citation-row { display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: 8px; width: 100%; min-height: 36px; padding: 7px 0; border: 0; border-bottom: 1px solid var(--pa-border); background: transparent; color: var(--pa-text); cursor: pointer; text-align: left; font-size: 12px; }
.citation-row-key { color: var(--pa-primary-hover); font-weight: 650; }.citation-row-source { overflow: hidden; color: var(--pa-muted); text-overflow: ellipsis; white-space: nowrap; }.citation-row-status { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }.citation-row-status.status-verified { color: var(--pa-success); }.citation-row-status.status-weak { color: var(--pa-warning); }.citation-row-status.status-unsupported { color: var(--pa-danger); }
.proposal-warnings { margin: 12px 0 0; padding: 9px 10px 9px 26px; border-radius: var(--pa-radius-sm); background: var(--pa-danger-soft); color: var(--pa-danger); font-size: 12px; line-height: 1.5; }
.proposal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }.proposal-actions button { min-height: 36px; padding: 6px 12px; border-radius: var(--pa-radius-sm); cursor: pointer; font-size: 12px; }.proposal-primary { border: 1px solid var(--pa-primary); background: var(--pa-primary); color: white; }.proposal-secondary { border: 1px solid var(--pa-border); background: var(--pa-surface); color: var(--pa-text); }.proposal-actions button:disabled { cursor: not-allowed; opacity: .55; }
</style>

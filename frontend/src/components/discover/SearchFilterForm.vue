<template>
  <section class="filter-card" aria-labelledby="filter-title">
    <div class="card-heading">
      <div>
        <p class="section-label">Structured filters</p>
        <h2 id="filter-title">筛选条件</h2>
      </div>
      <span class="filter-note">支持这些条件的检索服务会按所选条件筛选</span>
    </div>

    <div class="filter-grid">
      <div class="field-block">
        <label for="filter-year-from">起始年份</label>
        <input id="filter-year-from" class="native-field" type="number" :value="filters.year_from ?? ''" :disabled="disabled" min="1800" max="2200" placeholder="例如 2018" @input="updateYearFrom" />
      </div>
      <div class="field-block">
        <label for="filter-year-to">结束年份</label>
        <input id="filter-year-to" class="native-field" type="number" :value="filters.year_to ?? ''" :disabled="disabled" min="1800" max="2200" placeholder="例如 2026" @input="updateYearTo" />
      </div>
      <div class="field-block">
        <label for="filter-language">语言</label>
        <a-select id="filter-language" :model-value="filters.language || undefined" :disabled="disabled" allow-clear placeholder="不限语言" @update:model-value="updateLanguage">
          <a-option value="en">English</a-option>
          <a-option value="zh">中文</a-option>
          <a-option value="ja">日本語</a-option>
          <a-option value="ko">한국어</a-option>
        </a-select>
      </div>
      <div class="field-block">
        <label for="filter-fields">学科领域</label>
        <a-select id="filter-fields" :model-value="filters.fields" multiple allow-clear :disabled="disabled" placeholder="不限领域" @update:model-value="updateFields">
          <a-option v-for="field in fieldOptions" :key="field" :value="field">{{ field }}</a-option>
        </a-select>
      </div>
      <div class="field-block field-block--wide">
        <label for="filter-publication-types">文献类型</label>
        <a-select id="filter-publication-types" :model-value="filters.publication_types" multiple allow-clear :disabled="disabled" placeholder="不限类型" @update:model-value="updatePublicationTypes">
          <a-option v-for="type in publicationTypeOptions" :key="type.value" :value="type.value">{{ type.label }}</a-option>
        </a-select>
      </div>
    </div>

    <p v-if="validationError" class="filter-error" role="alert">{{ validationError }}</p>
    <div class="filter-footer">
      <span>最多返回 10 篇真实论文，结果不足时会如实返回。</span>
      <a-button type="primary" :loading="disabled" :disabled="disabled || Boolean(validationError)" @click="submit">搜索论文</a-button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { SearchFilters } from '@/api/discovery'

const props = defineProps<{
  filters: SearchFilters
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:filters': [value: Partial<SearchFilters>]
  search: []
}>()

const fieldOptions = ['Computer Science', 'Education', 'Medicine', 'Psychology', 'Social Sciences', 'Engineering']
const publicationTypeOptions = [
  { value: 'JournalArticle', label: '期刊论文' },
  { value: 'Conference', label: '会议论文' },
  { value: 'Review', label: '综述' },
  { value: 'Dataset', label: '数据集' },
]

const parseYear = (value: string | number) => {
  const text = String(value ?? '').trim()
  if (!text) return null
  const year = Number(text)
  return Number.isFinite(year) ? year : null
}

const inputValue = (event: Event) => (event.target as HTMLInputElement).value
const updateYearFrom = (event: Event) => emit('update:filters', { year_from: parseYear(inputValue(event)) })
const updateYearTo = (event: Event) => emit('update:filters', { year_to: parseYear(inputValue(event)) })
const updateLanguage = (value: unknown) => emit('update:filters', { language: typeof value === 'string' ? value || null : null })
const selectValues = (value: unknown) => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
const updateFields = (value: unknown) => emit('update:filters', { fields: selectValues(value) })
const updatePublicationTypes = (value: unknown) => emit('update:filters', { publication_types: selectValues(value) })

const validationError = computed(() => {
  if (props.filters.year_from && props.filters.year_to && props.filters.year_from > props.filters.year_to) return '起始年份不能晚于结束年份。'
  if (props.filters.year_from && (props.filters.year_from < 1800 || props.filters.year_from > 2200)) return '年份应在 1800 到 2200 之间。'
  if (props.filters.year_to && (props.filters.year_to < 1800 || props.filters.year_to > 2200)) return '年份应在 1800 到 2200 之间。'
  return ''
})

const submit = () => {
  if (!validationError.value) emit('search')
}
</script>

<style scoped>
.filter-card { padding: 20px; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface); }
.card-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
.section-label { margin: 0 0 6px; color: var(--pa-primary-hover); font-size: 11px; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.card-heading h2 { margin: 0; color: var(--pa-ink); font-size: 18px; font-weight: 650; line-height: 1.3; }
.filter-note, .filter-footer span { color: var(--pa-muted); font-size: 12px; line-height: 1.5; }
.filter-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.field-block--wide { grid-column: 1 / -1; }
label { display: block; margin-bottom: 7px; color: var(--pa-text); font-size: 12px; font-weight: 600; }
.native-field { box-sizing: border-box; width: 100%; min-height: 36px; padding: 7px 11px; border: 1px solid var(--pa-border); border-radius: var(--pa-radius-sm); background: var(--pa-surface); color: var(--pa-text); font: inherit; font-size: 13px; }
.native-field:focus { border-color: var(--pa-primary); outline: 2px solid color-mix(in srgb, var(--pa-primary) 22%, transparent); outline-offset: 1px; }
.native-field:disabled { background: var(--pa-surface-soft); color: var(--pa-muted); cursor: not-allowed; }
.filter-error { margin: 14px 0 0; color: var(--pa-danger); font-size: 12px; }
.filter-footer { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-top: 20px; }
@media (max-width: 680px) { .filter-card { padding: 18px; } .card-heading, .filter-footer { align-items: stretch; flex-direction: column; } .filter-grid { grid-template-columns: 1fr; gap: 14px; } .field-block--wide { grid-column: auto; } .filter-footer .arco-btn { width: 100%; } }
</style>

<template>
  <span class="brand-mark">
    <svg :width="size" :height="size" viewBox="0 0 32 32" aria-hidden="true">
      <rect x="2" y="2" width="28" height="28" rx="8" fill="var(--pa-primary)" />
      <path d="M10 10h12M10 16h8M10 22h10" stroke="white" stroke-width="2" stroke-linecap="round" />
    </svg>
    <span v-if="showName" class="brand-mark__name">PaperAI</span>
  </span>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  size?: number
  showName?: boolean
}>(), {
  size: 28,
  showName: true
})
</script>

<style scoped>
.brand-mark {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: inherit;
  line-height: 1;
}

.brand-mark svg { flex-shrink: 0; }

.brand-mark__name {
  font-size: inherit;
  font-weight: 700;
  letter-spacing: -0.02em;
}
</style>

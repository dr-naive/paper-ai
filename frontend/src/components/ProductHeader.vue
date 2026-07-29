<template>
  <header class="product-header" :class="{ 'product-header--edge': edge }">
    <div v-if="$slots.leading" class="product-header__leading">
      <slot name="leading" />
    </div>

    <button class="product-header__brand" type="button" @click="router.push('/home')" aria-label="返回 PaperAI 首页">
      <BrandMark :size="28" />
    </button>

    <template v-if="backTo || context || $slots.navigation">
      <span class="product-header__divider" aria-hidden="true"></span>
      <button
        v-if="backTo"
        class="product-header__back"
        type="button"
        :aria-label="`返回${backLabel}`"
        :title="`返回${backLabel}`"
        @click="router.push(backTo)"
      >
        <span class="product-header__back-icon" aria-hidden="true">←</span>
        <span>{{ backLabel }}</span>
      </button>
      <span
        v-if="backTo && context"
        class="product-header__sub-divider"
        aria-hidden="true"
      ></span>
      <span v-if="context" class="product-header__context">{{ context }}</span>
      <div v-if="$slots.navigation" class="product-header__navigation">
        <slot name="navigation" />
      </div>
    </template>

    <div class="product-header__main"><slot /></div>
    <div v-if="$slots.actions" class="product-header__actions"><slot name="actions" /></div>
  </header>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import BrandMark from './BrandMark.vue'

withDefaults(defineProps<{
  context?: string
  edge?: boolean
  backTo?: string
  backLabel?: string
}>(), {
  edge: false,
  backTo: '',
  backLabel: '上一页',
})
const router = useRouter()
</script>

<style scoped>
.product-header {
  display: flex;
  align-items: center;
  min-height: 60px;
  padding: 10px max(24px, calc((100vw - 1440px) / 2));
  border-bottom: 1px solid var(--pa-border);
  background: var(--pa-surface);
  color: var(--pa-ink);
}

.product-header--edge {
  padding-left: 8px;
  padding-right: 20px;
}

.product-header__brand {
  flex-shrink: 0;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font-size: 19px;
  cursor: pointer;
}

.product-header__back {
  display: inline-flex;
  min-height: 36px;
  padding: 0 8px;
  flex: none;
  align-items: center;
  gap: 8px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--pa-muted);
  font-size: 13px;
  cursor: pointer;
  transition: color 180ms ease-out, background-color 180ms ease-out;
}

.product-header__back-icon {
  font-size: 20px;
  line-height: 1;
}

.product-header__back:hover {
  color: var(--pa-ink);
  background: var(--pa-surface-soft);
}

.product-header__back:active {
  background: var(--pa-border);
}

.product-header__back:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

.product-header__leading {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  margin-right: 16px;
}

.product-header__brand:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 4px;
}

.product-header__divider {
  width: 1px;
  height: 24px;
  margin: 0 12px;
  background: var(--pa-border);
}

.product-header__sub-divider {
  width: 1px;
  height: 18px;
  margin: 0 12px;
  flex: none;
  background: var(--pa-border);
}

.product-header__context {
  flex-shrink: 0;
  color: var(--pa-ink);
  font-size: 15px;
  font-weight: 600;
}

.product-header__navigation {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.product-header__main {
  flex: 1;
  min-width: 0;
}

.product-header__back + .product-header__main,
.product-header__context + .product-header__main,
.product-header__navigation + .product-header__main {
  margin-left: 24px;
}

.product-header__actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  margin-left: 16px;
}

@media (max-width: 760px) {
  .product-header { padding-inline: 14px; }
  .product-header--edge { padding-left: 4px; }
  .product-header__leading { margin-right: 8px; }
  .product-header__brand :deep(.brand-mark__name) { display: none; }
  .product-header__divider { margin-inline: 8px; }
}

@media (pointer: coarse) {
  .product-header__back {
    min-height: 44px;
  }
}
</style>

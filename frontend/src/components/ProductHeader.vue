<template>
  <header class="product-header" :class="{ 'product-header--edge': edge }">
    <div v-if="$slots.leading" class="product-header__leading">
      <slot name="leading" />
    </div>

    <button class="product-header__brand" type="button" @click="router.push('/home')" aria-label="返回 PaperAI 首页">
      <BrandMark :size="28" />
    </button>

    <template v-if="context || $slots.navigation">
      <span class="product-header__divider" aria-hidden="true"></span>
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

withDefaults(defineProps<{ context?: string; edge?: boolean }>(), {
  edge: false,
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

.product-header__context {
  flex-shrink: 0;
  color: var(--pa-muted);
  font-size: 13px;
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
</style>

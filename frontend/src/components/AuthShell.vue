<template>
  <div class="auth-shell">
    <header class="auth-shell__header">
      <button type="button" class="auth-shell__brand" @click="router.push('/home')" aria-label="返回 PaperAI 首页">
        <BrandMark :size="30" />
      </button>
      <button type="button" class="auth-shell__home" @click="router.push('/home')">返回首页</button>
    </header>

    <main class="auth-shell__main">
      <section class="auth-shell__panel" :aria-labelledby="props.headingId">
        <div class="auth-shell__heading">
          <span class="auth-shell__label">PaperAI 论文工作台</span>
          <h1 :id="props.headingId">{{ props.title }}</h1>
          <p>{{ props.subtitle }}</p>
        </div>
        <div class="auth-shell__content"><slot /></div>
        <footer v-if="$slots.footer" class="auth-shell__footer"><slot name="footer" /></footer>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import BrandMark from './BrandMark.vue'

const props = withDefaults(defineProps<{
  title: string
  subtitle: string
  headingId?: string
}>(), {
  headingId: 'auth-heading'
})

const router = useRouter()
</script>

<style scoped>
.auth-shell {
  min-height: 100vh;
  background: var(--pa-bg);
  color: var(--pa-ink);
}

.auth-shell__header {
  display: flex;
  align-items: center;
  min-height: 64px;
  padding: 12px max(24px, calc((100vw - 1120px) / 2));
}

.auth-shell__brand,
.auth-shell__home {
  border: 0;
  background: transparent;
  color: var(--pa-ink);
  cursor: pointer;
}

.auth-shell__brand { font-size: 19px; }

.auth-shell__home {
  margin-left: auto;
  padding: 8px 10px;
  border-radius: 6px;
  color: var(--pa-text);
  font-size: 14px;
}

.auth-shell__home:hover {
  background: var(--pa-primary-soft);
  color: var(--pa-primary-hover);
}

.auth-shell__brand:focus-visible,
.auth-shell__home:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 3px;
}

.auth-shell__main {
  display: grid;
  min-height: calc(100vh - 64px);
  place-items: center;
  padding: 36px 24px 64px;
}

.auth-shell__panel {
  width: min(100%, 440px);
  padding: 38px 40px 34px;
  border: 1px solid var(--pa-border);
  border-radius: 14px;
  background: var(--pa-surface);
  box-shadow: 0 18px 50px oklch(0.35 0.02 45 / 0.08);
}

.auth-shell__heading { margin-bottom: 30px; }

.auth-shell__label {
  display: block;
  margin-bottom: 10px;
  color: var(--pa-primary-hover);
  font-size: 13px;
  font-weight: 600;
}

.auth-shell__heading h1 {
  margin: 0 0 8px;
  color: var(--pa-ink);
  font-size: 28px;
  line-height: 1.2;
  letter-spacing: -0.025em;
}

.auth-shell__heading p {
  margin: 0;
  color: var(--pa-muted);
  font-size: 14px;
  line-height: 1.65;
}

.auth-shell__content :deep(.arco-form-item) { margin-bottom: 20px; }
.auth-shell__content :deep(.arco-form-item:last-child) { margin-bottom: 0; }

.auth-shell__footer {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--pa-border);
  color: var(--pa-muted);
  text-align: center;
  font-size: 14px;
}

.auth-shell__footer :slotted(.auth-link) {
  border: 0;
  padding: 2px 4px;
  background: transparent;
  color: var(--pa-primary-hover);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.auth-shell__footer :slotted(.auth-link:hover) { text-decoration: underline; }
.auth-shell__footer :slotted(.auth-link:focus-visible) {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

@media (max-width: 520px) {
  .auth-shell__header { padding-inline: 16px; }
  .auth-shell__main { align-items: start; padding: 20px 14px 40px; }
  .auth-shell__panel { padding: 30px 22px 28px; }
}
</style>

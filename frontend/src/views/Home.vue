<template>
  <div class="home-page">
    <!-- 背景图片轮播 -->
    <div class="page-background">
      <div class="bg-slideshow">
        <div
          v-for="(bg, i) in backgrounds"
          :key="i"
          class="bg-slide"
          :class="{ active: currentBgIndex === i }"
          :style="{ backgroundImage: `url('/images/${bg}')` }"
        ></div>
      </div>
      <div class="bg-overlay"></div>
    </div>

    <header class="top-nav" :class="{ scrolled: isScrolled }">
      <div class="nav-brand">
        <BrandMark :size="28" />
      </div>
      <div class="nav-right">
        <div v-if="isLoggedIn" class="user-info" @click="showDropdown = !showDropdown">
          <a-avatar :size="32" :style="{ backgroundColor: 'oklch(0.50 0.16 45)' }">
            {{ userInitial }}
          </a-avatar>
          <span class="username">{{ currentUser?.username }}</span>
          <a-dropdown v-model:popup-visible="showDropdown" trigger="click" position="br">
            <a-button class="dropdown-trigger" size="mini">
              <template #icon><icon-down /></template>
            </a-button>
            <template #content>
              <a-doption @click="$router.push('/papers')">
                <template #icon><icon-file /></template>
                我的论文
              </a-doption>
              <a-doption @click="handleLogout" status="danger">
                <template #icon><icon-export /></template>
                退出登录
              </a-doption>
            </template>
          </a-dropdown>
        </div>
        <div v-else class="auth-buttons">
          <a-button type="text" @click="$router.push('/login')">登录</a-button>
          <a-button type="primary" size="small" @click="$router.push('/register')">注册</a-button>
        </div>
      </div>
    </header>

    <section class="hero-section">
      <div class="hero-content">
        <div class="hero-badge">
          <span class="badge-dot"></span>
          基于 RAG + LLM 的论文精读平台
        </div>
        <h1 class="hero-title">
          让 AI 帮你<br/>
          <span class="title-highlight">读懂每一篇论文</span>
        </h1>
        <p class="hero-desc">
          上传 PDF，AI 自动解析结构、生成摘要、深度解读。<br/>
          支持交互问答，精准定位原文，让科研阅读效率提升 10 倍。
        </p>
        <div class="hero-actions">
          <a-button type="primary" size="large" class="btn-primary" @click="$router.push('/papers')">
            <template #icon>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
              </svg>
            </template>
            开始使用
          </a-button>
          <a-button size="large" class="btn-secondary" @click="scrollToFeatures">
            了解更多
            <template #icon>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M12 5v14M6 13l6 6 6-6"/>
              </svg>
            </template>
          </a-button>
        </div>
        <div class="hero-stats">
          <div class="stat-item float-animation" style="animation-delay: 0s;">
            <span class="stat-value">智能解析</span>
            <span class="stat-label">自动提取论文结构</span>
          </div>
          <div class="stat-item float-animation" style="animation-delay: 0.2s;">
            <span class="stat-value">交互问答</span>
            <span class="stat-label">精准定位原文引用</span>
          </div>
          <div class="stat-item float-animation" style="animation-delay: 0.4s;">
            <span class="stat-value">深度解读</span>
            <span class="stat-label">概念解释与方法对比</span>
          </div>
        </div>
        <div class="slideshow-controls" aria-label="背景图片轮播">
          <button
            v-for="(_, i) in backgrounds"
            :key="i"
            type="button"
            class="slideshow-dot"
            :class="{ active: currentBgIndex === i }"
            :aria-label="`切换到背景图 ${i + 1}`"
            :aria-pressed="currentBgIndex === i"
            @click="selectBackground(i)"
          ></button>
        </div>
      </div>
    </section>

    <section class="features-section" ref="featuresSectionRef">
      <div class="section-shell">
        <div class="section-header">
          <h2>核心功能</h2>
          <p>从上传到理解，全流程 AI 辅助</p>
        </div>
        <div class="features-grid">
          <div class="feature-card" v-for="(f, i) in features" :key="i">
            <div class="feature-icon-wrap" :style="{ background: f.color }">
              <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" v-html="f.icon"></svg>
            </div>
            <h3>{{ f.title }}</h3>
            <p>{{ f.desc }}</p>
            <div class="feature-tags">
              <span v-for="tag in f.tags" :key="tag">{{ tag }}</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="workflow-section">
      <div class="section-shell workflow-shell">
        <div class="section-header workflow-header">
          <h2>三步开始</h2>
          <p>从上传论文到追问原文，一次完成。</p>
        </div>
        <div class="workflow-steps">
          <div class="workflow-step" v-for="(step, i) in workflowSteps" :key="i">
            <div class="step-number">{{ String(i + 1).padStart(2, '0') }}</div>
            <div class="step-content">
              <h3>{{ step.title }}</h3>
              <p>{{ step.desc }}</p>
            </div>
            <div class="step-connector" v-if="i < workflowSteps.length - 1">
              <svg viewBox="0 0 40 40" width="40" height="40" fill="none" stroke="oklch(0.55 0.14 45)" stroke-width="2">
                <path d="M10 20h20M24 14l6 6-6 6"/>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="cta-section">
      <div class="cta-content">
        <h2>准备好提升阅读效率了吗？</h2>
        <p>上传你的第一篇论文，体验 AI 驱动的精读流程</p>
        <a-button type="primary" size="large" @click="$router.push('/papers')">
          立即开始
        </a-button>
      </div>
    </section>

    <footer class="footer">
      <p>PaperAI &copy; 2026 · 智能论文精读助手</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import { getCurrentUser } from '@/api/auth'
import { IconDown, IconFile, IconExport } from '@arco-design/web-vue/es/icon'
import BrandMark from '@/components/BrandMark.vue'

const currentUser = ref<any>(null)
const showDropdown = ref(false)
const isScrolled = ref(false)
const featuresSectionRef = ref<HTMLElement | null>(null)
const currentBgIndex = ref(0)

const backgrounds = ['lib1.jpg', 'read2.jpg?v=20260621', 'research-reading.jpg']

const isLoggedIn = computed(() => !!currentUser.value)
const userInitial = computed(() => {
  if (!currentUser.value) return '?'
  return currentUser.value.username?.charAt(0).toUpperCase() || '?'
})

const features = [
  {
    title: '智能解析',
    desc: '自动提取论文结构，识别章节、图表、公式，快速定位关键内容',
    icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    color: 'oklch(0.50 0.16 45)',
    tags: ['自动分章', '结构提取', '快速定位']
  },
  {
    title: '交互问答',
    desc: '针对论文任意内容提问，AI 即时回答并精准引用原文位置',
    icon: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    color: 'oklch(0.55 0.14 30)',
    tags: ['上下文感知', '原文引用', '多轮对话']
  },
  {
    title: '结构化摘要',
    desc: '一键生成论文概述、方法、实验、贡献的结构化摘要',
    icon: '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>',
    color: 'oklch(0.48 0.12 55)',
    tags: ['自动摘要', '四维度分析', '可重新生成']
  },
  {
    title: '深度解读',
    desc: '概念解释、方法对比、关键信息提取，帮你深入理解论文',
    icon: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    color: 'oklch(0.52 0.13 120)',
    tags: ['概念解释', '方法对比', '关键信息']
  }
]

const workflowSteps = [
  { title: '上传论文', desc: '支持 PDF 格式，自动解析提取内容' },
  { title: 'AI 分析', desc: '自动生成结构化摘要和深度解读' },
  { title: '交互探索', desc: '随时提问，AI 精准回答并引用原文' }
]

let bgInterval: ReturnType<typeof setInterval> | undefined

const startBackgroundRotation = () => {
  clearInterval(bgInterval)
  bgInterval = setInterval(() => {
    currentBgIndex.value = (currentBgIndex.value + 1) % backgrounds.length
  }, 8000)
}

const selectBackground = (index: number) => {
  currentBgIndex.value = index
  startBackgroundRotation()
}

onMounted(async () => {
  const token = localStorage.getItem('access_token')
  if (token) {
    try {
      const user = await getCurrentUser()
      currentUser.value = user
      localStorage.setItem('user', JSON.stringify(user))
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      currentUser.value = null
    }
  }
  window.addEventListener('scroll', handleScroll)

  startBackgroundRotation()
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
  clearInterval(bgInterval)
})

const handleScroll = () => {
  isScrolled.value = window.scrollY > 20
}

const scrollToFeatures = () => {
  featuresSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const handleLogout = () => {
  localStorage.removeItem('access_token')
  localStorage.removeItem('user')
  currentUser.value = null
  showDropdown.value = false
  Message.success('已退出登录')
}
</script>

<style scoped>
.home-page {
  position: relative;
  min-height: 100vh;
  color: oklch(0.25 0.02 50);
  overflow-x: hidden;
  z-index: 1;
}

.page-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
}

.home-page > section,
.home-page > footer {
  position: relative;
  z-index: 1;
}

.bg-slideshow {
  position: absolute;
  inset: 0;
}

.bg-slide {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  opacity: 0;
  transition: opacity 2s ease-in-out;
  transform: scale(1.05);
}

.bg-slide.active {
  opacity: 1;
  animation: bgZoom 20s ease-in-out infinite;
}

@keyframes bgZoom {
  0%, 100% { transform: scale(1.05); }
  50% { transform: scale(1.12); }
}

.bg-overlay {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    180deg,
    oklch(0.13 0.02 255 / 0.64) 0%,
    oklch(0.14 0.02 255 / 0.70) 55%,
    oklch(0.12 0.02 255 / 0.78) 100%
  );
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulseSoft {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.top-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 32px;
  background: oklch(0.15 0.025 255 / 0.72);
  border-bottom: 1px solid oklch(1 0 / 0.12);
  transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
}

.top-nav.scrolled {
  background: oklch(0.14 0.025 255 / 0.96);
  border-bottom-color: oklch(1 0 / 0.08);
  box-shadow: 0 4px 24px oklch(0 0 / 0.08);
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 700;
  color: oklch(0.98 0.005 255);
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 8px;
  transition: background 0.2s;
}

.user-info:hover {
  background: oklch(1 0 / 0.09);
}

.username {
  color: oklch(0.94 0.01 255);
  font-size: 14px;
  font-weight: 500;
}

.dropdown-trigger {
  color: oklch(0.94 0.01 255);
  border: none;
  background: transparent;
}

.dropdown-trigger:hover {
  background: oklch(1 0 / 0.09);
}

.auth-buttons {
  display: flex;
  gap: 8px;
  align-items: center;
}

.hero-section {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 128px clamp(24px, 8vw, 144px) 72px;
}

.hero-content {
  position: relative;
  z-index: 1;
  text-align: center;
  max-width: 820px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 20px;
  background: oklch(1 0 / 0.08);
  border: 1px solid oklch(1 0 / 0.18);
  border-radius: 100px;
  font-size: 13px;
  color: oklch(0.92 0.025 70);
  margin-bottom: 32px;
  animation: fadeInUp 0.6s ease 0.1s forwards;
  opacity: 0;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: oklch(0.50 0.16 45);
  animation: pulseSoft 2s ease-in-out infinite;
}

.hero-title {
  font-size: clamp(40px, 6vw, 72px);
  font-weight: 800;
  line-height: 1.08;
  margin: 0 0 24px;
  color: oklch(0.99 0.004 255);
  letter-spacing: -0.02em;
  animation: fadeInUp 0.6s ease 0.2s forwards;
  opacity: 0;
  text-wrap: balance;
  text-shadow: 0 3px 24px oklch(0 0 / 0.28);
}

.title-highlight {
  color: oklch(0.78 0.16 55);
}

.hero-desc {
  font-size: 18px;
  line-height: 1.7;
  color: oklch(0.92 0.012 255);
  margin-bottom: 40px;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
  animation: fadeInUp 0.6s ease 0.3s forwards;
  opacity: 0;
  text-wrap: pretty;
  text-shadow: 0 2px 14px oklch(0 0 / 0.36);
}

.hero-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 64px;
  animation: fadeInUp 0.6s ease 0.4s forwards;
  opacity: 0;
}

.btn-primary {
  padding: 0 32px;
  height: 52px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 14px;
  background: oklch(0.50 0.16 45);
  border: none;
  color: oklch(0.98 0.01 95);
  box-shadow: 0 4px 24px oklch(0.50 0.16 45 / 0.25);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-primary:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 32px oklch(0.50 0.16 45 / 0.35);
  background: oklch(0.45 0.18 45);
}

.btn-secondary {
  padding: 0 24px;
  height: 52px;
  font-size: 16px;
  font-weight: 500;
  border-radius: 14px;
  background: oklch(1 0 / 0.08);
  border: 1px solid oklch(1 0 / 0.35);
  color: oklch(0.98 0.005 255);
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.btn-secondary:hover {
  background: oklch(1 0 / 0.16);
  border-color: oklch(1 0 / 0.65);
  color: white;
}

.hero-stats {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 40px;
  animation: fadeInUp 0.6s ease 0.5s forwards;
  opacity: 0;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 0 28px 0 0;
  background: transparent;
  border-right: 1px solid oklch(1 0 / 0.24);
  transition: all 0.3s ease;
}

.stat-item:last-child {
  padding-right: 0;
  border-right: 0;
}

.stat-item:hover {
  transform: translateY(-2px);
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: oklch(0.98 0.005 255);
}

.stat-label {
  font-size: 13px;
  color: oklch(0.78 0.015 255);
}

.slideshow-controls {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 34px;
}

.slideshow-dot {
  width: 24px;
  height: 3px;
  padding: 0;
  border: 0;
  border-radius: 2px;
  background: oklch(1 0 / 0.35);
  cursor: pointer;
  transition: background 0.25s ease, transform 0.25s cubic-bezier(0.25, 1, 0.5, 1);
}

.slideshow-dot.active {
  background: oklch(0.78 0.16 55);
  transform: scaleY(1.7);
}

.slideshow-dot:focus-visible {
  outline: 2px solid white;
  outline-offset: 4px;
}

.stat-divider {
  width: 1px;
  height: 40px;
  background: oklch(0.85 0.01 60 / 0.2);
}

.features-section {
  width: 100%;
  padding: clamp(64px, 7vw, 88px) clamp(24px, 7vw, 120px) clamp(52px, 6vw, 72px);
  background: oklch(0.985 0.006 255);
  scroll-margin-top: 72px;
}

.section-shell {
  width: min(100%, 1120px);
  margin: 0 auto;
}

.section-header {
  text-align: center;
  margin-bottom: clamp(36px, 4vw, 48px);
}

.section-header h2 {
  font-size: 36px;
  font-weight: 700;
  color: oklch(0.20 0.02 50);
  margin: 0 0 12px;
  text-wrap: balance;
}

.section-header p {
  font-size: 16px;
  color: oklch(0.45 0.02 50);
  margin: 0;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid oklch(0.84 0.012 255);
}

.feature-card {
  padding: 36px clamp(16px, 3vw, 44px) 40px 0;
  border-bottom: 1px solid oklch(0.84 0.012 255);
  transition: transform 0.25s cubic-bezier(0.25, 1, 0.5, 1);
}

.feature-card:nth-child(even) {
  padding-right: 0;
  padding-left: clamp(16px, 3vw, 44px);
  border-left: 1px solid oklch(0.84 0.012 255);
}

.feature-card:hover {
  transform: translateY(-3px);
}

.feature-card:hover .feature-icon-wrap {
  transform: scale(1.1) rotate(-5deg);
}

.feature-icon-wrap {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  transition: transform 0.3s ease;
}

.feature-card h3 {
  font-size: 18px;
  font-weight: 600;
  color: oklch(0.20 0.02 50);
  margin: 0 0 8px;
}

.feature-card p {
  font-size: 14px;
  line-height: 1.6;
  color: oklch(0.45 0.02 50);
  margin: 0 0 16px;
}

.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.feature-tags span {
  padding: 4px 12px;
  background: oklch(0.50 0.16 45 / 0.1);
  border-radius: 100px;
  font-size: 12px;
  color: oklch(0.40 0.10 45);
}

.workflow-section {
  width: 100%;
  padding: 0 clamp(24px, 7vw, 120px) clamp(68px, 8vw, 96px);
  background: oklch(0.985 0.006 255);
}

.workflow-shell {
  display: grid;
  grid-template-columns: minmax(210px, 0.72fr) minmax(0, 2.28fr);
  gap: clamp(40px, 5vw, 72px);
  align-items: start;
  padding-top: clamp(48px, 5vw, 64px);
  border-top: 1px solid oklch(0.84 0.012 255);
}

.workflow-header {
  text-align: left;
  margin-bottom: 0;
}

.workflow-header h2 {
  font-size: 32px;
}

.workflow-header p {
  max-width: 18em;
  line-height: 1.7;
}

.workflow-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-top: 2px;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px clamp(12px, 1.5vw, 20px);
  background: transparent;
  flex: 1;
  min-width: 0;
  transition: transform 0.25s cubic-bezier(0.25, 1, 0.5, 1);
}

.workflow-step:hover {
  transform: translateY(-3px);
}

.step-number {
  font-size: 32px;
  font-weight: 800;
  color: oklch(0.50 0.16 45);
  flex-shrink: 0;
  opacity: 0.3;
}

.step-content h3 {
  font-size: 16px;
  font-weight: 600;
  color: oklch(0.20 0.02 50);
  margin: 0 0 4px;
}

.step-content p {
  font-size: 13px;
  color: oklch(0.45 0.02 50);
  margin: 0;
}

.step-connector {
  flex-shrink: 0;
  opacity: 0.5;
}

.cta-section {
  width: 100%;
  padding: clamp(68px, 8vw, 96px) 24px;
  text-align: center;
  background: oklch(0.15 0.025 255);
  border-top: 1px solid oklch(1 0 / 0.08);
}

.cta-content {
  max-width: 600px;
  margin: 0 auto;
  padding: 0 24px;
}

.cta-content h2 {
  font-size: 28px;
  font-weight: 700;
  color: oklch(0.98 0.006 255);
  margin: 0 0 12px;
}

.cta-content p {
  font-size: 16px;
  color: oklch(0.78 0.018 255);
  margin: 0 0 32px;
}

.footer {
  padding: 32px 24px;
  text-align: center;
  border-top: 1px solid oklch(1 0 / 0.08);
  background: oklch(0.16 0.025 255);
}

.footer p {
  font-size: 13px;
  color: oklch(0.76 0.014 255);
  margin: 0;
}

@media (max-width: 960px) {
  .workflow-shell {
    grid-template-columns: 1fr;
    gap: 28px;
  }

  .workflow-header p { max-width: 32em; }
  .workflow-step:first-child { padding-left: 0; }
  .workflow-step:last-child { padding-right: 0; }
}

@media (max-width: 768px) {
  .hero-section { min-height: auto; padding-top: 116px; }
  .hero-title { font-size: 40px; }
  .hero-desc { font-size: 15px; }
  .hero-actions { flex-direction: column; align-items: stretch; max-width: 320px; }
  .hero-stats { flex-direction: column; align-items: stretch; gap: 14px; }
  .stat-item,
  .stat-item:last-child {
    padding: 0 0 14px;
    border-right: 0;
    border-bottom: 1px solid oklch(1 0 / 0.18);
  }
  .stat-item:last-child { border-bottom: 0; }
  .features-grid { grid-template-columns: 1fr; }
  .feature-card,
  .feature-card:nth-child(even) {
    padding: 28px 0;
    border-left: 0;
  }
  .workflow-steps {
    flex-direction: column;
    align-items: stretch;
  }
  .workflow-step {
    position: relative;
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr);
    width: 100%;
    min-width: 0;
    padding: 14px 0 46px;
  }
  .workflow-step:last-child { padding-bottom: 14px; }
  .step-number { grid-column: 1; }
  .step-content { grid-column: 2; }
  .step-connector {
    position: absolute;
    left: 4px;
    bottom: 2px;
    transform: rotate(90deg);
  }
}

@media (max-width: 480px) {
  .top-nav { padding: 12px 16px; }
  .hero-section { padding: 100px 16px 60px; }
  .hero-title { font-size: 34px; }
  .username { display: none; }
  .features-section { padding: 56px 16px 40px; }
  .workflow-section { padding: 0 16px 64px; }
  .workflow-shell { padding-top: 40px; }
  .section-header h2 { font-size: 30px; }
  .workflow-header h2 { font-size: 28px; }
  .cta-section { padding: 60px 16px; }
  .cta-content { padding: 0; }
}

@media (prefers-reduced-motion: reduce) {
  .bg-slide,
  .bg-slide.active,
  .hero-badge,
  .hero-title,
  .hero-desc,
  .hero-actions,
  .hero-stats,
  .badge-dot {
    animation: none !important;
    transition: none !important;
  }

  .hero-badge,
  .hero-title,
  .hero-desc,
  .hero-actions,
  .hero-stats {
    opacity: 1;
  }

  .feature-card,
  .feature-icon-wrap,
  .workflow-step {
    transition: none !important;
  }
}
</style>

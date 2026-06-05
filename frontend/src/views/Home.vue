<template>
  <div class="home-page">
    <!-- 背景装饰 -->
    <div class="page-background">
      <div class="background-gradient"></div>
      <div class="corner-glow corner-glow-top-left"></div>
      <div class="corner-glow corner-glow-top-right"></div>
      <div class="corner-glow corner-glow-bottom-left"></div>
      <div class="corner-glow corner-glow-bottom-right"></div>
      <div class="corner-line corner-line-top-left"></div>
      <div class="corner-line corner-line-top-right"></div>
      <div class="corner-line corner-line-bottom-left"></div>
      <div class="corner-line corner-line-bottom-right"></div>
      <div class="decoration-circle decoration-circle-1"></div>
      <div class="decoration-circle decoration-circle-2"></div>
      <div class="decoration-circle decoration-circle-3"></div>
      <div class="decoration-circle decoration-circle-4"></div>
      <div class="decoration-blob decoration-blob-1"></div>
      <div class="decoration-blob decoration-blob-2"></div>
      <div class="decoration-grid"></div>
    </div>
    <!-- 顶部导航栏 -->
    <header class="top-nav" :class="{ scrolled: isScrolled }">
      <div class="nav-brand">
        <svg class="brand-icon" viewBox="0 0 32 32" width="28" height="28">
          <defs>
            <linearGradient id="brandGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#6366f1"/>
              <stop offset="100%" style="stop-color:#8b5cf6"/>
            </linearGradient>
          </defs>
          <rect x="2" y="2" width="28" height="28" rx="8" fill="url(#brandGrad)"/>
          <path d="M10 10h12M10 16h8M10 22h10" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span>PaperAI</span>
      </div>
      <div class="nav-right">
        <div v-if="isLoggedIn" class="user-info" @click="showDropdown = !showDropdown">
          <a-avatar :size="32" :style="{ backgroundColor: '#6366f1' }">
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

    <!-- Hero 区域 -->
    <section class="hero-section">
      <div class="hero-bg">
        <div class="hero-grid"></div>
        <div class="hero-glow hero-glow-1"></div>
        <div class="hero-glow hero-glow-2"></div>
      </div>
      <div class="hero-content">
        <div class="hero-badge">
          <span class="badge-dot"></span>
          基于 RAG + LLM 的论文精读平台
        </div>
        <h1 class="hero-title">
          让 AI 帮你<br/>
          <span class="title-gradient">读懂每一篇论文</span>
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
                <path d="M7 17l5-5 5 5M7 7l5 5 5-5"/>
              </svg>
            </template>
          </a-button>
        </div>
        <!-- 统计数据 -->
        <div class="hero-stats">
          <div class="stat-item">
            <span class="stat-value">智能解析</span>
            <span class="stat-label">自动提取论文结构</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">交互问答</span>
            <span class="stat-label">精准定位原文引用</span>
          </div>
          <div class="stat-divider"></div>
          <div class="stat-item">
            <span class="stat-value">深度解读</span>
            <span class="stat-label">概念解释与方法对比</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 核心功能 -->
    <section class="features-section" ref="featuresRef">
      <div class="section-header">
        <h2>核心功能</h2>
        <p>从上传到理解，全流程 AI 辅助</p>
      </div>
      <div class="features-grid">
        <div class="feature-card" v-for="(f, i) in features" :key="i">
          <div class="feature-icon-wrap" :style="{ background: f.gradient }">
            <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="white" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" v-html="f.icon"></svg>
          </div>
          <h3>{{ f.title }}</h3>
          <p>{{ f.desc }}</p>
          <div class="feature-tags">
            <span v-for="tag in f.tags" :key="tag">{{ tag }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 使用流程 -->
    <section class="workflow-section">
      <div class="section-header">
        <h2>三步开始</h2>
        <p>简单几步，让 AI 成为你的研究助手</p>
      </div>
      <div class="workflow-steps">
        <div class="workflow-step" v-for="(step, i) in workflowSteps" :key="i">
          <div class="step-number">{{ String(i + 1).padStart(2, '0') }}</div>
          <div class="step-content">
            <h3>{{ step.title }}</h3>
            <p>{{ step.desc }}</p>
          </div>
          <div class="step-connector" v-if="i < workflowSteps.length - 1">
            <svg viewBox="0 0 40 40" width="40" height="40" fill="none" stroke="#6366f1" stroke-width="1.5">
              <path d="M10 20h20M24 14l6 6-6 6"/>
            </svg>
          </div>
        </div>
      </div>
    </section>

    <!-- CTA -->
    <section class="cta-section">
      <div class="cta-content">
        <h2>准备好提升阅读效率了吗？</h2>
        <p>上传你的第一篇论文，体验 AI 驱动的精读流程</p>
        <a-button type="primary" size="large" @click="$router.push('/papers')">
          立即开始
        </a-button>
      </div>
    </section>

    <!-- 页脚 -->
    <footer class="footer">
      <p>PaperAI &copy; 2026 &mdash; 智能论文精读助手</p>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { IconDown, IconFile, IconExport } from '@arco-design/web-vue/es/icon'

const router = useRouter()
const currentUser = ref<any>(null)
const showDropdown = ref(false)
const isScrolled = ref(false)
const featuresRef = ref<HTMLElement | null>(null)

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
    gradient: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
    tags: ['自动分章', '结构提取', '快速定位']
  },
  {
    title: '交互问答',
    desc: '针对论文任意内容提问，AI 即时回答并精准引用原文位置',
    icon: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    gradient: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
    tags: ['上下文感知', '原文引用', '多轮对话']
  },
  {
    title: '结构化摘要',
    desc: '一键生成论文概述、方法、实验、贡献的结构化摘要',
    icon: '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>',
    gradient: 'linear-gradient(135deg, #f59e0b, #ef4444)',
    tags: ['自动摘要', '四维度分析', '可重新生成']
  },
  {
    title: '深度解读',
    desc: '概念解释、方法对比、关键信息提取，帮你深入理解论文',
    icon: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    gradient: 'linear-gradient(135deg, #10b981, #06b6d4)',
    tags: ['概念解释', '方法对比', '关键信息']
  }
]

const workflowSteps = [
  { title: '上传论文', desc: '支持 PDF 格式，自动解析提取内容' },
  { title: 'AI 分析', desc: '自动生成结构化摘要和深度解读' },
  { title: '交互探索', desc: '随时提问，AI 精准回答并引用原文' }
]

onMounted(() => {
  const userStr = localStorage.getItem('user')
  if (userStr) {
    try {
      currentUser.value = JSON.parse(userStr)
    } catch {
      localStorage.removeItem('user')
    }
  }
  window.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  window.removeEventListener('scroll', handleScroll)
})

const handleScroll = () => {
  isScrolled.value = window.scrollY > 20
}

const scrollToFeatures = () => {
  featuresRef.value?.scrollIntoView({ behavior: 'smooth' })
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
  color: #1d2129;
  overflow-x: hidden;
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

.background-gradient {
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, #f0f4ff 0%, #f5f0ff 30%, #faf5ff 60%, #f0f7ff 100%);
}

.corner-glow {
  position: absolute;
  width: 300px;
  height: 300px;
  opacity: 0.15;
  filter: blur(60px);
}

.corner-glow-top-left {
  top: -50px;
  left: -50px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.4) 0%, transparent 70%);
}

.corner-glow-top-right {
  top: -50px;
  right: -50px;
  background: radial-gradient(circle, rgba(139, 92, 246, 0.3) 0%, transparent 70%);
}

.corner-glow-bottom-left {
  bottom: -50px;
  left: -50px;
  background: radial-gradient(circle, rgba(192, 132, 252, 0.3) 0%, transparent 70%);
}

.corner-glow-bottom-right {
  bottom: -50px;
  right: -50px;
  background: radial-gradient(circle, rgba(96, 165, 250, 0.3) 0%, transparent 70%);
}

.corner-line {
  position: absolute;
  background: linear-gradient(90deg, rgba(99, 102, 241, 0.1), transparent);
  height: 1px;
}

.corner-line-top-left {
  top: 80px;
  left: 0;
  width: 180px;
  transform: rotate(-45deg);
  transform-origin: left center;
}

.corner-line-top-right {
  top: 80px;
  right: 0;
  width: 180px;
  transform: rotate(45deg);
  transform-origin: right center;
}

.corner-line-bottom-left {
  bottom: 80px;
  left: 0;
  width: 180px;
  transform: rotate(45deg);
  transform-origin: left center;
}

.corner-line-bottom-right {
  bottom: 80px;
  right: 0;
  width: 180px;
  transform: rotate(-45deg);
  transform-origin: right center;
}

.decoration-circle {
  position: absolute;
  border-radius: 50%;
  opacity: 0.25;
  filter: blur(40px);
}

.decoration-circle-1 {
  width: 200px;
  height: 200px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  top: 10%;
  right: 15%;
  animation: float1 20s ease-in-out infinite;
}

.decoration-circle-2 {
  width: 180px;
  height: 180px;
  background: linear-gradient(135deg, #8b5cf6, #a855f7);
  bottom: 15%;
  left: 12%;
  animation: float2 25s ease-in-out infinite;
}

.decoration-circle-3 {
  width: 140px;
  height: 140px;
  background: linear-gradient(135deg, #c084fc, #e9d5ff);
  top: 55%;
  right: 25%;
  animation: float3 18s ease-in-out infinite;
}

.decoration-circle-4 {
  width: 120px;
  height: 120px;
  background: linear-gradient(135deg, #60a5fa, #93c5fd);
  top: 25%;
  left: 20%;
  animation: float4 22s ease-in-out infinite;
}

.decoration-blob {
  position: absolute;
  border-radius: 40% 60% 70% 30% / 40% 50% 60% 50%;
  opacity: 0.2;
  filter: blur(30px);
}

.decoration-blob-1 {
  width: 150px;
  height: 150px;
  background: linear-gradient(135deg, #a78bfa, #c4b5fd);
  top: 70%;
  right: 20%;
  animation: morph1 15s ease-in-out infinite;
}

.decoration-blob-2 {
  width: 130px;
  height: 130px;
  background: linear-gradient(135deg, #7dd3fc, #a5f3fc);
  top: 35%;
  left: 45%;
  animation: morph2 18s ease-in-out infinite;
}

.decoration-grid {
  position: absolute;
  width: 100%;
  height: 100%;
  background-image: 
    linear-gradient(rgba(99, 102, 241, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(99, 102, 241, 0.03) 1px, transparent 1px);
  background-size: 60px 60px;
  animation: gridMove 40s linear infinite;
}

@keyframes float1 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-30px, 30px) scale(1.05); }
}

@keyframes float2 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(40px, -40px) scale(0.95); }
}

@keyframes float3 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(20px, -20px) scale(1.1); }
}

@keyframes float4 {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(-25px, 25px) scale(0.9); }
}

@keyframes morph1 {
  0%, 100% { border-radius: 40% 60% 70% 30% / 40% 50% 60% 50%; }
  25% { border-radius: 70% 30% 50% 50% / 30% 60% 40% 70%; }
  50% { border-radius: 50% 60% 30% 70% / 50% 40% 60% 50%; }
  75% { border-radius: 60% 40% 60% 40% / 60% 30% 70% 40%; }
}

@keyframes morph2 {
  0%, 100% { border-radius: 60% 40% 30% 70% / 60% 30% 70% 40%; }
  25% { border-radius: 30% 70% 50% 50% / 50% 60% 40% 50%; }
  50% { border-radius: 50% 50% 70% 30% / 40% 70% 30% 60%; }
  75% { border-radius: 70% 30% 40% 60% / 30% 50% 50% 70%; }
}

@keyframes gridMove {
  0% { background-position: 0 0; }
  100% { background-position: 60px 60px; }
}

/* 顶部导航栏 */
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
  transition: all 0.3s ease;
}

.top-nav.scrolled {
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  box-shadow: 0 1px 8px rgba(0, 0, 0, 0.04);
}

.nav-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 700;
  color: #1d2129;
}

.brand-icon {
  filter: drop-shadow(0 2px 8px rgba(99, 102, 241, 0.3));
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
  background: rgba(99, 102, 241, 0.06);
}

.username {
  color: #1d2129;
  font-size: 14px;
  font-weight: 500;
}

.dropdown-trigger {
  color: #4e5969;
  border: none;
  background: transparent;
}

.dropdown-trigger:hover {
  background: rgba(99, 102, 241, 0.06);
}

.auth-buttons {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* Hero 区域 */
.hero-section {
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  padding: 120px 24px 80px;
  overflow: hidden;
}

.hero-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.hero-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(99, 102, 241, 0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(99, 102, 241, 0.04) 1px, transparent 1px);
  background-size: 60px 60px;
  mask-image: radial-gradient(ellipse at center, black 30%, transparent 70%);
}

.hero-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.12;
  animation: glowFloat 8s ease-in-out infinite;
}

.hero-glow-1 {
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, #6366f1, transparent 70%);
  top: -10%;
  left: 20%;
  animation-delay: 0s;
}

.hero-glow-2 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, #8b5cf6, transparent 70%);
  top: 30%;
  right: 10%;
  animation-delay: -3s;
}

@keyframes glowFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -20px) scale(1.05); }
  66% { transform: translate(-20px, 20px) scale(0.95); }
}

.hero-content {
  position: relative;
  z-index: 1;
  text-align: center;
  max-width: 800px;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.15);
  border-radius: 100px;
  font-size: 13px;
  color: #6366f1;
  margin-bottom: 32px;
}

.badge-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6366f1;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.hero-title {
  font-size: clamp(40px, 6vw, 72px);
  font-weight: 800;
  line-height: 1.1;
  margin: 0 0 24px;
  color: #1d2129;
  letter-spacing: -0.02em;
}

.title-gradient {
  background: linear-gradient(135deg, #6366f1, #8b5cf6, #06b6d4);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.hero-desc {
  font-size: 18px;
  line-height: 1.7;
  color: #4e5969;
  margin-bottom: 40px;
  max-width: 600px;
  margin-left: auto;
  margin-right: auto;
}

.hero-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 64px;
}

.btn-primary {
  padding: 0 32px;
  height: 48px;
  font-size: 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
  box-shadow: 0 4px 24px rgba(99, 102, 241, 0.25);
  transition: all 0.3s ease;
}

.btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 32px rgba(99, 102, 241, 0.35);
}

.btn-secondary {
  padding: 0 24px;
  height: 48px;
  font-size: 16px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e5e6eb;
  color: #4e5969;
  transition: all 0.3s ease;
}

.btn-secondary:hover {
  border-color: #6366f1;
  color: #6366f1;
}

.hero-stats {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 40px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.stat-value {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
}

.stat-label {
  font-size: 13px;
  color: #86909c;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: #e5e6eb;
}

/* 核心功能 */
.features-section {
  padding: 100px 24px;
  max-width: 1200px;
  margin: 0 auto;
}

.section-header {
  text-align: center;
  margin-bottom: 64px;
}

.section-header h2 {
  font-size: 36px;
  font-weight: 700;
  color: #1d2129;
  margin: 0 0 12px;
}

.section-header p {
  font-size: 16px;
  color: #86909c;
  margin: 0;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 24px;
}

.feature-card {
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 16px;
  padding: 32px 24px;
  transition: all 0.3s ease;
}

.feature-card:hover {
  border-color: rgba(99, 102, 241, 0.2);
  box-shadow: 0 8px 32px rgba(99, 102, 241, 0.08);
  transform: translateY(-4px);
}

.feature-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

.feature-card h3 {
  font-size: 18px;
  font-weight: 600;
  color: #1d2129;
  margin: 0 0 8px;
}

.feature-card p {
  font-size: 14px;
  line-height: 1.6;
  color: #4e5969;
  margin: 0 0 16px;
}

.feature-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.feature-tags span {
  padding: 3px 10px;
  background: rgba(99, 102, 241, 0.06);
  border-radius: 100px;
  font-size: 12px;
  color: #6366f1;
}

/* 使用流程 */
.workflow-section {
  padding: 100px 24px;
  max-width: 900px;
  margin: 0 auto;
}

.workflow-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 24px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 16px;
  flex: 1;
  min-width: 220px;
  max-width: 280px;
}

.step-number {
  font-size: 32px;
  font-weight: 800;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  flex-shrink: 0;
}

.step-content h3 {
  font-size: 16px;
  font-weight: 600;
  color: #1d2129;
  margin: 0 0 4px;
}

.step-content p {
  font-size: 13px;
  color: #86909c;
  margin: 0;
}

.step-connector {
  flex-shrink: 0;
  color: #6366f1;
}

/* CTA */
.cta-section {
  padding: 100px 24px;
  text-align: center;
}

.cta-content {
  max-width: 600px;
  margin: 0 auto;
  padding: 64px 40px;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.06), rgba(139, 92, 246, 0.06));
  border: 1px solid rgba(99, 102, 241, 0.12);
  border-radius: 24px;
}

.cta-content h2 {
  font-size: 28px;
  font-weight: 700;
  color: #1d2129;
  margin: 0 0 12px;
}

.cta-content p {
  font-size: 16px;
  color: #4e5969;
  margin: 0 0 32px;
}

/* 页脚 */
.footer {
  padding: 32px 24px;
  text-align: center;
  border-top: 1px solid #e5e6eb;
}

.footer p {
  font-size: 13px;
  color: #86909c;
  margin: 0;
}

/* 响应式 */
@media (max-width: 768px) {
  .hero-title { font-size: 36px; }
  .hero-desc { font-size: 15px; }
  .hero-actions { flex-direction: column; align-items: center; }
  .hero-stats { flex-direction: column; gap: 24px; }
  .stat-divider { width: 32px; height: 1px; }
  .workflow-steps { flex-direction: column; }
  .step-connector { transform: rotate(90deg); }
  .workflow-step { max-width: 100%; }
}
</style>

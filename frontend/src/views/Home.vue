<template>
  <div class="home-page">
    <!-- 背景图片轮播 -->
    <div class="page-background">
      <div class="bg-slideshow">
        <div
          class="bg-slide active"
          :style="{ backgroundImage: `url('/images/${currentBackground}')` }"
        ></div>
      </div>
      <div class="bg-overlay"></div>
    </div>

    <header class="top-nav" :class="{ scrolled: isScrolled }">
      <div class="nav-brand">
        <BrandMark :size="28" />
      </div>
      <div class="nav-right">
        <a-dropdown
          v-if="isLoggedIn"
          v-model:popup-visible="showDropdown"
          trigger="hover"
          position="br"
        >
            <button
              class="user-info"
              type="button"
              aria-label="打开账户菜单"
              :aria-expanded="showDropdown"
              @click="showDropdown = !showDropdown"
            >
              <a-avatar :size="32" :style="{ backgroundColor: 'oklch(0.50 0.16 45)' }">
                {{ userInitial }}
              </a-avatar>
              <span class="username">{{ currentUser?.username }}</span>
            </button>
            <template #content>
              <a-doption @click="$router.push('/library')">
                <template #icon><icon-file /></template>
                本地论文库
              </a-doption>
              <a-doption @click="$router.push('/projects')">
                <template #icon><icon-folder /></template>
                研究项目
              </a-doption>
              <a-doption v-if="currentUser?.role === 'admin'" @click="$router.push('/admin')">
                <template #icon><icon-dashboard /></template>
                管理后台
              </a-doption>
              <template v-if="otherAccounts.length">
                <a-doption
                  v-for="account in otherAccounts"
                  :key="account.user.id"
                  @click="handleSwitchAccount(account)"
                >
                  <template #icon><icon-swap /></template>
                  切换至 {{ account.user.username }}
                </a-doption>
              </template>
              <a-doption @click="openAddAccount">
                <template #icon><icon-plus /></template>
                添加账号
              </a-doption>
              <a-doption @click="handleLogout" status="danger">
                <template #icon><icon-export /></template>
                退出登录
              </a-doption>
            </template>
        </a-dropdown>
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
          从真实文献到可核对写作
        </div>
        <h1 class="hero-title">
          让论文研究<br/>
          <span class="title-highlight">从阅读走向写作</span>
        </h1>
        <p class="hero-desc">
          在项目中发现真实论文、管理全文证据并完成写作。<br/>
          也可以独立精读 PDF，用页码、原文片段和版面定位核对回答。
        </p>
        <div class="hero-actions">
          <a-button type="primary" size="large" class="btn-primary" @click="$router.push('/projects')">
            <template #icon>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12"/>
              </svg>
            </template>
            {{ isLoggedIn ? '进入研究项目' : '开始研究' }}
          </a-button>
          <a-button size="large" class="btn-secondary" @click="$router.push('/guide')">
            查看使用指南
            <template #icon>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
                <path d="M4 5.5A2.5 2.5 0 016.5 3H11v16H6.5A2.5 2.5 0 004 21.5zM20 5.5A2.5 2.5 0 0017.5 3H13v16h4.5a2.5 2.5 0 012.5 2.5z"/>
              </svg>
            </template>
          </a-button>
        </div>
        <div class="hero-stats">
          <div class="stat-item">
            <span class="stat-value">真实文献</span>
            <span class="stat-label">可编辑条件与有界检索</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">原文证据</span>
            <span class="stat-label">页码、片段与版面定位</span>
          </div>
          <div class="stat-item">
            <span class="stat-value">过程可见</span>
            <span class="stat-label">流式阶段与任务状态</span>
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

    <section class="features-section">
      <div class="section-shell">
        <div class="section-header">
          <h2>一套连续的研究工作流</h2>
          <p>检索结果、项目论文、原文证据和写作文稿各自有清晰边界</p>
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
          <h2>项目研究的四个阶段</h2>
          <p>每个模块只处理自己的任务，资料沿流程进入下一步。</p>
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
        <h2>按你的任务选择入口</h2>
        <p>多篇论文的发现、管理与写作从研究项目开始；单篇 PDF 精读从本地论文库开始。</p>
        <div class="cta-actions">
          <a-button type="primary" size="large" @click="$router.push('/projects')">进入研究项目</a-button>
          <a-button size="large" @click="$router.push('/library')">打开本地论文库</a-button>
        </div>
      </div>
    </section>

    <footer class="footer">
      <p>PaperAI &copy; 2026 · 证据可追溯的论文研究工作台</p>
      <button type="button" @click="$router.push('/guide')">使用指南</button>
    </footer>

    <a-modal
      v-model:visible="showAddAccount"
      title="添加登录账号"
      :ok-loading="addingAccount"
      ok-text="登录并添加"
      cancel-text="取消"
      :on-before-ok="handleAddAccount"
    >
      <a-form :model="accountForm" layout="vertical">
        <a-form-item label="用户名或邮箱" required>
          <a-input
            v-model="accountForm.username"
            placeholder="输入另一个账号"
            autocomplete="username"
          />
        </a-form-item>
        <a-form-item label="密码" required>
          <a-input-password
            v-model="accountForm.password"
            placeholder="输入该账号的密码"
            autocomplete="current-password"
            @press-enter="handleAddAccount"
          />
        </a-form-item>
        <div v-if="accountError" class="pa-form-error" role="alert" aria-live="assertive">
          {{ accountError }}
        </div>
      </a-form>
      <p class="account-help">验证成功后，这个浏览器会记住该账号的登录会话。</p>
    </a-modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Message } from '@arco-design/web-vue'
import {
  login,
} from '@/api/auth'
import {
  IconDashboard,
  IconExport,
  IconFile,
  IconFolder,
  IconPlus,
  IconSwap,
} from '@arco-design/web-vue/es/icon'
import BrandMark from '@/components/BrandMark.vue'
import {
  getSavedAccounts,
  rememberAccount,
  rememberCurrentAccount,
  removeSavedAccount,
  type SavedAccount,
} from '@/utils/accountSessions'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const currentUser = computed(() => auth.user)
const savedAccounts = ref<SavedAccount[]>(getSavedAccounts())
const showDropdown = ref(false)
const showAddAccount = ref(false)
const addingAccount = ref(false)
const accountError = ref('')
const accountForm = ref({ username: '', password: '' })
const isScrolled = ref(false)
const currentBgIndex = ref(0)

const backgrounds = ['lib1.jpg', 'read2.jpg?v=20260621', 'research-reading.jpg']

const isLoggedIn = computed(() => !!currentUser.value)
const currentBackground = computed(() => backgrounds[currentBgIndex.value])
const otherAccounts = computed(() =>
  savedAccounts.value.filter(account => account.user.id !== currentUser.value?.id)
)
const userInitial = computed(() => {
  if (!currentUser.value) return '?'
  return currentUser.value.username?.charAt(0).toUpperCase() || '?'
})

const features = [
  {
    title: '真实文献发现',
    desc: '把研究需求整理成可编辑的检索意图和筛选条件，只返回学术来源中的真实结果',
    icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    color: 'oklch(0.50 0.16 45)',
    tags: ['有界检索', '结构化结果', '独立导入']
  },
  {
    title: '论文结构化解析',
    desc: '解析章节、正文、表格和图片等版面元素，保留页码与 bbox 坐标用于原文定位',
    icon: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
    color: 'oklch(0.55 0.14 30)',
    tags: ['多级目录', '版面元素', 'bbox 定位']
  },
  {
    title: '证据支持的写作',
    desc: '从已导入的项目论文中查找证据，生成带结构化引用的段落或改写建议',
    icon: '<path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/>',
    color: 'oklch(0.48 0.12 55)',
    tags: ['Evidence', 'Citation', '明确替换']
  },
  {
    title: '可追踪的质量检查',
    desc: '以流式阶段展示后台进度，保存检查点，并在任务完成前核对证据、引用与输出完整性',
    icon: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    color: 'oklch(0.52 0.13 120)',
    tags: ['SSE 阶段', 'Checkpoint', '完成检查']
  }
]

const workflowSteps = [
  { title: '概览', desc: '定义研究主题、问题与目标' },
  { title: '文献发现', desc: '检索真实论文并选择需要导入的全文' },
  { title: '项目论文', desc: '等待解析与索引，阅读并核对原文' },
  { title: '写作', desc: '使用证据生成建议稿并验证引用' }
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
  const user = await auth.validate()
  if (user) {
    rememberCurrentAccount(user)
    savedAccounts.value = getSavedAccounts()
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

const handleLogout = () => {
  const remainingAccounts = currentUser.value
    ? removeSavedAccount(currentUser.value.id)
    : getSavedAccounts()
  if (remainingAccounts.length) {
    auth.setSession(remainingAccounts[0])
    window.location.reload()
    return
  }
  auth.clearSession()
  savedAccounts.value = []
  showDropdown.value = false
  Message.success('已退出登录')
}

const handleSwitchAccount = (account: SavedAccount) => {
  if (account.user.id === currentUser.value?.id) return
  auth.setSession(account)
  window.location.reload()
}

const openAddAccount = () => {
  showDropdown.value = false
  accountForm.value = { username: '', password: '' }
  accountError.value = ''
  showAddAccount.value = true
}

const handleAddAccount = async () => {
  accountError.value = ''
  if (!accountForm.value.username || !accountForm.value.password) {
    accountError.value = '请填写用户名和密码'
    return false
  }
  addingAccount.value = true
  try {
    const response = await login(accountForm.value)
    rememberAccount(response)
    auth.setSession(response)
    showAddAccount.value = false
    Message.success(`已添加并切换到 ${response.user.username}`)
    window.location.reload()
    return true
  } catch (error: any) {
    accountError.value = error?.response?.data?.detail || '账号或密码不正确'
    return false
  } finally {
    addingAccount.value = false
  }
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

.account-help {
  margin-top: -4px;
  color: var(--pa-muted);
  font-size: 13px;
  line-height: 1.6;
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
  transition: background-color 200ms ease-out, border-color 200ms ease-out, box-shadow 200ms ease-out;
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
  border: 0;
  border-radius: 8px;
  background: transparent;
  transition: background 0.2s;
}

.user-info:hover {
  background: oklch(1 0 / 0.09);
}

.user-info:focus-visible {
  outline: 2px solid oklch(0.92 0.02 70);
  outline-offset: 2px;
}

.username {
  color: oklch(0.94 0.01 255);
  font-size: 14px;
  font-weight: 500;
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
  text-wrap: pretty;
  text-shadow: 0 2px 14px oklch(0 0 / 0.36);
}

.hero-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
  margin-bottom: 64px;
}

.hero-actions :deep(.arco-btn) {
  width: 220px;
}

.btn-primary {
  height: 52px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 14px;
  background: oklch(0.50 0.16 45);
  border: none;
  color: oklch(0.98 0.01 95);
  box-shadow: 0 4px 24px oklch(0.50 0.16 45 / 0.25);
  transition: transform 180ms cubic-bezier(0.25, 1, 0.5, 1), background-color 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}

.btn-primary:not(.arco-btn-disabled):hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 32px oklch(0.50 0.16 45 / 0.35);
  background: oklch(0.45 0.18 45);
}

.btn-secondary {
  height: 52px;
  font-size: 16px;
  font-weight: 500;
  border-radius: 14px;
  background: oklch(0.96 0.012 70);
  border: 1px solid oklch(0.88 0.016 65);
  color: oklch(0.24 0.025 45);
  box-shadow: 0 4px 20px oklch(0 0 / 0.16);
  transition: transform 180ms cubic-bezier(0.25, 1, 0.5, 1), background-color 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}

.btn-secondary:not(.arco-btn-disabled):hover {
  transform: translateY(-3px);
  background: oklch(0.90 0.018 65);
  border-color: oklch(0.78 0.025 60);
  color: oklch(0.20 0.025 45);
  box-shadow: 0 8px 28px oklch(0 0 / 0.24);
}

.btn-primary:active,
.btn-secondary:active {
  transform: translateY(0);
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
  gap: 6px;
  padding: 0 28px 0 0;
  background: transparent;
  border-right: 1px solid oklch(1 0 / 0.24);
}

.stat-item:last-child {
  padding-right: 0;
  border-right: 0;
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
  position: relative;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}

.slideshow-dot::after {
  content: '';
  position: absolute;
  inset: 14px 4px;
  border-radius: 2px;
  background: oklch(1 0 / 0.35);
  transition: background-color 180ms ease-out, transform 180ms ease-out;
}

.slideshow-dot.active::after {
  background: oklch(0.78 0.16 55);
  transform: scaleY(1.7);
}

.slideshow-dot:focus-visible {
  outline: 2px solid white;
  outline-offset: 4px;
}

@media (pointer: coarse) {
  .slideshow-dot { width: 44px; height: 44px; }
  .slideshow-dot::after { inset-block: 20px; }
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
  padding-top: clamp(48px, 5vw, 64px);
  border-top: 1px solid oklch(0.84 0.012 255);
}

.workflow-header {
  text-align: center;
}

.workflow-header h2 {
  font-size: 32px;
}

.workflow-header p {
  max-width: 42em;
  margin-inline: auto;
  line-height: 1.7;
}

.workflow-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  max-width: 680px;
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

.cta-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.footer {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 18px;
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

.footer button {
  padding: 0;
  border: 0;
  border-bottom: 1px solid transparent;
  background: transparent;
  color: oklch(0.82 0.05 55);
  cursor: pointer;
  font-size: 13px;
}

.footer button:hover {
  border-bottom-color: currentColor;
  color: oklch(0.90 0.08 60);
}

.footer button:focus-visible {
  outline: 2px solid oklch(0.82 0.12 55);
  outline-offset: 4px;
}

@media (max-width: 960px) {
  .workflow-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .workflow-step:nth-child(2) .step-connector { display: none; }
}

@media (max-width: 768px) {
  .hero-section { min-height: auto; padding-top: 116px; }
  .hero-title { font-size: 40px; }
  .hero-desc { font-size: 15px; }
  .hero-actions { flex-direction: column; align-items: stretch; width: min(100%, 320px); margin-inline: auto; }
  .hero-actions :deep(.arco-btn) { width: 100%; }
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
    display: block;
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
  .workflow-step:nth-child(2) .step-connector { display: block; }
  .cta-actions { flex-direction: column; }
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

<template>
  <div class="register-page">
    <div class="register-bg">
      <div class="bg-glow bg-glow-1"></div>
      <div class="bg-glow bg-glow-2"></div>
    </div>
    <div class="register-card">
      <div class="logo">
        <svg class="logo-icon" viewBox="0 0 32 32" width="32" height="32">
          <defs>
            <linearGradient id="logoGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" style="stop-color:#6366f1"/>
              <stop offset="100%" style="stop-color:#8b5cf6"/>
            </linearGradient>
          </defs>
          <rect x="2" y="2" width="28" height="28" rx="8" fill="url(#logoGrad)"/>
          <path d="M10 10h12M10 16h8M10 22h10" stroke="white" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <h1>PaperAI</h1>
        <p>加入我们，开始智能论文阅读之旅</p>
      </div>
      <a-form :model="form" layout="vertical" @submit="handleRegister">
        <a-form-item label="用户名" required>
          <a-input v-model="form.username" placeholder="请输入用户名" size="large" />
        </a-form-item>
        <a-form-item label="邮箱" required>
          <a-input v-model="form.email" placeholder="请输入邮箱" size="large" />
        </a-form-item>
        <a-form-item label="密码" required>
          <a-input-password v-model="form.password" placeholder="请输入密码" size="large" autocomplete="new-password" />
        </a-form-item>
        <a-form-item label="确认密码" required>
          <a-input-password v-model="form.confirmPassword" placeholder="请再次输入密码" size="large" autocomplete="new-password" />
        </a-form-item>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="loading" long size="large">注册</a-button>
        </a-form-item>
      </a-form>
      <div class="footer">已有账号？<span class="link" @click="router.push('/login')">立即登录</span></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { register } from '@/api/auth'

const router = useRouter()
const form = ref({ username: '', email: '', password: '', confirmPassword: '' })
const loading = ref(false)

const handleRegister = async () => {
  if (!form.value.username || !form.value.email || !form.value.password) {
    Message.warning('请填写所有字段'); return
  }
  if (form.value.password !== form.value.confirmPassword) {
    Message.error('两次输入的密码不一致'); return
  }
  if (form.value.password.length < 6) {
    Message.error('密码长度至少为6位'); return
  }
  loading.value = true
  try {
    await register(form.value)
    Message.success('注册成功，请登录')
    router.push('/login')
  } catch (error: any) {
    Message.error(error.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.register-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: #f5f7fa;
  padding: 24px;
  position: relative;
  overflow: hidden;
}

.register-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.bg-glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  opacity: 0.08;
}

.bg-glow-1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, #6366f1, transparent 70%);
  top: -10%;
  left: 10%;
}

.bg-glow-2 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, #8b5cf6, transparent 70%);
  bottom: -5%;
  right: 10%;
}

.register-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: #fff;
  border: 1px solid #e5e6eb;
  border-radius: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.04);
}

.logo {
  text-align: center;
  margin-bottom: 32px;
}

.logo-icon {
  margin-bottom: 16px;
  filter: drop-shadow(0 4px 12px rgba(99, 102, 241, 0.3));
}

.logo h1 {
  font-size: 28px;
  margin: 0 0 6px;
  color: #1d2129;
}

.logo p {
  color: #86909c;
  font-size: 14px;
  margin: 0;
}

.footer {
  text-align: center;
  margin-top: 24px;
  color: #86909c;
}

.footer .link {
  color: #6366f1;
  cursor: pointer;
}

.footer .link:hover {
  text-decoration: underline;
}
</style>

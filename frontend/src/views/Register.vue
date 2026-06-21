<template>
  <AuthShell title="创建账号" subtitle="建立你的论文工作台，集中阅读、分析和核对研究资料。" heading-id="register-heading">
      <a-form :model="form" layout="vertical" @submit="handleRegister">
        <a-form-item label="用户名" required>
          <a-input v-model="form.username" placeholder="请输入用户名" size="large" autocomplete="username" />
        </a-form-item>
        <a-form-item label="邮箱" required>
          <a-input v-model="form.email" placeholder="请输入邮箱" size="large" autocomplete="email" />
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
      <template #footer>
        已有账号？
        <button class="auth-link" type="button" @click="router.push('/login')">返回登录</button>
      </template>
  </AuthShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { register } from '@/api/auth'
import AuthShell from '@/components/AuthShell.vue'

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

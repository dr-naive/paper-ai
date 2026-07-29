<template>
  <AuthShell title="欢迎回来" subtitle="登录后继续阅读论文、查看摘要并核对 AI 引用。">
      <a-form :model="form" layout="vertical" @submit="handleLogin">
        <a-form-item label="用户名/邮箱" required>
          <a-input v-model="form.username" placeholder="请输入用户名或邮箱" size="large" autocomplete="username" />
        </a-form-item>
        <a-form-item label="密码" required>
          <a-input-password v-model="form.password" placeholder="请输入密码" size="large" autocomplete="current-password" />
        </a-form-item>
        <div v-if="formError" class="pa-form-error" role="alert" aria-live="assertive">
          {{ formError }}
        </div>
        <a-form-item>
          <a-button type="primary" html-type="submit" :loading="loading" long size="large">登录</a-button>
        </a-form-item>
      </a-form>
      <template #footer>
        还没有账号？
        <button class="auth-link" type="button" @click="router.push('/register')">创建账号</button>
      </template>
  </AuthShell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { login } from '@/api/auth'
import AuthShell from '@/components/AuthShell.vue'
import { rememberAccount } from '@/utils/accountSessions'

const router = useRouter()
const form = ref({ username: '', password: '' })
const loading = ref(false)
const formError = ref('')

const handleLogin = async () => {
  formError.value = ''
  if (!form.value.username || !form.value.password) {
    formError.value = '请填写用户名和密码'
    return
  }
  loading.value = true
  try {
    const response = await login(form.value)
    rememberAccount(response)
    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('user', JSON.stringify(response.user))
    Message.success('登录成功')
    router.push('/home')
  } catch (error: any) {
    const msg = error?.response?.data?.detail || '登录失败，请检查用户名和密码'
    formError.value = msg
  } finally { loading.value = false }
}
</script>

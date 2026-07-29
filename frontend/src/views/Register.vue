<template>
  <AuthShell title="创建账号" subtitle="建立你的论文工作台，集中阅读、分析和核对研究资料。" heading-id="register-heading">
      <a-form :model="form" layout="vertical" @submit="handleRegister">
        <a-form-item label="用户名" required>
          <a-input v-model="form.username" placeholder="请输入用户名" size="large" autocomplete="username" :max-length="50" />
        </a-form-item>
        <a-form-item label="邮箱" required>
          <a-input v-model="form.email" placeholder="请输入邮箱" size="large" autocomplete="email" :max-length="254" />
        </a-form-item>
        <a-form-item label="密码" required>
          <a-input-password
            v-model="form.password"
            placeholder="请输入密码"
            size="large"
            autocomplete="new-password"
            :max-length="128"
            aria-describedby="password-requirements"
          />
          <p
            id="password-requirements"
            class="field-guidance"
            :class="{ valid: passwordLengthValid }"
          >
            <span aria-hidden="true">{{ passwordLengthValid ? '✓' : '○' }}</span>
          至少 8 个字符
          </p>
        </a-form-item>
        <a-form-item label="确认密码" required>
          <a-input-password
            v-model="form.confirmPassword"
            placeholder="请再次输入密码"
            size="large"
            autocomplete="new-password"
            :max-length="128"
          />
        </a-form-item>
        <div v-if="formError" class="pa-form-error" role="alert" aria-live="assertive">
          {{ formError }}
        </div>
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
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { register } from '@/api/auth'
import AuthShell from '@/components/AuthShell.vue'

const router = useRouter()
const form = ref({ username: '', email: '', password: '', confirmPassword: '' })
const loading = ref(false)
const formError = ref('')
const passwordLengthValid = computed(() => (
  form.value.password.length >= 8 && form.value.password.length <= 128
))

const handleRegister = async () => {
  formError.value = ''

  if (!form.value.username || !form.value.email || !form.value.password || !form.value.confirmPassword) {
    formError.value = '请填写所有字段'
  } else if (form.value.username.length < 3) {
    formError.value = '用户名至少需要 3 个字符'
    } else if (form.value.password.length < 8) {
      formError.value = '密码至少需要 8 个字符'
  } else if (form.value.password !== form.value.confirmPassword) {
    formError.value = '两次输入的密码不一致'
  }

  if (formError.value) {
    Message.error(formError.value)
    return
  }

  loading.value = true
  try {
    await register({
      username: form.value.username,
      email: form.value.email,
      password: form.value.password
    })
    Message.success('注册成功，请登录')
    router.push('/login')
  } catch (error: any) {
    const detail = error.response?.data?.detail
    if (Array.isArray(detail)) {
      formError.value = detail
        .map(item => item?.msg)
        .filter(Boolean)
        .join('；') || '注册信息不符合要求'
    } else if (typeof detail === 'string') {
      formError.value = detail
    } else if (!error.response) {
      formError.value = '无法连接服务器，请稍后重试'
    } else {
      formError.value = '注册失败，请稍后重试'
    }
    Message.error(formError.value)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.field-guidance {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 7px 0 0;
  color: var(--pa-muted);
  font-size: 12px;
  line-height: 1.5;
}

.field-guidance.valid {
  color: var(--pa-success);
}

</style>

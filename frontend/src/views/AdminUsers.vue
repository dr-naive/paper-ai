<template>
  <AdminShell title="用户与权限" subtitle="设置用户角色与登录状态。系统默认管理员始终保持启用。">
      <template #actions><span class="user-count">{{ users.length }} 位用户</span></template>

      <div v-if="loading" class="loading-list" aria-label="正在加载用户">
        <span v-for="item in 4" :key="item"></span>
      </div>

      <div v-else-if="users.length" class="user-table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">用户</th>
              <th scope="col">角色</th>
              <th scope="col">登录权限</th>
              <th scope="col">注册时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="user in users" :key="user.id">
              <td>
                <div class="identity">
                  <span class="avatar" aria-hidden="true">{{ user.username.charAt(0).toUpperCase() }}</span>
                  <span>
                    <strong>{{ user.username }}</strong>
                    <small>{{ user.email }}</small>
                  </span>
                  <a-tag v-if="user.username === 'admin'" size="small">系统账户</a-tag>
                </div>
              </td>
              <td>
                <a-select
                  :model-value="user.role"
                  :disabled="user.username === 'admin' || savingId === user.id"
                  :aria-label="`设置 ${user.username} 的角色`"
                  @change="value => save(user, { role: value as UserRole })"
                >
                  <a-option value="user">普通用户</a-option>
                  <a-option value="admin">管理员</a-option>
                </a-select>
              </td>
              <td>
                <div class="access-control">
                  <a-switch
                    :model-value="user.is_active"
                    :disabled="user.username === 'admin' || savingId === user.id"
                    :aria-label="`${user.is_active ? '停用' : '启用'} ${user.username}`"
                    @change="value => save(user, { is_active: Boolean(value) })"
                  />
                  <span :class="{ inactive: !user.is_active }">
                    {{ user.is_active ? '已启用' : '已停用' }}
                  </span>
                </div>
              </td>
              <td class="date-cell">{{ formatDate(user.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="empty-state">
        <strong>暂无用户</strong>
        <span>新用户注册后会显示在这里。</span>
      </div>
  </AdminShell>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import AdminShell from '@/components/AdminShell.vue'
import {
  listUsers,
  updateUserPermissions,
  type UserResponse,
} from '@/api/auth'

type UserRole = UserResponse['role']

const users = ref<UserResponse[]>([])
const loading = ref(true)
const savingId = ref('')

const loadUsers = async () => {
  loading.value = true
  try {
    users.value = await listUsers()
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '用户列表加载失败')
  } finally {
    loading.value = false
  }
}

const save = async (
  user: UserResponse,
  update: Partial<Pick<UserResponse, 'role' | 'is_active'>>
) => {
  savingId.value = user.id
  try {
    const updated = await updateUserPermissions(user.id, update)
    const index = users.value.findIndex(item => item.id === user.id)
    if (index >= 0) users.value[index] = updated
    Message.success('权限已更新')
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '权限更新失败')
  } finally {
    savingId.value = ''
  }
}

const formatDate = (date: string) => new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
}).format(new Date(date))

onMounted(loadUsers)
</script>

<style scoped>
.user-count { flex: none; color: var(--pa-muted); font-size: 13px; }
.user-table-wrap { overflow-x: auto; border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); }
table { width: 100%; min-width: 760px; border-collapse: collapse; text-align: left; }
th { padding: 13px 20px; background: var(--pa-surface-soft); color: var(--pa-muted); font-size: 12px; font-weight: 600; }
td { padding: 16px 20px; border-top: 1px solid var(--pa-border); color: var(--pa-text); }
.identity { display: flex; align-items: center; gap: 12px; min-width: 260px; }
.identity > span:nth-child(2) { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.identity strong { color: var(--pa-ink); font-size: 14px; }
.identity small { max-width: 240px; overflow: hidden; color: var(--pa-muted); text-overflow: ellipsis; }
.avatar { display: grid; width: 36px; height: 36px; flex: none; place-items: center; border-radius: 50%; background: var(--pa-primary-soft); color: var(--pa-primary-hover); font-weight: 700; }
td :deep(.arco-select-view) { width: 126px; }
.access-control { display: flex; align-items: center; gap: 9px; white-space: nowrap; font-size: 13px; }
.access-control .inactive { color: var(--pa-danger); }
.date-cell { color: var(--pa-muted); font-size: 13px; white-space: nowrap; }
.loading-list { overflow: hidden; border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); }
.loading-list span { display: block; height: 68px; border-bottom: 1px solid var(--pa-border); background: linear-gradient(90deg, transparent, var(--pa-surface-soft), transparent); background-size: 240% 100%; animation: loading 1.4s ease-in-out infinite; }
.loading-list span:last-child { border-bottom: 0; }
.empty-state { display: flex; min-height: 240px; flex-direction: column; align-items: center; justify-content: center; gap: 8px; border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); }
.empty-state span { color: var(--pa-muted); }
@keyframes loading { to { background-position: -240% 0; } }
@media (prefers-reduced-motion: reduce) {
  .loading-list span { animation: none; }
}
</style>

<template>
  <AdminShell
    title="链路追踪"
    subtitle="免看日志即可定位慢请求、失败请求和多轮决策异常。"
  >
    <template #actions>
      <a-button :loading="loading" @click="loadTraces(1)">刷新数据</a-button>
    </template>

    <div v-if="loading && !tracesData" class="traces-skeleton">
      <span></span>
    </div>

    <template v-else-if="tracesData">
      <section class="panel traces-panel">
        <div class="panel-heading traces-heading">
          <div>
            <h2>最近 {{ tracesStatsLabel }}</h2>
            <p>共 {{ tracesData.total }} 条记录,支持按状态和耗时筛选</p>
          </div>
          <div class="traces-filters">
            <a-select
              v-model="traceFilterStatus"
              size="small"
              placeholder="状态"
              :style="{ width: '110px' }"
              @change="loadTraces(1)"
            >
              <a-option value="">全部状态</a-option>
              <a-option value="completed">成功</a-option>
              <a-option value="failed">失败</a-option>
            </a-select>
            <a-select
              v-model="traceFilterSlow"
              size="small"
              placeholder="耗时"
              :style="{ width: '130px' }"
              @change="loadTraces(1)"
            >
              <a-option value="">全部耗时</a-option>
              <a-option value="3000">≥ 3 秒</a-option>
              <a-option value="5000">≥ 5 秒</a-option>
              <a-option value="10000">≥ 10 秒</a-option>
            </a-select>
          </div>
        </div>

        <!-- 分位数 -->
        <div class="percentile-strip" v-if="tracesData.stats.count">
          <div>
            <span>样本数</span><strong>{{ tracesData.stats.count }}</strong>
          </div>
          <div>
            <span>首字 P50 / P90 / P95</span>
            <strong>
              {{ duration(tracesData.stats.first_token_ms.p50) }} /
              {{ duration(tracesData.stats.first_token_ms.p90) }} /
              {{ duration(tracesData.stats.first_token_ms.p95) }}
            </strong>
          </div>
          <div>
            <span>总耗时 P50 / P90 / P95</span>
            <strong>
              {{ duration(tracesData.stats.total_ms.p50) }} /
              {{ duration(tracesData.stats.total_ms.p90) }} /
              {{ duration(tracesData.stats.total_ms.p95) }}
            </strong>
          </div>
        </div>

        <!-- Trace 列表 -->
        <div class="traces-table-wrap">
          <table class="traces-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>用户</th>
                <th>状态</th>
                <th>首字</th>
                <th>总耗时</th>
                <th>检索</th>
                <th>LLM 次</th>
                <th>引用</th>
                <th>重试</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in tracesData.items" :key="item.trace_id" @click="openTraceDetail(item.trace_id)">
                <td class="trace-time">{{ item.recorded_at ? shortTime(item.recorded_at) : '—' }}</td>
                <td class="trace-user">{{ item.username || '匿名' }}</td>
                <td>
                  <span class="trace-status" :class="item.status">{{
                    item.status === 'completed' ? '成功' : item.status === 'failed' ? '失败' : item.status
                  }}</span>
                </td>
                <td :class="{ slow: item.first_token_ms != null && item.first_token_ms > 5000 }">{{
                  duration(item.first_token_ms)
                }}</td>
                <td :class="{ slow: item.total_ms != null && item.total_ms > 10000 }">{{
                  duration(item.total_ms)
                }}</td>
                <td>{{ duration(item.retrieval_ms) }}</td>
                <td :class="{ warn: item.model_calls > 2 }">{{ item.model_calls || 0 }}</td>
                <td>{{ item.citation_count }}</td>
                <td :class="{ warn: item.retry_count > 0 }">{{ item.retry_count }}</td>
                <td>
                  <a-link class="trace-detail-btn">详情</a-link>
                </td>
              </tr>
              <tr v-if="!tracesData.items.length">
                <td colspan="10" class="trace-empty">暂无追踪记录,完成一次问答后会自动生成</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="traces-pagination" v-if="tracesData.total > tracesData.page_size">
          <a-pagination
            :total="tracesData.total"
            :current="tracesData.page"
            :page-size="tracesData.page_size"
            show-total
            @change="loadTraces"
          />
        </div>
      </section>

      <!-- Trace 详情 Modal -->
      <a-modal
        v-model:visible="traceDetailVisible"
        :title="`链路详情 · ${selectedTraceId || ''}`"
        width="880px"
        unmount-on-close
        :mask-closable="true"
      >
        <div v-if="traceDetail" class="trace-detail">
          <div class="detail-row">
            <span>状态</span>
            <span class="trace-status" :class="traceDetail.status">{{
              traceDetail.status === 'completed' ? '成功' : traceDetail.status === 'failed' ? '失败' : traceDetail.status
            }}</span>
          </div>
          <div class="detail-row">
            <span>用户 / 会话</span>
            <strong>{{ traceDetail.user.username || '匿名' }} · {{ traceDetail.session.title || traceDetail.session.id }}</strong>
          </div>
          <div class="detail-grid">
            <div><span>首字时间</span><strong>{{ duration(traceDetail.first_token_ms) }}</strong></div>
            <div><span>总耗时</span><strong>{{ duration(traceDetail.total_ms) }}</strong></div>
            <div><span>检索耗时</span><strong>{{ duration(traceDetail.retrieval_ms) }}</strong></div>
            <div><span>LLM 调用</span><strong>{{ traceDetail.model_calls }} 次</strong></div>
            <div><span>思考 Token</span><strong>{{ number(traceDetail.thinking_tokens) }}</strong></div>
            <div><span>回答 Token</span><strong>{{ number(traceDetail.answer_tokens) }}</strong></div>
            <div><span>引用数量</span><strong>{{ traceDetail.citation_count }}</strong></div>
            <div><span>重试次数</span><strong class="warn" v-if="traceDetail.retry_count">{{ traceDetail.retry_count }}</strong><strong v-else>0</strong></div>
            <div><span>迭代轮数</span><strong>{{ traceDetail.iterations ?? '—' }}</strong></div>
            <div><span>快速路径</span><strong>{{ traceDetail.fast_path == null ? '—' : (traceDetail.fast_path ? '是 ✅' : '否(ReAct)') }}</strong></div>
            <div><span>二次检索</span><strong>{{ traceDetail.used_second_pass ? '是' : '否' }}</strong></div>
            <div><span>意图类型</span><strong>{{ traceDetail.intent || '—' }}</strong></div>
          </div>

          <div v-if="traceDetail.failure_stage" class="detail-failure">
            <strong>失败阶段:</strong>{{ traceDetail.failure_stage }}
          </div>

          <details v-if="traceDetail.question || traceDetail.answer" class="detail-block">
            <summary>问题与回答</summary>
            <div class="detail-qa">
              <p class="detail-q"><strong>问:</strong>{{ traceDetail.question }}</p>
              <p class="detail-a"><strong>答:</strong>{{ traceDetail.answer }}</p>
            </div>
          </details>

          <details v-if="traceDetail.tool_calls && traceDetail.tool_calls.length" class="detail-block">
            <summary>Tool 调用明细({{ traceDetail.tool_calls.length }} 次)</summary>
            <table class="tool-calls-table">
              <thead>
                <tr><th>Tool</th><th>耗时</th><th>参数</th><th>结果</th></tr>
              </thead>
              <tbody>
                <tr v-for="(tc, i) in traceDetail.tool_calls" :key="i">
                  <td><code>{{ tc.name }}</code></td>
                  <td :class="{ slow: tc.elapsed_ms > 3000 }">{{ tc.elapsed_ms != null ? `${(tc.elapsed_ms / 1000).toFixed(2)}s` : '—' }}</td>
                  <td class="tool-args">{{ formatToolArgs(tc.args) }}</td>
                  <td>
                    <span v-if="tc.ok !== false" class="ok">✅</span>
                    <span v-else class="fail">❌</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </details>

          <details v-if="traceDetail.intent_analysis" class="detail-block">
            <summary>意图分析</summary>
            <pre class="detail-pre">{{ JSON.stringify(traceDetail.intent_analysis, null, 2) }}</pre>
          </details>
        </div>
        <div v-else class="trace-detail-loading">加载中...</div>
      </a-modal>
    </template>
  </AdminShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import AdminShell from '@/components/AdminShell.vue'
import {
  listTraces,
  getTraceDetail,
  type TraceListResponse,
  type TraceDetailResponse,
} from '@/api/admin'

const loading = ref(true)
const tracesData = ref<TraceListResponse | null>(null)
const traceFilterStatus = ref('')
const traceFilterSlow = ref<string>('')
const tracesStatsLabel = computed(() => traceFilterSlow.value ? `耗时 ≥ ${Number(traceFilterSlow.value)/1000}s` : '7 天')

const loadTraces = async (page = 1) => {
  loading.value = true
  try {
    tracesData.value = await listTraces({
      page,
      page_size: 20,
      status: traceFilterStatus.value || undefined,
      min_total_ms: traceFilterSlow.value ? Number(traceFilterSlow.value) : undefined,
      max_age_days: 7,
    })
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '链路追踪加载失败')
  } finally {
    loading.value = false
  }
}

const traceDetailVisible = ref(false)
const selectedTraceId = ref('')
const traceDetail = ref<TraceDetailResponse | null>(null)
const openTraceDetail = async (traceId: string) => {
  selectedTraceId.value = traceId
  traceDetail.value = null
  traceDetailVisible.value = true
  try {
    traceDetail.value = await getTraceDetail(traceId)
  } catch (error: any) {
    Message.error(error?.response?.data?.detail || '详情加载失败')
  }
}

const number = (value: number) => new Intl.NumberFormat('zh-CN').format(value)
const duration = (value: number | null) => value == null ? '暂无' : value >= 1000 ? `${(value / 1000).toFixed(1)} 秒` : `${Math.round(value)} 毫秒`
const shortTime = (iso: string) => new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
const formatToolArgs = (args: any) => {
  if (args == null) return '—'
  try {
    const s = typeof args === 'string' ? args : JSON.stringify(args)
    return s.length > 80 ? s.slice(0, 80) + '…' : s
  } catch { return String(args) }
}

onMounted(() => loadTraces(1))
</script>

<style scoped>
.traces-skeleton { margin-top: 26px; height: 80px; background: linear-gradient(90deg, var(--pa-surface-soft), var(--pa-surface), var(--pa-surface-soft)); background-size: 220% 100%; animation: traces-loading 1.4s ease-in-out infinite; border: 1px solid var(--pa-border); border-radius: 12px; }
@keyframes traces-loading { to { background-position: -220% 0; } }

.panel { border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); overflow: hidden; }
.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; padding: 20px 22px 16px; }
.panel-heading h2 { color: var(--pa-ink); font-size: 17px; }
.panel-heading p { margin-top: 6px; color: var(--pa-muted); font-size: 12px; }
.traces-filters { display: flex; align-items: center; gap: 8px; }
.percentile-strip { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px; margin: 0 22px; padding: 14px 18px; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface-soft); }
.percentile-strip div { display: flex; flex-direction: column; gap: 5px; }
.percentile-strip span { color: var(--pa-muted); font-size: 11px; }
.percentile-strip strong { color: var(--pa-ink); font-size: 13px; }
.traces-table-wrap { padding: 16px 22px 10px; overflow-x: auto; }
.traces-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.traces-table th, .traces-table td { padding: 9px 10px; border-bottom: 1px solid var(--pa-border); text-align: left; white-space: nowrap; }
.traces-table th { color: var(--pa-muted); font-weight: 500; font-size: 11px; background: var(--pa-surface-soft); }
.traces-table tbody tr { cursor: pointer; transition: background 0.15s; }
.traces-table tbody tr:hover { background: var(--pa-surface-soft); }
.traces-table td.slow { color: var(--pa-danger); font-weight: 600; }
.traces-table td.warn { color: #b45309; font-weight: 600; }
.trace-time { color: var(--pa-muted); font-variant-numeric: tabular-nums; }
.trace-user { font-weight: 500; }
.trace-status { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 500; }
.trace-status.completed { background: rgba(16, 185, 129, 0.12); color: #059669; }
.trace-status.failed { background: rgba(239, 68, 68, 0.12); color: var(--pa-danger); }
.trace-status:not(.completed):not(.failed) { background: var(--pa-surface-soft); color: var(--pa-muted); }
.trace-empty { text-align: center; padding: 32px 0 !important; color: var(--pa-muted); }
.trace-detail-btn { font-size: 11px; }
.traces-pagination { padding: 14px 22px 20px; display: flex; justify-content: flex-end; }

.trace-detail { display: flex; flex-direction: column; gap: 14px; }
.detail-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--pa-surface-soft); border-radius: 8px; }
.detail-row > span:first-child { color: var(--pa-muted); font-size: 12px; }
.detail-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.detail-grid > div { padding: 10px 12px; border: 1px solid var(--pa-border); border-radius: 8px; display: flex; flex-direction: column; gap: 4px; }
.detail-grid span { color: var(--pa-muted); font-size: 11px; }
.detail-grid strong { color: var(--pa-ink); font-size: 14px; }
.detail-grid .warn { color: #b45309; }
.detail-failure { padding: 12px 16px; background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 8px; color: var(--pa-danger); font-size: 13px; }
.detail-block { border: 1px solid var(--pa-border); border-radius: 8px; overflow: hidden; }
.detail-block > summary { padding: 11px 14px; background: var(--pa-surface-soft); cursor: pointer; font-size: 13px; font-weight: 500; color: var(--pa-ink); }
.detail-block > summary:hover { background: var(--pa-border); }
.detail-qa { padding: 14px 16px; }
.detail-qa p { margin: 8px 0; font-size: 13px; line-height: 1.7; }
.detail-q strong { color: var(--pa-muted); }
.detail-a strong { color: var(--pa-muted); }
.tool-calls-table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12px; }
.tool-calls-table th, .tool-calls-table td { padding: 8px 12px; border-bottom: 1px solid var(--pa-border); text-align: left; }
.tool-calls-table th { background: var(--pa-surface-soft); color: var(--pa-muted); font-weight: 500; font-size: 11px; }
.tool-calls-table td.slow { color: var(--pa-danger); font-weight: 600; }
.tool-calls-table .tool-args { color: var(--pa-muted); font-family: ui-monospace, monospace; font-size: 11px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; }
.tool-calls-table .ok { color: #059669; }
.tool-calls-table .fail { color: var(--pa-danger); }
.detail-pre { padding: 14px 16px; margin: 0; background: var(--pa-surface); color: var(--pa-ink); font-size: 12px; overflow-x: auto; }
.trace-detail-loading { padding: 40px; text-align: center; color: var(--pa-muted); }

@media (max-width: 900px) {
  .percentile-strip { grid-template-columns: 1fr; }
  .detail-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>

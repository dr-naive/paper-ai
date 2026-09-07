<template>
  <AdminShell title="系统运行概览" subtitle="用户活动、AI 用量、服务状态和质量评测集中在这里。">
      <template #actions>
        <div class="heading-actions">
          <span v-if="data">更新于 {{ formatTime(data.generated_at) }}</span>
          <a-button :loading="loading" @click="loadDashboard">刷新数据</a-button>
        </div>
      </template>

      <div v-if="loading && !data" class="dashboard-skeleton" aria-label="正在汇总系统数据">
        <span class="skeleton-strip"></span>
        <div class="skeleton-metrics"><span v-for="item in 4" :key="item"></span></div>
        <div class="skeleton-panels"><span></span><span></span></div>
      </div>

      <template v-else-if="data">
        <section class="status-strip" aria-label="服务状态">
          <div v-for="service in services" :key="service.label">
            <span class="status-dot" :class="service.state"></span>
            <span>{{ service.label }}</span>
            <strong>{{ service.state === 'healthy' ? '正常' : '异常' }}</strong>
          </div>
        </section>

        <section class="metrics" aria-label="核心指标">
          <article>
            <span>累计用户</span>
            <strong>{{ number(data.users.total) }}</strong>
            <small>近 7 日新增 {{ data.users.new_7d }}</small>
          </article>
          <article>
            <span>累计论文</span>
            <strong>{{ number(data.usage.papers_total) }}</strong>
            <small>近 7 日上传 {{ data.usage.papers_7d }}</small>
          </article>
          <article>
            <span>累计问答</span>
            <strong>{{ number(data.usage.questions_total) }}</strong>
            <small>今日 {{ data.usage.questions_today }}</small>
          </article>
          <article>
            <span>累计生成 Token</span>
            <strong>{{ compactNumber(data.ai.total_tokens) }}</strong>
            <small>回答侧估算，不等同账单</small>
          </article>
        </section>

        <section class="dashboard-grid">
          <AdminEvaluationPanel />

          <article id="ai-usage" class="panel usage-panel">
            <div class="panel-heading">
              <div><h2>近 7 日使用趋势</h2><p>问答次数与回答侧 Token 消耗，两组数据按各自峰值缩放</p></div>
              <div class="legend"><span class="question-key"></span>问答 <span class="token-key"></span>Token</div>
            </div>
            <div class="trend-chart" role="group" aria-label="近七日系统使用趋势柱状图">
              <div
                v-for="item in data.trend"
                :key="item.date"
                class="trend-day"
              >
                <div class="bars">
                  <button
                    type="button"
                    class="metric-bar question-bar"
                    :style="{ height: barHeight(item.questions, maxQuestions) }"
                    :aria-label="`${item.date}，问答 ${number(item.questions)} 次`"
                  >
                    <span class="bar-tooltip" role="tooltip">问答 {{ number(item.questions) }} 次</span>
                  </button>
                  <button
                    type="button"
                    class="metric-bar token-bar"
                    :style="{ height: barHeight(item.tokens, maxTokens) }"
                    :aria-label="`${item.date}，Token ${number(item.tokens)}`"
                  >
                    <span class="bar-tooltip" role="tooltip">Token {{ number(item.tokens) }}</span>
                  </button>
                </div>
                <span>{{ shortDate(item.date) }}</span>
              </div>
            </div>
            <table class="pa-sr-only">
              <caption>近七日系统使用趋势明细</caption>
              <thead><tr><th scope="col">日期</th><th scope="col">问答次数</th><th scope="col">Token 数</th></tr></thead>
              <tbody>
                <tr v-for="item in data.trend" :key="`trend-row-${item.date}`">
                  <th scope="row">{{ item.date }}</th>
                  <td>{{ item.questions }}</td>
                  <td>{{ item.tokens }}</td>
                </tr>
              </tbody>
            </table>
          </article>

          <article class="panel ai-panel">
            <div class="panel-heading"><div><h2>AI 回答链路</h2><p>从持久化 Trace 汇总</p></div></div>
            <dl>
              <div><dt>回答任务</dt><dd>{{ data.ai.answer_runs }}</dd></div>
              <div><dt>成功率</dt><dd>{{ percent(data.ai.success_rate) }}</dd></div>
              <div><dt>平均首字</dt><dd>{{ duration(data.ai.avg_first_token_ms) }}</dd></div>
              <div><dt>平均总耗时</dt><dd>{{ duration(data.ai.avg_total_ms) }}</dd></div>
              <div><dt>平均检索</dt><dd>{{ duration(data.ai.avg_retrieval_ms) }}</dd></div>
              <div><dt>累计引用</dt><dd>{{ data.ai.citations_total }}</dd></div>
              <div><dt>思考 Token</dt><dd>{{ compactNumber(data.ai.thinking_tokens) }}</dd></div>
              <div><dt>回答 Token</dt><dd>{{ compactNumber(data.ai.answer_tokens) }}</dd></div>
            </dl>
          </article>

          <article id="evaluations" class="panel evaluation-panel">
            <div class="panel-heading">
              <div><h2>最新质量评测</h2><p>后端评测报告的最近一次结果</p></div>
            </div>
            <div class="evaluation-block">
              <h3>检索质量</h3>
              <template v-if="retrievalSummary">
                <div class="evaluation-metrics">
                  <span>Hit@K <strong>{{ percent(retrievalSummary.hit_at_k) }}</strong></span>
                  <span>Recall@K <strong>{{ percent(retrievalSummary.evidence_recall_at_k) }}</strong></span>
                  <span>MRR <strong>{{ decimal(retrievalSummary.mrr) }}</strong></span>
                </div>
                <small>{{ reportDate(data.evaluations.retrieval?.generated_at) }}</small>
              </template>
              <p v-else>暂无检索评测报告</p>
            </div>
            <div class="evaluation-block">
              <h3>端到端回答</h3>
              <template v-if="e2eSummary">
                <div class="evaluation-metrics">
                  <span>有效回答 <strong>{{ percent(e2eSummary.valid_answer_rate) }}</strong></span>
                  <span>引用支持 <strong>{{ percent(e2eSummary.citation_precision) }}</strong></span>
                  <span>页码准确 <strong>{{ percent(e2eSummary.page_accuracy) }}</strong></span>
                </div>
                <small>{{ reportDate(data.evaluations.e2e?.generated_at) }}</small>
              </template>
              <p v-else>暂无端到端评测报告</p>
            </div>
          </article>

          <article class="panel activity-panel">
            <div class="panel-heading"><div><h2>最近系统活动</h2><p>快速确认内容与用户增长是否正常</p></div></div>
            <div class="activity-columns">
              <section>
                <h3>最近上传论文</h3>
                <ul v-if="data.recent.papers.length">
                  <li v-for="paper in data.recent.papers" :key="paper.id">
                    <span><strong>{{ paper.title }}</strong><small>{{ paper.username }}</small></span>
                    <time>{{ shortDay(paper.uploaded_at) }}</time>
                  </li>
                </ul>
                <p v-else>暂无论文上传记录</p>
              </section>
              <section>
                <h3>最近注册用户</h3>
                <ul v-if="data.recent.users.length">
                  <li v-for="user in data.recent.users" :key="user.id">
                    <span><strong>{{ user.username }}</strong><small>{{ user.role === 'admin' ? '管理员' : '普通用户' }}</small></span>
                    <time>{{ shortDay(user.created_at) }}</time>
                  </li>
                </ul>
                <p v-else>暂无用户注册记录</p>
              </section>
            </div>
          </article>
        </section>
      </template>
  </AdminShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import AdminShell from '@/components/AdminShell.vue'
import AdminEvaluationPanel from '@/components/admin/AdminEvaluationPanel.vue'
import { getAdminDashboard, type AdminDashboardData } from '@/api/admin'

const data = ref<AdminDashboardData | null>(null)
const loading = ref(true)
const services = computed(() => data.value ? [
  { label: '数据库', state: data.value.system.database },
  { label: 'Redis', state: data.value.system.redis },
  { label: '后台 Worker', state: data.value.system.worker },
] : [])
const maxQuestions = computed(() => Math.max(1, ...(data.value?.trend.map(item => item.questions) || [1])))
const maxTokens = computed(() => Math.max(1, ...(data.value?.trend.map(item => item.tokens) || [1])))
const retrievalSummary = computed(() => data.value?.evaluations.retrieval?.summary)
const e2eSummary = computed(() => data.value?.evaluations.e2e?.summary)

const loadDashboard = async () => {
  loading.value = true
  try { data.value = await getAdminDashboard() }
  catch (error: any) { Message.error(error?.response?.data?.detail || '系统数据加载失败') }
  finally { loading.value = false }
}
const number = (value: number) => new Intl.NumberFormat('zh-CN').format(value)
const compactNumber = (value: number) => new Intl.NumberFormat('zh-CN', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
const percent = (value: number | null | undefined) => value == null ? '暂无' : `${(value * 100).toFixed(1)}%`
const decimal = (value: number | null | undefined) => value == null ? '暂无' : value.toFixed(3)
const duration = (value: number | null) => value == null ? '暂无' : value >= 1000 ? `${(value / 1000).toFixed(1)} 秒` : `${Math.round(value)} 毫秒`
const barHeight = (value: number, max: number) => value ? `${Math.max(8, value / max * 100)}%` : '2px'
const shortDate = (date: string) => date.slice(5).replace('-', '/')
const shortDay = (date: string) => new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit' }).format(new Date(date))
const formatTime = (date: string) => new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date(date))
const reportDate = (date?: string | null) => date ? `运行于 ${new Intl.DateTimeFormat('zh-CN').format(new Date(date))}` : '未记录运行时间'
onMounted(loadDashboard)
</script>

<style scoped>
.panel-heading p { margin-top: 7px; color: var(--pa-muted); font-size: 13px; }
.heading-actions { display: flex; align-items: center; gap: 14px; color: var(--pa-muted); font-size: 12px; }
.dashboard-skeleton { margin-top: 26px; overflow: hidden; }
.dashboard-skeleton span { display: block; background: linear-gradient(90deg, var(--pa-surface-soft), var(--pa-surface), var(--pa-surface-soft)); background-size: 220% 100%; animation: dashboard-loading 1.4s ease-in-out infinite; }
.skeleton-strip { height: 44px; border: 1px solid var(--pa-border); border-radius: 10px; }
.skeleton-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; margin-top: 16px; overflow: hidden; border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-border); }
.skeleton-metrics span { height: 126px; }
.skeleton-panels { display: grid; grid-template-columns: 1.35fr .65fr; gap: 16px; margin-top: 16px; }
.skeleton-panels span { height: 320px; border: 1px solid var(--pa-border); border-radius: 12px; }
@keyframes dashboard-loading { to { background-position: -220% 0; } }
.status-strip { display: flex; gap: 24px; margin-top: 26px; padding: 12px 16px; border: 1px solid var(--pa-border); border-radius: 10px; background: var(--pa-surface); }
.status-strip div { display: flex; align-items: center; gap: 7px; color: var(--pa-muted); font-size: 12px; }
.status-strip strong { color: var(--pa-text); font-weight: 600; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--pa-danger); }
.status-dot.healthy { background: var(--pa-success); }
.metrics { display: grid; grid-template-columns: repeat(4, 1fr); margin-top: 16px; overflow: hidden; border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); }
.metrics article { display: flex; min-height: 126px; flex-direction: column; justify-content: center; padding: 22px 24px; border-right: 1px solid var(--pa-border); }
.metrics article:last-child { border-right: 0; }
.metrics span { color: var(--pa-muted); font-size: 13px; }
.metrics strong { margin: 8px 0; color: var(--pa-ink); font-size: 29px; line-height: 1; }
.metrics small { color: var(--pa-muted); font-size: 11px; }
.dashboard-grid { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(330px, .65fr); gap: 16px; margin-top: 16px; }
.panel { border: 1px solid var(--pa-border); border-radius: 12px; background: var(--pa-surface); }
.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; padding: 20px 22px; border-bottom: 1px solid var(--pa-border); }
.panel-heading h2 { color: var(--pa-ink); font-size: 16px; }
.legend { display: flex; align-items: center; gap: 6px; color: var(--pa-muted); font-size: 11px; }
.legend span { width: 8px; height: 8px; border-radius: 2px; }
.question-key, .question-bar { background: var(--pa-primary); }
.token-key, .token-bar { background: var(--pa-info); }
.trend-chart { display: flex; height: 240px; align-items: stretch; gap: 12px; padding: 26px 24px 18px; }
.trend-day { position: relative; display: flex; min-width: 0; flex: 1; flex-direction: column; align-items: center; gap: 9px; color: var(--pa-muted); font-size: 10px; }
.bars { display: flex; width: 100%; flex: 1; align-items: flex-end; justify-content: center; gap: 4px; border-bottom: 1px solid var(--pa-border); }
.metric-bar { position: relative; width: min(18px, 38%); min-height: 2px; padding: 0; flex: none; border: 0; border-radius: 3px 3px 0 0; cursor: default; transform-origin: center bottom; transition: height 180ms ease-out, filter 160ms ease-out, transform 160ms ease-out, box-shadow 160ms ease-out; }
.metric-bar::after { content: ''; position: absolute; z-index: 4; top: 50%; left: 100%; width: 34px; height: 1px; background: oklch(0.54 0.012 50 / 0.72); opacity: 0; pointer-events: none; transform: rotate(-28deg); transform-origin: left center; transition: opacity 140ms ease-out; }
.metric-bar:hover,
.metric-bar:focus-visible { z-index: 3; filter: brightness(1.18) saturate(1.08); transform: scaleX(1.16) scaleY(1.025); box-shadow: 0 0 0 2px oklch(1 0 / 0.72), 0 4px 12px oklch(0.25 0.03 45 / 0.18); outline: none; }
.bar-tooltip { position: absolute; z-index: 5; top: calc(50% - 16px); left: calc(100% + 30px); min-width: max-content; padding: 9px 12px; border: 1px solid oklch(0.82 0.015 55 / 0.82); border-radius: 8px; background: oklch(0.995 0.003 55 / 0.86); box-shadow: var(--pa-shadow-md); color: var(--pa-ink); font-size: 11px; font-weight: 600; line-height: 1.2; opacity: 0; pointer-events: none; transform: translateY(-50%); visibility: hidden; backdrop-filter: blur(8px); transition: opacity 140ms ease-out, visibility 140ms ease-out; }
.trend-day:last-child .bar-tooltip { right: calc(100% + 30px); left: auto; }
.trend-day:last-child .metric-bar::after { right: 100%; left: auto; transform: rotate(28deg); transform-origin: right center; }
.metric-bar:hover .bar-tooltip,
.metric-bar:focus-visible .bar-tooltip,
.metric-bar:hover::after,
.metric-bar:focus-visible::after { opacity: 1; visibility: visible; }
.ai-panel dl { display: grid; grid-template-columns: repeat(2, 1fr); padding: 10px 22px 18px; }
.ai-panel dl div { padding: 14px 0; border-bottom: 1px solid var(--pa-border); }
.ai-panel dl div:nth-last-child(-n+2) { border-bottom: 0; }
.ai-panel dt { color: var(--pa-muted); font-size: 11px; }
.ai-panel dd { margin-top: 5px; color: var(--pa-ink); font-size: 16px; font-weight: 650; }
.evaluation-panel { display: grid; grid-column: 1 / -1; grid-template-columns: repeat(2, 1fr); }
.evaluation-panel .panel-heading { grid-column: 1 / -1; }
.evaluation-block { padding: 17px 22px; }
.evaluation-block + .evaluation-block { border-left: 1px solid var(--pa-border); }
.evaluation-block h3 { color: var(--pa-ink); font-size: 13px; }
.evaluation-block p, .evaluation-block small { color: var(--pa-muted); font-size: 11px; }
.evaluation-metrics { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 11px 0 8px; color: var(--pa-muted); font-size: 11px; }
.evaluation-metrics strong { display: block; margin-top: 3px; color: var(--pa-ink); font-size: 16px; }
.activity-panel { grid-column: 1 / -1; }
.activity-columns { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0; }
.activity-columns section { padding: 18px 22px 22px; }
.activity-columns section + section { border-left: 1px solid var(--pa-border); }
.activity-columns h3 { margin-bottom: 8px; color: var(--pa-ink); font-size: 13px; }
.activity-columns ul { list-style: none; }
.activity-columns li { display: flex; align-items: center; justify-content: space-between; gap: 18px; padding: 10px 0; border-bottom: 1px solid var(--pa-border); }
.activity-columns li:last-child { border-bottom: 0; }
.activity-columns li > span { display: flex; min-width: 0; flex-direction: column; gap: 3px; }
.activity-columns strong { overflow: hidden; color: var(--pa-text); font-size: 12px; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.activity-columns small, .activity-columns time, .activity-columns p { color: var(--pa-muted); font-size: 11px; }
@media (max-width: 900px) { .dashboard-grid { grid-template-columns: 1fr; } }
@media (max-width: 680px) {
  .skeleton-metrics { grid-template-columns: repeat(2, 1fr); }
  .skeleton-panels { grid-template-columns: 1fr; }
  .metrics { grid-template-columns: repeat(2, 1fr); }
  .metrics article:nth-child(2) { border-right: 0; }
  .metrics article:nth-child(-n+2) { border-bottom: 1px solid var(--pa-border); }
  .status-strip { flex-wrap: wrap; gap: 10px 18px; }
  .evaluation-panel { grid-template-columns: 1fr; }
  .evaluation-block + .evaluation-block { border-top: 1px solid var(--pa-border); border-left: 0; }
  .activity-columns { grid-template-columns: 1fr; }
  .activity-columns section + section { border-top: 1px solid var(--pa-border); border-left: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .metric-bar,
  .metric-bar,
  .metric-bar::after,
  .bar-tooltip { transition: none; }
  .dashboard-skeleton span { animation: none; }
}
</style>

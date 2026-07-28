<template>
  <div class="guide-page">
    <ProductHeader context="使用指南">
      <template #actions>
        <a-button type="primary" @click="$router.push('/papers')">进入论文工作台</a-button>
      </template>
    </ProductHeader>

    <main class="guide-shell">
      <div class="guide-layout">
        <nav class="guide-nav" aria-label="指南目录">
          <strong>本页内容</strong>
          <a v-for="item in navigation" :key="item.id" :href="`#${item.id}`">{{ item.label }}</a>
        </nav>

        <div class="guide-main">
          <header class="guide-intro">
            <span>PaperAI 使用指南</span>
            <h1>从上传论文到核对原文</h1>
            <p>按照下面的流程完成第一次论文精读，也可以直接跳到遇到问题的部分。</p>
          </header>

          <article class="guide-content">
          <section id="upload">
            <div class="section-heading">
              <span>01</span>
              <div>
                <h2>上传并等待解析</h2>
                <p>论文解析完成后，目录、正文和问答能力才会完整可用。</p>
              </div>
            </div>
            <ol>
              <li>进入“我的论文”，点击“上传论文”。</li>
              <li>选择 PDF 文件并开始上传，不要在上传过程中重复点击。</li>
              <li>等待解析状态完成。如果图表仍在处理中，可以先阅读正文。</li>
            </ol>
            <div class="guide-note">
              <strong>建议</strong>
              <span>优先上传文字可复制的 PDF。纯扫描件、复杂双栏排版和异常字体可能降低目录与原文定位精度。</span>
            </div>
          </section>

          <section id="outline">
            <div class="section-heading">
              <span>02</span>
              <div>
                <h2>使用目录阅读</h2>
                <p>左侧目录用于浏览论文结构，不同层级的章节可以分别展开和收起。</p>
              </div>
            </div>
            <ul>
              <li>点击章节标题，PDF 会跳转到对应页面。</li>
              <li>点击目录边缘的收起按钮，可以为正文留出更多空间。</li>
              <li>系统会记录最近阅读位置，再次进入论文时自动恢复。</li>
              <li>目录明显缺失时，可以使用目录区域的重新抽取功能。</li>
            </ul>
          </section>

          <section id="questions">
            <div class="section-heading">
              <span>03</span>
              <div>
                <h2>提出更有效的问题</h2>
                <p>问题越明确，检索到完整证据的概率越高。</p>
              </div>
            </div>
            <div class="question-examples">
              <div>
                <span>总结</span>
                <p>这篇论文解决了什么问题，主要贡献有哪些？</p>
              </div>
              <div>
                <span>方法</span>
                <p>作者的方法包含哪些模块，各模块分别起什么作用？</p>
              </div>
              <div>
                <span>比较</span>
                <p>方法 A 与方法 B 在设计和实验结果上有什么区别？</p>
              </div>
              <div>
                <span>证据</span>
                <p>论文用哪些实验支持核心结论？请分别说明。</p>
              </div>
            </div>
            <p>涉及两个对象或多个章节时，请在问题中明确写出比较对象。系统会分别检索证据，再合并回答。</p>
          </section>

          <section id="thinking">
            <div class="section-heading">
              <span>04</span>
              <div>
                <h2>普通回答与深度思考</h2>
                <p>两种模式使用同一篇论文，但生成过程和耗时不同。</p>
              </div>
            </div>
            <div class="mode-table">
              <div class="mode-row mode-head">
                <span>模式</span><span>适合问题</span><span>特点</span>
              </div>
              <div class="mode-row">
                <strong>普通回答</strong><span>事实查找、章节总结、简单解释</span><span>响应更快</span>
              </div>
              <div class="mode-row">
                <strong>深度思考</strong><span>跨章节分析、方法对比、多证据归纳</span><span>耗时更长，可展开查看思考内容</span>
              </div>
            </div>
            <p>生成期间可以停止回答。网络短暂中断或页面刷新后，系统会尝试恢复正在进行的任务或最终答案。</p>
          </section>

          <section id="citations">
            <div class="section-heading">
              <span>05</span>
              <div>
                <h2>核对引用与原文</h2>
                <p>不要只看回答结论，重要信息应回到论文原文核对。</p>
              </div>
            </div>
            <ol>
              <li>回答完成后，查看下方引用的章节、页码和原文片段。</li>
              <li>点击一条引用，PDF 会跳转到对应页面并高亮相关区域。</li>
              <li>如果只能定位页面而没有框选，说明该片段缺少可靠的版面坐标，请在页面内核对原文。</li>
            </ol>
          </section>

          <section id="sessions">
            <div class="section-heading">
              <span>06</span>
              <div>
                <h2>管理问答与阅读记录</h2>
                <p>问答会话和单条回答均可以独立管理。</p>
              </div>
            </div>
            <ul>
              <li>使用会话选择器切换不同研究主题。</li>
              <li>问题右侧的“…”可以编辑问题或删除单组问答。</li>
              <li>编辑会把原问题放回输入框，不会直接覆盖旧回答。</li>
              <li>“我的论文”会展示最近阅读和最近问题，方便继续研究。</li>
            </ul>
          </section>

          <section id="troubleshooting">
            <div class="section-heading">
              <span>07</span>
              <div>
                <h2>常见问题</h2>
                <p>先确认问题出现在哪个阶段，再决定是否重试。</p>
              </div>
            </div>
            <details>
              <summary>PDF 一直加载或显示失败怎么办？</summary>
              <p>先刷新页面并确认网络正常。如果只有某一篇失败，重新打开该论文；仍然失败时检查原 PDF 是否可以正常打开。</p>
            </details>
            <details>
              <summary>目录层级或页码不正确怎么办？</summary>
              <p>使用目录区域的重新抽取功能。复杂目录、扫描页和页码标记不一致的论文可能需要重新解析。</p>
            </details>
            <details>
              <summary>回答只找到一部分证据怎么办？</summary>
              <p>明确问题中的对象、指标或章节范围。比较问题最好同时写出两边对象，也可以拆成两个问题后再要求综合比较。</p>
            </details>
            <details>
              <summary>引用定位略有偏差怎么办？</summary>
              <p>框选依赖 PDF 文本坐标。遇到双栏、跨行、表格或字体编码异常时，仍应结合引用片段在对应页面人工核对。</p>
            </details>
          </section>

            <div class="guide-finish">
              <div>
                <h2>现在可以开始了</h2>
                <p>进入论文工作台，上传 PDF 或继续阅读已有论文。</p>
              </div>
              <a-button type="primary" size="large" @click="$router.push('/papers')">进入论文工作台</a-button>
            </div>
          </article>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import ProductHeader from '@/components/ProductHeader.vue'

const navigation = [
  { id: 'upload', label: '上传与解析' },
  { id: 'outline', label: '目录阅读' },
  { id: 'questions', label: '有效提问' },
  { id: 'thinking', label: '深度思考' },
  { id: 'citations', label: '引用定位' },
  { id: 'sessions', label: '会话管理' },
  { id: 'troubleshooting', label: '常见问题' },
]
</script>

<style scoped>
.guide-page {
  min-height: 100vh;
  background: var(--pa-bg);
  color: var(--pa-text);
}

.guide-shell {
  width: min(100% - 48px, 1440px);
  margin: 0 auto;
  padding: 34px 0 88px;
}

.guide-intro {
  max-width: 980px;
  padding: 48px 52px 42px;
  border-bottom: 1px solid var(--pa-border);
}

.guide-intro > span {
  color: var(--pa-primary);
  font-size: 14px;
  font-weight: 650;
}

.guide-intro h1 {
  margin: 10px 0 14px;
  color: var(--pa-ink);
  font-size: clamp(34px, 5vw, 52px);
  letter-spacing: -0.035em;
  line-height: 1.12;
  text-wrap: balance;
}

.guide-intro p {
  margin: 0;
  color: var(--pa-muted);
  font-size: 17px;
  line-height: 1.7;
}

.guide-layout {
  display: grid;
  grid-template-columns: 230px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.guide-nav {
  position: sticky;
  top: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-self: start;
  min-height: calc(100vh - 40px);
  padding: 28px 22px;
  border: 1px solid var(--pa-border);
  border-radius: 10px;
  background: #fff;
  box-shadow: 0 10px 28px rgb(52 37 30 / 0.04);
}

.guide-nav strong {
  margin-bottom: 10px;
  color: var(--pa-ink);
  font-size: 13px;
}

.guide-nav a {
  padding: 8px 10px;
  border-radius: 7px;
  color: var(--pa-muted);
  font-size: 13px;
  text-decoration: none;
}

.guide-nav a:hover {
  background: var(--pa-primary-soft);
  color: var(--pa-primary);
}

.guide-nav a:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 1px;
}

.guide-main {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--pa-border);
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 16px 42px rgb(52 37 30 / 0.06);
}

.guide-content {
  min-width: 0;
}

.guide-content section {
  padding: 42px 52px 46px;
  margin: 0;
  border-bottom: 1px solid var(--pa-border);
  scroll-margin-top: 24px;
}

.guide-content section:last-of-type {
  border-bottom: 0;
}

.section-heading {
  display: flex;
  gap: 18px;
  align-items: flex-start;
  margin-bottom: 24px;
}

.section-heading > span {
  min-width: 36px;
  padding-top: 5px;
  color: var(--pa-primary);
  font-size: 13px;
  font-weight: 700;
}

.section-heading h2 {
  margin: 0 0 7px;
  color: var(--pa-ink);
  font-size: 25px;
  letter-spacing: -0.02em;
}

.section-heading p,
.guide-content > section > p {
  margin: 0;
  color: var(--pa-muted);
  font-size: 14px;
  line-height: 1.75;
}

.guide-content ol,
.guide-content ul {
  margin: 0;
  padding-left: 54px;
  color: var(--pa-text);
}

.guide-content li {
  padding-left: 5px;
  margin-bottom: 11px;
  line-height: 1.75;
}

.guide-note {
  display: flex;
  gap: 14px;
  margin: 24px 0 0 54px;
  padding: 16px 18px;
  border: 1px solid color-mix(in srgb, var(--pa-primary) 28%, var(--pa-border));
  border-radius: 9px;
  background: var(--pa-primary-soft);
  font-size: 13px;
  line-height: 1.65;
}

.guide-note strong {
  flex: 0 0 auto;
  color: var(--pa-primary);
}

.question-examples {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin: 0 0 20px 54px;
}

.question-examples div {
  padding: 14px 16px;
  border: 1px solid var(--pa-border);
  border-radius: 9px;
  background: var(--pa-surface);
}

.question-examples span {
  color: var(--pa-primary);
  font-size: 12px;
  font-weight: 650;
}

.question-examples p {
  margin: 6px 0 0;
  color: var(--pa-text);
  font-size: 13px;
  line-height: 1.55;
}

.mode-table {
  margin: 0 0 20px 54px;
  overflow: hidden;
  border: 1px solid var(--pa-border);
  border-radius: 9px;
  background: var(--pa-surface);
}

.mode-row {
  display: grid;
  grid-template-columns: 110px 1fr 1fr;
  gap: 16px;
  padding: 13px 16px;
  border-bottom: 1px solid var(--pa-border);
  font-size: 13px;
  line-height: 1.55;
}

.mode-row:last-child {
  border-bottom: 0;
}

.mode-head {
  background: var(--pa-surface-soft);
  color: var(--pa-muted);
  font-weight: 650;
}

.mode-row strong {
  color: var(--pa-primary);
}

details {
  margin-left: 54px;
  border-bottom: 1px solid var(--pa-border);
}

summary {
  padding: 15px 0;
  color: var(--pa-ink);
  cursor: pointer;
  font-weight: 600;
}

details p {
  margin: 0;
  padding: 0 0 17px;
  color: var(--pa-muted);
  font-size: 14px;
  line-height: 1.75;
}

.guide-finish {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  margin: 38px 52px 46px;
  padding: 28px;
  border-radius: 12px;
  background: var(--pa-ink);
  color: #fff;
}

.guide-finish h2 {
  margin: 0 0 7px;
  font-size: 22px;
}

.guide-finish p {
  margin: 0;
  color: rgb(255 255 255 / 0.72);
  font-size: 14px;
}

@media (max-width: 820px) {
  .guide-layout { grid-template-columns: 1fr; }
  .guide-nav {
    position: static;
    flex-direction: row;
    flex-wrap: wrap;
    min-height: 0;
    padding: 20px;
  }
  .guide-nav strong { width: 100%; }
}

@media (max-width: 620px) {
  .guide-shell { width: calc(100% - 28px); padding: 42px 0 64px; }
  .guide-intro { padding: 34px 20px 32px; }
  .guide-intro h1 { font-size: 34px; }
  .section-heading { gap: 10px; }
  .section-heading > span { min-width: 30px; }
  .section-heading h2 { font-size: 22px; }
  .guide-content ol,
  .guide-content ul { padding-left: 40px; }
  .guide-note,
  .question-examples,
  .mode-table,
  details { margin-left: 40px; }
  .question-examples { grid-template-columns: 1fr; }
  .mode-row { grid-template-columns: 1fr; gap: 4px; }
  .mode-head { display: none; }
  .guide-finish { align-items: flex-start; flex-direction: column; }
  .guide-content section { padding: 34px 20px 38px; }
  .guide-finish { margin: 26px 20px 32px; }
}
</style>

<template>
  <div class="guide-page">
    <ProductHeader context="使用指南">
      <template #actions>
        <a-button type="primary" @click="$router.push('/projects')">进入研究项目</a-button>
      </template>
    </ProductHeader>

    <main class="guide-shell">
      <h1 class="pa-sr-only">PaperAI 使用指南</h1>
      <div class="guide-layout">
        <nav class="guide-nav" aria-label="指南目录">
          <strong>使用指南</strong>
          <a
            v-for="item in navigation"
            :key="item.id"
            :href="`#${item.id}`"
            :class="{ 'is-active': activeSection === item.id }"
            :aria-current="activeSection === item.id ? 'location' : undefined"
          >{{ item.label }}</a>
        </nav>

        <article class="guide-content">
          <section id="overview">
            <header class="section-heading">
              <h2>项目概览</h2>
              <p>适合管理多篇论文、持续检索或论文写作。</p>
            </header>
            <ol>
              <li>进入“研究项目”，创建项目并填写标题与研究主题。</li>
              <li>补充研究问题、目标、关键词、领域或方法方向。</li>
              <li>从概览进入“文献发现”“项目论文”或“写作”。</li>
            </ol>
            <p class="guide-note"><strong>注意：</strong>普通对话不会自动成为长期项目记忆。项目资料、论文内容、证据和写作上下文会分别管理。</p>
          </section>

          <section id="discover">
            <header class="section-heading">
              <h2>文献发现</h2>
              <p>把研究需求整理成可编辑的检索条件，再从真实学术来源获取结果。</p>
            </header>
            <ol>
              <li>描述研究主题、问题和希望包含或排除的方向。</li>
              <li>检查检索意图，并编辑年份、语言、领域和出版类型。</li>
              <li>开始检索，查看论文标题、作者、摘要、来源和推荐理由。</li>
              <li>根据用途选择收藏、下载或导入。</li>
            </ol>
            <dl class="term-list">
              <div><dt>收藏</dt><dd>只保存元数据和链接，不能作为写作证据。</dd></div>
              <div><dt>下载</dt><dd>仅在有安全、可用的 PDF 来源时提供。</dd></div>
              <div><dt>导入</dt><dd>获取全文并进入解析流程，完成后成为项目论文。</dd></div>
            </dl>
            <p class="section-footnote">结果数量取决于真实检索结果，系统不会为凑数量生成论文。</p>
          </section>

          <section id="papers">
            <header class="section-heading">
              <h2>项目论文</h2>
              <p>管理已经正式导入项目的论文，并查看解析和索引状态。</p>
            </header>
            <ul>
              <li><strong>处理中：</strong>正文、目录或索引仍在生成。</li>
              <li><strong>可阅读：</strong>可以进入阅读器浏览 PDF 和结构化目录。</li>
              <li><strong>可检索：</strong>可以参与证据检索和写作。</li>
              <li><strong>失败：</strong>检查 PDF 是否可正常打开，再重新导入或上传。</li>
            </ul>
            <p class="guide-note"><strong>说明：</strong>从项目中打开论文时，会复用独立阅读器的目录、问答、引用定位和阅读位置。</p>
          </section>

          <section id="writing">
            <header class="section-heading">
              <h2>写作</h2>
              <p>在大纲、编辑器和写作助手之间工作，使用已导入论文中的证据。</p>
            </header>
            <h3>生成与改写</h3>
            <ul>
              <li><strong>选中文本：</strong>输入改写要求，系统返回建议稿。你需要明确选择“替换”或“复制”。</li>
              <li><strong>未选中文本：</strong>针对当前章节一次生成一个段落。</li>
            </ul>
            <h3>采用建议稿之前</h3>
            <ul>
              <li>查看建议稿使用了哪些项目论文和证据片段。</li>
              <li>区分“已验证”“较弱”和“不支持”的引用状态。</li>
              <li>文档变化后，过期建议可能无法直接替换，需要重新生成或手动复制。</li>
              <li>生成失败不会影响手动编辑、保存、版本记录和导出。</li>
            </ul>
          </section>

          <section id="reader">
            <header class="section-heading">
              <h2>PDF 精读</h2>
              <p>单独阅读一篇论文时，从本地论文库上传 PDF。</p>
            </header>
            <ol>
              <li>等待正文、目录和图表解析完成。</li>
              <li>使用多级目录跳转章节，系统会保存最近阅读位置。</li>
              <li>围绕方法、实验、比较对象或结论提问，复杂问题可以启用深度思考。</li>
              <li>点击引用，跳转到对应页码和 bbox 版面区域核对原文。</li>
            </ol>
            <div class="question-examples">
              <p>“论文的核心方法包含哪些模块，各模块分别解决什么问题？”</p>
              <p>“作者用哪些实验支持主要结论？请按实验分别说明证据。”</p>
            </div>
            <p class="section-footnote">扫描件、复杂双栏、跨行表格或异常字体可能降低目录与框选精度。只有页码而没有框选时，请在对应页面人工核对。</p>
          </section>

          <section id="evidence">
            <header class="section-heading">
              <h2>证据、引用与任务状态</h2>
              <p>这些信息帮助你判断结果来自哪里、是否经过验证，以及任务进行到哪一步。</p>
            </header>
            <dl class="definition-list">
              <div><dt>Evidence（证据）</dt><dd>来自已导入论文的可追溯原文片段，包含论文身份和原文位置。</dd></div>
              <div><dt>Citation（引用）</dt><dd>把回答或文稿映射回论文、证据和页码，重要结论应回到原文核对。</dd></div>
              <div><dt>任务中心</dt><dd>展示搜索论文、查找证据和验证引用等阶段，以及可用的暂停、继续或取消操作。</dd></div>
              <div><dt>质量检查</dt><dd>任务完成前检查证据、引用和输出完整性，但不替代人工学术审阅。</dd></div>
            </dl>
          </section>

          <section id="troubleshooting">
            <header class="section-heading"><h2>常见问题</h2></header>
            <details><summary>为什么收藏的论文不能用于写作？</summary><p>收藏只保存检索元数据。论文必须正式导入项目，并完成足够的解析与索引后，才能提供可核对的全文证据。</p></details>
            <details><summary>为什么返回的论文少于期望数量？</summary><p>检索只返回符合条件的真实论文。可以放宽年份、语言或出版类型，再重新检索。</p></details>
            <details><summary>为什么建议稿不能替换选中文本？</summary><p>文档版本或原选区可能已经变化。重新选中文本并生成，或复制建议稿后手动调整。</p></details>
            <details><summary>引用定位略有偏差怎么办？</summary><p>框选依赖 PDF 版面坐标。遇到双栏、跨行、表格或字体编码异常时，请结合引用片段在对应页面人工核对。</p></details>
          </section>
        </article>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import ProductHeader from '@/components/ProductHeader.vue'

const navigation = [
  { id: 'overview', label: '项目概览' },
  { id: 'discover', label: '文献发现' },
  { id: 'papers', label: '项目论文' },
  { id: 'writing', label: '写作' },
  { id: 'reader', label: 'PDF 精读' },
  { id: 'evidence', label: '证据与任务状态' },
  { id: 'troubleshooting', label: '常见问题' },
]

const activeSection = ref('overview')
let sectionObserver: IntersectionObserver | undefined

onMounted(() => {
  const hashSection = window.location.hash.slice(1)
  if (navigation.some(item => item.id === hashSection)) activeSection.value = hashSection
  if (!('IntersectionObserver' in window)) return

  sectionObserver = new IntersectionObserver((entries) => {
    const visible = entries
      .filter(entry => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
    if (visible?.target.id) activeSection.value = visible.target.id
  }, { rootMargin: '-15% 0px -65% 0px', threshold: [0, 0.2, 0.5] })

  navigation.forEach(({ id }) => {
    const section = document.getElementById(id)
    if (section) sectionObserver?.observe(section)
  })
})

onUnmounted(() => sectionObserver?.disconnect())
</script>

<style scoped>
.guide-page {
  min-height: 100vh;
  background: var(--pa-bg);
  color: var(--pa-text);
}

.guide-shell {
  width: min(100% - 48px, 1280px);
  margin: 0 auto;
  padding: 34px 0 88px;
}

.guide-layout {
  display: grid;
  grid-template-columns: 210px minmax(0, 1fr);
  gap: 24px;
  align-items: start;
}

.guide-nav {
  position: sticky;
  top: 20px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 24px 20px;
  border: 1px solid var(--pa-border);
  border-radius: 10px;
  background: var(--pa-surface);
  box-shadow: var(--pa-shadow-sm);
}

.guide-nav strong {
  margin: 0 10px 10px;
  color: var(--pa-ink);
  font-size: 13px;
}

.guide-nav a {
  min-height: 36px;
  padding: 8px 10px;
  border-radius: 7px;
  color: var(--pa-muted);
  font-size: 13px;
  text-decoration: none;
}

.guide-nav a:hover,
.guide-nav a.is-active {
  background: var(--pa-primary-soft);
  color: var(--pa-primary);
}

.guide-nav a.is-active {
  font-weight: 650;
}

.guide-nav a:focus-visible,
summary:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 2px;
}

.guide-content {
  overflow: hidden;
  border: 1px solid var(--pa-border);
  border-radius: 12px;
  background: var(--pa-surface);
  box-shadow: var(--pa-shadow-md);
}

.guide-content section {
  max-width: 78ch;
  padding: 42px 52px 46px;
  border-bottom: 1px solid var(--pa-border);
  scroll-margin-top: 24px;
}

.guide-content section:last-child {
  border-bottom: 0;
}

.section-heading {
  margin-bottom: 24px;
}

.section-heading h2 {
  margin: 0 0 8px;
  color: var(--pa-ink);
  font-size: 25px;
  line-height: 1.3;
  letter-spacing: -0.02em;
  text-wrap: balance;
}

.section-heading p,
.section-footnote {
  margin: 0;
  color: var(--pa-muted);
  font-size: 14px;
  line-height: 1.75;
}

.guide-content h3 {
  margin: 26px 0 10px;
  color: var(--pa-ink);
  font-size: 15px;
}

.guide-content ol,
.guide-content ul {
  margin: 0;
  padding-left: 22px;
}

.guide-content li {
  margin-bottom: 10px;
  padding-left: 4px;
  line-height: 1.75;
}

.guide-note {
  margin: 22px 0 0;
  padding: 14px 16px;
  border: 1px solid color-mix(in srgb, var(--pa-primary) 22%, var(--pa-border));
  border-radius: 8px;
  background: var(--pa-primary-soft);
  font-size: 13px;
  line-height: 1.7;
}

.guide-note strong {
  color: var(--pa-primary);
}

.term-list,
.definition-list {
  margin: 22px 0 0;
  border-top: 1px solid var(--pa-border);
}

.term-list div,
.definition-list div {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 18px;
  padding: 13px 0;
  border-bottom: 1px solid var(--pa-border);
  font-size: 13px;
  line-height: 1.7;
}

.term-list dt,
.definition-list dt {
  color: var(--pa-ink);
  font-weight: 650;
}

.term-list dd,
.definition-list dd {
  margin: 0;
  color: var(--pa-muted);
}

.section-footnote {
  margin-top: 18px;
  font-size: 13px;
}

.question-examples {
  margin-top: 20px;
  padding: 4px 0 4px 16px;
  border-left: 1px solid var(--pa-border-strong);
}

.question-examples p {
  margin: 8px 0;
  color: var(--pa-muted);
  font-size: 13px;
  line-height: 1.65;
}

details {
  border-bottom: 1px solid var(--pa-border);
}

details:last-child {
  border-bottom: 0;
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

@media (max-width: 820px) {
  .guide-layout {
    grid-template-columns: 1fr;
  }

  .guide-nav {
    position: static;
    flex-direction: row;
    flex-wrap: wrap;
    padding: 18px;
  }

  .guide-nav strong {
    width: 100%;
  }
}

@media (max-width: 620px) {
  .guide-shell {
    width: calc(100% - 28px);
    padding: 20px 0 60px;
  }

  .guide-nav a {
    min-height: 44px;
  }

  .guide-content section {
    padding: 34px 20px 38px;
  }

  .section-heading h2 {
    font-size: 22px;
  }

  .term-list div,
  .definition-list div {
    grid-template-columns: 1fr;
    gap: 3px;
  }
}

@media (pointer: coarse) {
  .guide-nav a {
    min-height: 44px;
  }
}
</style>

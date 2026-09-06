<template>
  <div class="guide-page">
    <ProductHeader context="使用指南">
      <template #actions>
        <a-button type="primary" @click="openProjects">进入研究项目</a-button>
      </template>
    </ProductHeader>

    <div class="guide-workspace">
      <aside class="guide-sidebar" aria-label="使用指南导航">
        <div class="guide-sidebar__head">
          <strong>使用指南</strong>
          <p>按任务查阅操作步骤</p>
        </div>

        <nav class="guide-nav" aria-label="指南模块">
          <section v-for="group in navigationGroups" :key="group.label" class="guide-nav-group">
            <h2>{{ group.label }}</h2>
            <div class="guide-nav-items">
              <RouterLink
                v-for="page in group.items"
                :key="page.id"
                class="guide-nav__link"
                :class="{ 'is-active': currentPage.id === page.id }"
                :to="{ name: 'GuideSection', params: { section: page.id } }"
                :aria-current="currentPage.id === page.id ? 'page' : undefined"
              >{{ page.label }}</RouterLink>
            </div>
          </section>
        </nav>
      </aside>

      <main class="guide-main">
        <article class="guide-document" :aria-labelledby="`guide-title-${currentPage.id}`">
          <header class="guide-document__header">
            <h1 :id="`guide-title-${currentPage.id}`">{{ currentPage.title }}</h1>
            <p>{{ currentPage.intro }}</p>
          </header>

          <section class="guide-section">
            <h2>从哪里开始</h2>
            <p>{{ currentPage.start }}</p>
          </section>

          <section class="guide-section">
            <h2>操作步骤</h2>
            <ol class="guide-steps">
              <li v-for="(step, index) in currentPage.steps" :key="step.title">
                <span class="guide-step-number" aria-hidden="true">{{ index + 1 }}</span>
                <div>
                  <h3>{{ step.title }}</h3>
                  <p>{{ step.body }}</p>
                </div>
              </li>
            </ol>
          </section>

          <section class="guide-section">
            <h2>完成后你会看到</h2>
            <ul class="guide-outcomes">
              <li v-for="outcome in currentPage.outcomes" :key="outcome">{{ outcome }}</li>
            </ul>
          </section>

          <section v-if="currentPage.terms" class="guide-section">
            <h2>{{ currentPage.termsTitle || '关键动作怎么区分' }}</h2>
            <dl class="guide-terms">
              <div v-for="term in currentPage.terms" :key="term.name">
                <dt>{{ term.name }}</dt>
                <dd>{{ term.description }}</dd>
              </div>
            </dl>
          </section>

          <section v-if="currentPage.questions" class="guide-section guide-faq">
            <h2>遇到问题</h2>
            <details v-for="question in currentPage.questions" :key="question.title">
              <summary>{{ question.title }}</summary>
              <p>{{ question.answer }}</p>
            </details>
          </section>

          <aside v-if="currentPage.note" class="guide-note" role="note">
            <strong>{{ currentPage.note.title }}</strong>
            <p>{{ currentPage.note.body }}</p>
          </aside>

          <nav class="guide-page-nav" aria-label="指南页面切换">
            <RouterLink
              v-if="previousPage"
              class="guide-page-nav__link guide-page-nav__link--previous"
              :to="{ name: 'GuideSection', params: { section: previousPage.id } }"
            >
              <span>上一页</span>
              <strong>{{ previousPage.label }}</strong>
            </RouterLink>
            <span v-else></span>
            <RouterLink
              v-if="nextPage"
              class="guide-page-nav__link guide-page-nav__link--next"
              :to="{ name: 'GuideSection', params: { section: nextPage.id } }"
            >
              <span>下一页</span>
              <strong>{{ nextPage.label }}</strong>
            </RouterLink>
          </nav>
        </article>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ProductHeader from '@/components/ProductHeader.vue'

type GuideStep = {
  title: string
  body: string
}

type GuideTerm = {
  name: string
  description: string
}

type GuideQuestion = {
  title: string
  answer: string
}

type GuidePage = {
  id: string
  label: string
  title: string
  intro: string
  start: string
  steps: GuideStep[]
  outcomes: string[]
  termsTitle?: string
  terms?: GuideTerm[]
  questions?: GuideQuestion[]
  note?: { title: string; body: string }
}

const guidePages: GuidePage[] = [
  {
    id: 'overview',
    label: '项目概览',
    title: '把研究问题变成一个项目',
    intro: '项目是管理多篇论文、持续检索和证据写作的工作空间。先定义范围，再进入后续阶段。',
    start: '从首页点击“进入研究项目”，或直接打开研究项目列表。一个项目至少需要标题和研究主题，创建后会进入项目概览。',
    steps: [
      { title: '创建项目', body: '点击“创建项目”，填写项目标题和研究主题。标题用于识别项目，主题应说明你准备研究的对象或问题。' },
      { title: '补充研究范围', body: '按需要填写领域、主题、研究问题、研究目标、关键词、方法方向和备注，让后续检索和写作知道边界。' },
      { title: '检查项目概览', body: '保存后确认研究范围、项目论文数量和当前入口都显示正常；概览页是回到 Discover、Papers、Writing 的起点。' },
      { title: '选择下一步', body: '还没有论文时进入“文献发现”；已有正式导入的论文时查看“项目论文”；准备组织文稿时进入“写作”。' },
    ],
    outcomes: [
      '概览页显示项目主题、研究范围和进入三个工作阶段的入口。',
      '项目资料只属于当前项目及其所有者，不会因为普通对话自动变成长期记忆。',
      '后续的论文、证据和写作上下文会按各自用途分别管理。',
    ],
    note: {
      title: '什么时候不需要创建项目？',
      body: '如果只是阅读一篇本地 PDF，直接使用“独立阅读”即可；项目适合需要多篇论文、持续检索或证据写作的任务。',
    },
  },
  {
    id: 'discover',
    label: '文献发现',
    title: '在项目中发现真实文献',
    intro: '把自然语言研究需求整理成可编辑的检索条件，再从真实学术来源获取结构化论文结果。',
    start: '在项目概览点击“文献发现”。首次进入时先说明研究主题、问题、希望包含的方向和需要排除的方向。',
    steps: [
      { title: '描述检索需求', body: '用完整句子说明研究对象、核心问题、时间范围或方法偏好。越具体，后面的检索意图越容易检查。' },
      { title: '检查并编辑检索条件', body: '确认系统整理出的检索意图，并按需要修改年份、语言、领域和出版类型等筛选条件。' },
      { title: '开始检索并阅读结果', body: '启动检索后查看论文标题、作者、年份、来源、摘要和推荐理由。页面会显示明确检索阶段，不需要阅读内部执行日志。' },
      { title: '按用途处理论文', body: '对结果分别选择收藏、下载、导入或查看详情。先收藏不代表论文已经进入项目，也不会自动成为写作证据。' },
    ],
    outcomes: [
      '结果以结构化论文记录呈现，可以直接检查元数据和完整摘要。',
      '结果数量取决于真实检索结果，少于期望数量时不会用虚构论文补齐。',
      '导入成功后，论文才会进入项目论文列表并开始解析、索引流程。',
    ],
    termsTitle: '收藏、下载和导入的区别',
    terms: [
      { name: '收藏', description: '只保存论文元数据和来源链接，方便稍后处理，不能作为写作证据。' },
      { name: '下载', description: '仅在存在安全、可用的 PDF 来源时提供可用文件。' },
      { name: '导入', description: '获取获准的全文并进入 PaperAI 的解析和索引流程，完成后成为项目论文。' },
      { name: '详情', description: '查看规范化元数据、摘要和可用来源链接，不会改变论文所属状态。' },
    ],
    note: {
      title: '结果太少怎么办？',
      body: '先放宽年份、语言、领域或出版类型，再重新检索。系统只返回符合条件的真实结果，不会为了凑数量生成论文。',
    },
  },
  {
    id: 'papers',
    label: '项目论文',
    title: '确认项目论文已读、可检索',
    intro: '项目论文页管理已经正式导入或明确附加到项目的论文，并展示解析、阅读和检索状态。',
    start: '从项目概览进入“项目论文”。Discover 中仅收藏或仅查看过的记录不会出现在这里，必须先完成正式导入。',
    steps: [
      { title: '查看论文状态', body: '打开论文列表，先看处理状态和最后更新时间。正在处理的论文仍可能在生成正文、目录、图表或索引。' },
      { title: '等待解析完成', body: '等论文进入可阅读或可检索状态后再开始证据写作；处理中时可以先阅读其他已经准备好的论文。' },
      { title: '开始阅读项目论文', body: '点击论文标题或“开始阅读 / 继续阅读 / 阅读”，进入同一个 PDF 阅读页；项目身份和项目专属的证据操作会继续保留。' },
      { title: '处理失败论文', body: '如果状态失败，先确认 PDF 可以正常打开且文件完整，再在当前项目论文页重新上传，或回到文献发现重新导入；不要把失败记录当作可用证据。' },
    ],
    outcomes: [
      '列表能区分处理中、可阅读、可检索和失败等处理结果。',
      '可阅读论文可以使用目录、问答和原文定位功能。',
      '可检索论文才会被证据检索和写作工作流选为候选来源。',
    ],
    note: {
      title: '写作前的最低条件',
      body: '论文必须属于当前项目、已经正式导入，并完成足够的解析和索引。Discover-only 或收藏-only 记录不能用于生成可验证引用。',
    },
  },
  {
    id: 'writing',
    label: '写作',
    title: '用证据完成一段写作',
    intro: '在大纲、编辑器和写作助手之间组织文稿，只使用当前项目中已导入并可检索论文的证据。',
    start: '从项目概览进入“写作”，先打开或创建写作文档。建议在已有研究范围和可检索项目论文后，再请求证据支持的生成。',
    steps: [
      { title: '准备写作上下文', body: '在大纲中定位章节，在编辑器中确认当前文档版本；需要引用时，先确认项目论文页已有可检索来源。' },
      { title: '选择生成方式', body: '未选中文本时，针对当前章节请求一次一个段落；选中文本时，附上明确的改写、压缩、扩展或学术化指令。' },
      { title: '检查建议稿和证据', body: '阅读生成文本、证据片段和结构化引用映射，分别确认论文身份、原文位置及引用是否已验证。' },
      { title: '明确采用方式', body: '选中文本的建议稿只能由你明确选择“替换”或“复制”。不满意时可以放弃建议，手动编辑、保存版本或重新生成。' },
      { title: '保存并导出', body: '确认内容后保存文档和修订记录；需要交付时使用现有导出入口，不要把未验证的引用当作最终结论。' },
    ],
    outcomes: [
      '编辑器保留原文，建议稿以可审阅的提案形式出现，不会静默覆盖内容。',
      '证据来自当前项目的正式导入论文，并显示引用验证状态。',
      '生成失败或证据不足时，手动编辑、保存版本和导出仍然可用。',
    ],
    termsTitle: '生成模式和引用状态',
    terms: [
      { name: '选中文本', description: '根据选区和指令返回改写建议，必须明确选择替换或复制。' },
      { name: '未选中文本', description: '围绕当前章节一次生成一个段落，避免一次性覆盖整篇文档。' },
      { name: '已验证', description: '引用已经通过证据和来源位置核对，可以继续人工检查语义是否准确。' },
      { name: '未支持/较弱', description: '证据不足或定位不充分，不应当以已验证结论展示或直接交付。' },
    ],
    note: {
      title: '写作边界',
      body: 'V1 写作不会为了补充引用而自动搜索网页或新论文。先回到文献发现并导入合适来源，再返回写作。',
    },
  },
  {
    id: 'reader',
    label: 'PDF 精读',
    title: '独立阅读一篇 PDF',
    intro: '单篇论文不需要创建项目。上传到本地论文库后，可以使用结构化目录、问答和原文定位完成精读。',
    start: '从首页进入“独立阅读”，选择一个 PDF 上传。上传完成后，先等待正文、目录和索引处理。',
    steps: [
      { title: '上传并等待处理', body: '选择完整、可打开的 PDF，等待解析状态完成；扫描件、复杂双栏和异常字体可能需要更长时间或降低解析精度。' },
      { title: '用目录定位章节', body: '打开多级目录跳转到引言、方法、实验或结论，并利用自动保存的阅读位置继续上次进度。' },
      { title: '围绕原文提问', body: '优先询问方法模块、实验对照、数据来源或结论依据。复杂问题可以启用深度思考，但仍需回到原文核对。' },
      { title: '核对引用位置', body: '点击回答中的引用，跳转到对应页码和 bbox 版面区域；如果只提供页码或框选偏差，请在该页人工查找原文。' },
    ],
    outcomes: [
      '独立阅读保存当前论文和最近阅读位置，不依赖项目上下文。',
      '回答可以回到章节、页码和版面区域，便于核对原文。',
      '解析能力受 PDF 版面和字体质量影响，异常文件会保留可见的限制。',
    ],
    note: {
      title: '定位不准确时',
      body: '双栏、跨行表格、扫描件或字体编码异常可能影响 bbox 框选。以引用片段和页码为准，在对应页面人工核对。',
    },
  },
  {
    id: 'evidence',
    label: '证据与任务状态',
    title: '读懂证据、引用和任务进度',
    intro: '证据、引用验证和任务阶段帮助你判断内容来自哪里、是否可以信任，以及长任务进行到哪一步。',
    start: '在写作建议稿、证据区域或顶部任务中心查看这些信息。先看来源和状态，再决定是否采用内容。',
    steps: [
      { title: '从引用回到来源', body: '点击文稿或回答里的结构化引用，检查对应项目论文、证据片段、页码和原文位置是否与当前论断一致。' },
      { title: '区分验证状态', body: '把已验证、较弱和不支持视为不同的审阅信号；未验证的内容需要补充来源或改写，不能只因为有编号就当成事实。' },
      { title: '查看任务阶段', body: '在任务中心关注明确的用户阶段，例如搜索论文、筛选结果、查找支持证据和验证引用；需要时使用暂停、继续或取消。' },
      { title: '在完成前做质量检查', body: '确认必需证据存在、引用映射完整、来源属于当前项目且任务没有失败，再进行人工学术审阅和交付。' },
    ],
    outcomes: [
      '每个关键结论都能追溯到论文和原文位置，或明确显示证据不足。',
      '长任务有可理解的状态和恢复入口，不需要查看原始执行日志。',
      '质量检查减少遗漏，但不替代你对研究结论、语义和格式的最终判断。',
    ],
    termsTitle: '四类信息分别代表什么',
    terms: [
      { name: 'Evidence（证据）', description: '来自已导入论文的可追溯原文片段，包含论文身份和原文位置。' },
      { name: 'Citation（引用）', description: '把回答或文稿映射回论文与证据；重要结论应打开来源核对。' },
      { name: '任务状态', description: '展示当前阶段、等待原因和可用操作，例如继续、暂停或取消。' },
      { name: '质量检查', description: '在任务完成前检查证据、引用和输出完整性，不等同于人工同行评审。' },
    ],
  },
  {
    id: 'troubleshooting',
    label: '常见问题',
    title: '遇到问题时怎么处理',
    intro: '先确认当前模块和任务状态，再用下面的恢复路径处理论文、解析、引用和写作问题。',
    start: '如果页面正在执行任务，先打开任务中心确认是否仍在处理、已暂停或已失败；不要在状态未知时重复提交相同操作。',
    steps: [
      { title: '收藏的论文不能写作', body: '回到文献发现，对论文执行正式导入；然后在项目论文页等待解析和索引达到可检索状态。' },
      { title: '检索结果少于预期', body: '检查年份、语言、领域和出版类型过滤条件，适度放宽后重新检索；少于目标数量可能是有效结果的真实数量。' },
      { title: '项目论文处理失败', body: '确认原 PDF 能打开、文件没有损坏且来源获准，再在当前项目论文页重新上传，或回到文献发现重新导入；失败记录不能用作证据。' },
      { title: '建议稿无法替换选区', body: '文档版本或原选区可能已经变化。重新选中文本后生成，或复制建议稿并手动调整，避免覆盖错误内容。' },
      { title: '引用定位偏差', body: '结合引用片段和页码在原 PDF 中人工核对。双栏、表格、扫描件和异常字体可能降低 bbox 精度。' },
    ],
    outcomes: [
      '每类问题都有对应的下一步，不需要通过重复点击来猜测状态。',
      '重新导入、放宽过滤条件或重新生成都不会绕过项目归属和引用验证。',
      '无法自动验证的内容会保持未验证，直到你补充来源并完成核对。',
    ],
    questions: [
      { title: '为什么普通对话没有记住我的项目？', answer: '普通对话历史不会自动变成长期项目记忆。请把研究范围填写到项目概览，把论文正式导入项目，并在写作中使用对应文档。' },
      { title: '为什么任务看起来停住了？', answer: '先查看任务中心的当前阶段和错误提示。等待中的任务可以继续，失败任务需要按提示修复输入或重新执行；不要把黑盒日志当作恢复依据。' },
      { title: '为什么有引用编号却不能算已验证？', answer: '引用编号只是结构化映射的一部分。只有当证据、论文归属和原文位置都能核对时，才应视为已验证。' },
    ],
  },
]

const navigationGroups = [
  { label: '研究项目', items: guidePages.slice(0, 4) },
  { label: '单篇阅读', items: guidePages.slice(4, 5) },
  { label: '核对与帮助', items: guidePages.slice(5) },
]

const route = useRoute()
const router = useRouter()

const requestedSection = computed(() => {
  const section = route.params.section
  return typeof section === 'string' ? section : 'overview'
})

const currentPage = computed(() => (
  guidePages.find(page => page.id === requestedSection.value) || guidePages[0]
))

const currentIndex = computed(() => guidePages.findIndex(page => page.id === currentPage.value.id))
const previousPage = computed(() => currentIndex.value > 0 ? guidePages[currentIndex.value - 1] : undefined)
const nextPage = computed(() => currentIndex.value < guidePages.length - 1 ? guidePages[currentIndex.value + 1] : undefined)

function openProjects() {
  router.push('/projects')
}
</script>

<style scoped>
.guide-page {
  --guide-header-height: var(--pa-header-height);
  --guide-sidebar-height: 0px;
  --guide-sidebar-width: 240px;
  min-height: 100vh;
  background: var(--pa-bg);
  color: var(--pa-text);
}

.guide-page :deep(.product-header) {
  position: fixed;
  z-index: 20;
  top: 0;
  right: 0;
  left: 0;
}

.guide-workspace {
  min-height: 100vh;
  padding-top: var(--guide-header-height);
}

.guide-sidebar {
  position: fixed;
  z-index: 10;
  top: var(--guide-header-height);
  bottom: 0;
  left: 0;
  width: var(--guide-sidebar-width);
  overflow-y: auto;
  padding: 32px 16px;
  border-right: 1px solid var(--pa-border);
  background: var(--pa-surface);
}

.guide-sidebar__head {
  padding: 0 12px 26px;
}

.guide-sidebar__head strong {
  display: block;
  color: var(--pa-ink);
  font-size: 15px;
  font-weight: 700;
}

.guide-sidebar__head p {
  margin: 7px 0 0;
  color: var(--pa-muted);
  font-size: 12px;
  line-height: 1.5;
}

.guide-nav {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.guide-nav-group h2 {
  margin: 0 4px 9px;
  padding: 0 8px 9px;
  border-bottom: 1px solid var(--pa-border);
  color: var(--pa-ink);
  font-size: 14px;
  font-weight: 720;
  letter-spacing: -0.01em;
}

.guide-nav-items {
  display: flex;
  flex-direction: column;
  gap: 3px;
  padding-left: 8px;
}

.guide-nav__link {
  display: flex;
  min-height: 40px;
  align-items: center;
  padding: 8px 12px;
  border-radius: 8px;
  color: var(--pa-muted);
  font-size: 13px;
  line-height: 1.35;
  text-decoration: none;
  transition: color 180ms ease-out, background-color 180ms ease-out;
}

.guide-nav__link:hover,
.guide-nav__link.is-active {
  background: var(--pa-primary-soft);
  color: var(--pa-primary);
}

.guide-nav__link.is-active {
  font-weight: 650;
}

.guide-nav__link:focus-visible,
.guide-page-nav__link:focus-visible,
summary:focus-visible {
  outline: 2px solid var(--pa-primary);
  outline-offset: 3px;
}

.guide-main {
  min-width: 0;
  margin-left: var(--guide-sidebar-width);
  padding: 0 3px 72px;
  background: var(--pa-bg);
}

.guide-document {
  width: 100%;
  margin: 0;
  overflow: hidden;
  border: 1px solid var(--pa-border);
  border-top: 0;
  border-radius: 0;
  background: var(--pa-surface);
  box-shadow: none;
}

.guide-document__header {
  padding: 48px 56px 38px;
  border-bottom: 1px solid var(--pa-border);
}

.guide-document__header h1 {
  max-width: 18ch;
  margin: 0;
  color: var(--pa-ink);
  font-size: clamp(28px, 3vw, 38px);
  font-weight: 720;
  letter-spacing: -0.035em;
  line-height: 1.2;
  text-wrap: balance;
}

.guide-document__header p {
  max-width: 68ch;
  margin: 16px 0 0;
  color: var(--pa-muted);
  font-size: 15px;
  line-height: 1.8;
}

.guide-section {
  padding: 32px 56px 36px;
  border-bottom: 1px solid var(--pa-border);
}

.guide-section h2 {
  margin: 0 0 16px;
  color: var(--pa-ink);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: -0.015em;
  line-height: 1.4;
}

.guide-section > p {
  max-width: 68ch;
  margin: 0;
  color: var(--pa-text);
  font-size: 14px;
  line-height: 1.85;
}

.guide-steps {
  display: flex;
  flex-direction: column;
  gap: 22px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.guide-steps li {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.guide-step-number {
  display: inline-flex;
  width: 28px;
  height: 28px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--pa-primary-soft);
  color: var(--pa-primary);
  font-size: 12px;
  font-weight: 700;
}

.guide-steps h3 {
  margin: 2px 0 5px;
  color: var(--pa-ink);
  font-size: 15px;
  font-weight: 680;
  line-height: 1.45;
}

.guide-steps p {
  margin: 0;
  color: var(--pa-text);
  font-size: 14px;
  line-height: 1.8;
}

.guide-outcomes {
  display: flex;
  flex-direction: column;
  gap: 11px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.guide-outcomes li {
  position: relative;
  padding-left: 18px;
  color: var(--pa-text);
  font-size: 14px;
  line-height: 1.75;
}

.guide-outcomes li::before {
  position: absolute;
  top: 0.75em;
  left: 2px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--pa-primary);
  content: '';
}

.guide-terms {
  margin: 0;
  border-top: 1px solid var(--pa-border);
}

.guide-terms > div {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 20px;
  padding: 14px 0;
  border-bottom: 1px solid var(--pa-border);
}

.guide-terms dt {
  color: var(--pa-ink);
  font-size: 13px;
  font-weight: 680;
  line-height: 1.7;
}

.guide-terms dd {
  margin: 0;
  color: var(--pa-muted);
  font-size: 13px;
  line-height: 1.7;
}

.guide-faq details {
  border-bottom: 1px solid var(--pa-border);
}

.guide-faq details:last-child {
  border-bottom: 0;
}

.guide-faq summary {
  padding: 14px 0;
  color: var(--pa-ink);
  cursor: pointer;
  font-size: 14px;
  font-weight: 650;
  line-height: 1.6;
}

.guide-faq details p {
  margin: 0;
  padding: 0 0 17px;
  color: var(--pa-muted);
  font-size: 14px;
  line-height: 1.8;
}

.guide-note {
  margin: 32px 56px 0;
  padding: 16px 18px;
  border: 1px solid color-mix(in srgb, var(--pa-primary) 22%, var(--pa-border));
  border-radius: 8px;
  background: var(--pa-primary-soft);
}

.guide-note strong {
  color: var(--pa-primary);
  font-size: 13px;
  line-height: 1.5;
}

.guide-note p {
  margin: 6px 0 0;
  color: var(--pa-text);
  font-size: 13px;
  line-height: 1.75;
}

.guide-page-nav {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  padding: 32px 56px 38px;
}

.guide-page-nav__link {
  display: flex;
  min-height: 52px;
  flex-direction: column;
  justify-content: center;
  padding: 8px 12px;
  border: 1px solid var(--pa-border);
  border-radius: 8px;
  color: var(--pa-muted);
  text-decoration: none;
  transition: color 180ms ease-out, border-color 180ms ease-out, background-color 180ms ease-out;
}

.guide-page-nav__link:hover {
  border-color: var(--pa-border-strong);
  background: var(--pa-surface-soft);
  color: var(--pa-primary);
}

.guide-page-nav__link--next {
  align-items: flex-end;
  text-align: right;
}

.guide-page-nav__link span {
  font-size: 11px;
  line-height: 1.5;
}

.guide-page-nav__link strong {
  margin-top: 2px;
  color: var(--pa-ink);
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 900px) {
  .guide-page {
    --guide-sidebar-height: 132px;
  }

  .guide-sidebar {
    position: fixed;
    z-index: 10;
    top: var(--guide-header-height);
    right: 0;
    bottom: auto;
    left: 0;
    width: 100%;
    height: var(--guide-sidebar-height);
    overflow: hidden;
    padding: 18px 16px 14px;
    border-right: 0;
    border-bottom: 1px solid var(--pa-border);
  }

  .guide-workspace {
    padding-top: calc(var(--guide-header-height) + var(--guide-sidebar-height));
  }

  .guide-sidebar__head {
    display: flex;
    align-items: baseline;
    gap: 10px;
    padding: 0 4px 12px;
  }

  .guide-sidebar__head p {
    margin: 0;
  }

  .guide-nav {
    flex-direction: row;
    gap: 18px;
    overflow-x: auto;
    padding: 0 4px 4px;
  }

  .guide-nav-group {
    flex: 0 0 auto;
  }

  .guide-nav-group h2 {
    margin: 0 0 5px;
    padding: 0 0 5px;
    border-bottom: 0;
  }

  .guide-nav-items {
    flex-direction: row;
    gap: 4px;
    padding-left: 0;
  }

  .guide-nav__link {
    min-height: 44px;
    white-space: nowrap;
  }

  .guide-main {
    margin-left: 0;
    padding-top: 0;
  }
}

@media (max-width: 760px) {
  .guide-page {
    --guide-header-height: 104px;
  }

  .guide-main {
    padding: 0 3px 56px;
  }

  .guide-document__header {
    padding: 34px 22px 28px;
  }

  .guide-document__header h1 {
    font-size: 28px;
  }

  .guide-document__header p {
    font-size: 14px;
  }

  .guide-section {
    padding: 28px 22px 30px;
  }

  .guide-terms > div {
    grid-template-columns: 1fr;
    gap: 3px;
  }

  .guide-note {
    margin: 26px 22px 0;
  }

  .guide-page-nav {
    padding: 26px 22px 30px;
  }
}

@media (pointer: coarse) {
  .guide-nav__link,
  .guide-page-nav__link {
    min-height: 44px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .guide-nav__link,
  .guide-page-nav__link {
    transition: none;
  }
}
</style>

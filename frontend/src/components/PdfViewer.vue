<template>
  <div class="pdf-viewer-wrapper">
    <!-- 工具栏 -->
    <div class="pdf-toolbar">
      <div class="page-selector">
        <button class="toolbar-btn page-nav-btn" @click="prevPage" :disabled="currentPage <= 1">
          <span>◀</span>
        </button>
        <input
          type="number"
          v-model.number="currentPage"
          @keydown.enter="goToPage"
          min="1"
          :max="numPages"
          class="page-input"
        />
        <span class="page-separator">/</span>
        <span class="page-total">{{ numPages }}</span>
        <button class="toolbar-btn page-nav-btn" @click="nextPage" :disabled="currentPage >= numPages">
          <span>▶</span>
        </button>
      </div>
      <div class="toolbar-spacer"></div>
      <button class="toolbar-btn" @click="zoomOut" :disabled="scale <= 0.5">
        <span>-</span>
      </button>
      <span class="zoom-level">{{ Math.round(scale * 100) }}%</span>
      <button class="toolbar-btn" @click="zoomIn" :disabled="scale >= 3">
        <span>+</span>
      </button>
      <button class="toolbar-btn" @click="resetZoom">
        <span>100%</span>
      </button>
      <button class="toolbar-btn" @click="fitWidth">
        <span>适应宽度</span>
      </button>
    </div>
    
    <!-- PDF 内容区域 -->
    <div ref="containerRef" class="pdf-container" @scroll="onScroll">
      <div ref="contentRef" class="pdf-content">
        <canvas
          v-for="i in numPages"
          :key="i - 1"
          :ref="el => setCanvasRef(i - 1, el as HTMLCanvasElement | null)"
          class="pdf-canvas"
        />
      </div>
    </div>
    
    <!-- 加载状态 -->
    <div v-if="loading && numPages === 0" class="pdf-loading">
      <div class="loading-spinner"></div>
      <p>加载 PDF 中...</p>
    </div>
    
    <!-- 后台加载进度 -->
    <div v-if="!loading && loadingProgress > 0 && loadingProgress < 100" class="pdf-progress">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: loadingProgress + '%' }"></div>
      </div>
      <span class="progress-text">{{ loadingProgress }}%</span>
    </div>
    
    <!-- 错误状态 -->
    <div v-if="error" class="pdf-error">
      <div class="error-icon">⚠️</div>
      <h3>PDF 加载失败</h3>
      <p>无法加载 PDF 文件</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorker from 'pdfjs-dist/build/pdf.worker.min.mjs?worker'

pdfjsLib.GlobalWorkerOptions.workerPort = new pdfWorker()

// 抑制 PDF.js 的字体警告
const originalWarn = console.warn
console.warn = function(...args: any[]) {
  // 过滤掉字体相关的警告
  const message = args[0] || ''
  if (typeof message === 'string' && message.includes('Not enough space in glyfs')) {
    return  // 忽略这个警告
  }
  originalWarn.apply(console, args)
}

const props = defineProps<{
  pdfUrl: string
}>()

const containerRef = ref<HTMLElement | null>(null)
const contentRef = ref<HTMLElement | null>(null)
const canvasRefs = ref<(HTMLCanvasElement | null)[]>([])
const loading = ref(true)
const error = ref(false)
const numPages = ref(0)
const scale = ref(1.0)
const currentPage = ref(1)

let pdfDoc: any = null
let pageHeights: number[] = []
let pageWidths: number[] = []
const renderedPages = new Set<number>()
const renderingPages = new Set<number>()
const loadingProgress = ref(0) // 加载进度 0-100

const setCanvasRef = (index: number, el: HTMLCanvasElement | null) => {
  canvasRefs.value[index] = el
}

const renderPage = async (pageIndex: number, forceRender = false) => {
  // 如果已经渲染过且不是强制渲染，则跳过
  if (!forceRender && renderedPages.has(pageIndex)) return
  if (renderingPages.has(pageIndex)) return
  
  renderingPages.add(pageIndex)
  
  try {
    const page = await pdfDoc.getPage(pageIndex + 1)
    const dpr = window.devicePixelRatio || 1
    const viewport = page.getViewport({ scale: scale.value })
    
    const canvas = canvasRefs.value[pageIndex]
    if (!canvas) {
      renderingPages.delete(pageIndex)
      return
    }
    
    const ctx = canvas.getContext('2d')
    if (!ctx) {
      renderingPages.delete(pageIndex)
      return
    }
    
    // 清空canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    
    canvas.width = viewport.width * dpr
    canvas.height = viewport.height * dpr
    canvas.style.width = `${viewport.width}px`
    canvas.style.height = `${viewport.height}px`
    
    ctx.scale(dpr, dpr)
    
    pageHeights[pageIndex] = viewport.height
    pageWidths[pageIndex] = viewport.width
    
    await page.render({
      canvasContext: ctx,
      viewport,
      canvas
    }).promise
    
    renderedPages.add(pageIndex)
  } catch (e) {
    console.error(`渲染页面 ${pageIndex + 1} 失败:`, e)
  } finally {
    renderingPages.delete(pageIndex)
  }
}

const renderVisiblePages = () => {
  if (!containerRef.value || !pdfDoc) return
  
  const container = containerRef.value
  const scrollTop = container.scrollTop
  const containerHeight = container.clientHeight
  
  let cumulativeHeight = 0
  for (let i = 0; i < numPages.value; i++) {
    const pageHeight = pageHeights[i] || 800
    const pageTop = cumulativeHeight
    const pageBottom = cumulativeHeight + pageHeight
    
    if (pageBottom > scrollTop && pageTop < scrollTop + containerHeight + 500) {
      if (!renderedPages.has(i)) {
        renderPage(i)
      }
    }
    
    cumulativeHeight += pageHeight
  }
  
  updateCurrentPage(scrollTop)
}

const updateCurrentPage = (scrollTop: number) => {
  let cumulativeHeight = 0
  for (let i = 0; i < numPages.value; i++) {
    cumulativeHeight += pageHeights[i] || 800
    if (cumulativeHeight > scrollTop + 50) {
      currentPage.value = i + 1
      break
    }
  }
}

const onScroll = () => {
  renderVisiblePages()
}

const loadPdf = async () => {
  console.log('=== loadPdf called ===')
  console.log('pdfUrl:', props.pdfUrl)
  
  loading.value = true
  error.value = false
  numPages.value = 0
  renderedPages.clear()
  pageHeights = []
  pageWidths = []
  currentPage.value = 1
  
  try {
    console.log('开始加载 PDF...')
    const pdf = await pdfjsLib.getDocument({ 
  url: props.pdfUrl,
  verbosity: 0  // 设置日志级别：0=静默(不输出任何日志), 1=错误, 2=警告(默认), 3=信息
}).promise
    console.log('PDF 加载成功，页数:', pdf.numPages)
    
    pdfDoc = pdf
    numPages.value = pdf.numPages
    pageHeights = new Array(pdf.numPages).fill(800)  // 默认高度
    pageWidths = new Array(pdf.numPages).fill(600)    // 默认宽度
    
    await nextTick()
    
    // 【第一步：立即渲染首页】不等待所有页面高度计算
    console.log('渲染首页...')
    await renderPage(0)
    
    // 【第二步：立即显示首页】用户马上能看到内容
    loading.value = false
    loadingProgress.value = Math.round(100 / numPages.value) // 首页已加载
    console.log('PDF首页已显示')
    
    // 【第三步：后台异步计算页面高度】
    setTimeout(() => {
      calculateAllPageHeights()
    }, 50)
    
    // 【第四步：按优先级异步渲染剩余页面】
    // P1: 首页（已完成）
    // P2: 前10页（高优先级，快速渲染）
    // P3: 剩余所有页（低优先级，浏览器空闲时渲染）
    setTimeout(() => {
      renderWithPriority()
    }, 100)
  } catch (e: any) {
    console.error('加载 PDF 失败:', e.message || e)
    error.value = true
    loading.value = false
  }
}

// 后台计算所有页面高度（不阻塞渲染）
const calculateAllPageHeights = async () => {
  console.log('开始后台计算页面高度...')
  for (let i = 0; i < numPages.value; i++) {
    if (!pageHeights[i] || pageHeights[i] === 800) {
      try {
        const page = await pdfDoc.getPage(i + 1)
        const viewport = page.getViewport({ scale: scale.value })
        pageHeights[i] = viewport.height
        pageWidths[i] = viewport.width
      } catch (e) {
        console.error(`计算第 ${i + 1} 页高度失败:`, e)
      }
    }
  }
  console.log('页面高度计算完成:', pageHeights)
}

// 优先级异步渲染：P1=首页(已渲染), P2=前10页, P3=剩余所有页
const renderWithPriority = async () => {
  if (!pdfDoc) return

  const totalPages = numPages.value
  if (totalPages <= 1) return

  // 定义优先级队列
  // P2: 第2页到第10页（或总页数，取较小值）
  const priority2End = Math.min(totalPages, 10)
  const priority2Pages: number[] = []
  for (let i = 1; i < priority2End; i++) {
    if (!renderedPages.has(i)) {
      priority2Pages.push(i)
    }
  }

  // P3: 第11页到最后一页
  const priority3Pages: number[] = []
  for (let i = priority2End; i < totalPages; i++) {
    if (!renderedPages.has(i)) {
      priority3Pages.push(i)
    }
  }

  let renderedCount = 1 // 首页已渲染
  const totalToRender = priority2Pages.length + priority3Pages.length

  // 渲染单个页面并更新进度
  const renderAndUpdateProgress = async (pageIndex: number) => {
    if (renderedPages.has(pageIndex) || renderingPages.has(pageIndex)) return
    await renderPage(pageIndex)
    renderedCount++
    loadingProgress.value = Math.round((renderedCount / totalPages) * 100)
  }

  // P2: 渲染前10页（高优先级）
  console.log(`[P2] 开始渲染前 ${priority2Pages.length} 页...`)
  for (const i of priority2Pages) {
    await renderAndUpdateProgress(i)
    // 每渲染2页让出主线程，确保用户交互流畅
    if (priority2Pages.indexOf(i) % 2 === 0) {
      await new Promise(resolve => setTimeout(resolve, 30))
    }
  }
  console.log('[P2] 前10页渲染完成')

  // P3: 渲染剩余页面（低优先级，后台异步）
  if (priority3Pages.length > 0) {
    console.log(`[P3] 开始后台渲染剩余 ${priority3Pages.length} 页...`)
    // 使用 requestIdleCallback 或 setTimeout 让出主线程
    for (const i of priority3Pages) {
      // 等待浏览器空闲时再渲染
      await new Promise<void>(resolve => {
        if (typeof requestIdleCallback !== 'undefined') {
          requestIdleCallback(async () => {
            await renderAndUpdateProgress(i)
            resolve()
          }, { timeout: 200 })
        } else {
          setTimeout(async () => {
            await renderAndUpdateProgress(i)
            resolve()
          }, 50)
        }
      })
    }
    console.log('[P3] 剩余页面渲染完成')
  }

  loadingProgress.value = 100
  console.log('所有页面渲染完成')
}

const zoomIn = () => {
  scale.value = Math.min(3, scale.value + 0.1)
  reRenderAll()
}

const zoomOut = () => {
  scale.value = Math.max(0.5, scale.value - 0.1)
  reRenderAll()
}

const resetZoom = () => {
  scale.value = 1.0
  reRenderAll()
}

const fitWidth = () => {
  if (!containerRef.value || pageWidths.length === 0) return
  
  const containerWidth = containerRef.value.clientWidth - 20
  const firstPageWidth = pageWidths[0] || 600
  
  scale.value = containerWidth / firstPageWidth
  reRenderAll()
}

const reRenderAll = async () => {
  if (!pdfDoc) return
  
  // 记录缩放前的当前页面
  const currentScrollTop = containerRef.value?.scrollTop || 0
  let currentDisplayPage = currentPage.value
  
  // 计算缩放前显示的是第几页
  if (currentScrollTop > 0 && pageHeights.length > 0) {
    let cumulativeHeight = 0
    for (let i = 0; i < numPages.value; i++) {
      cumulativeHeight += pageHeights[i] || 800
      if (cumulativeHeight > currentScrollTop + 50) {
        currentDisplayPage = i + 1
        break
      }
    }
  }
  
  console.log(`缩放前显示第 ${currentDisplayPage} 页`)
  
  renderedPages.clear()
  
  // 重新计算所有页面高度（考虑当前缩放比例）
  for (let i = 0; i < numPages.value; i++) {
    const page = await pdfDoc.getPage(i + 1)
    const viewport = page.getViewport({ scale: scale.value })
    pageHeights[i] = viewport.height
    pageWidths[i] = viewport.width
  }
  
  await nextTick()
  
  // 重新渲染所有页面（强制渲染）
  for (let i = 0; i < numPages.value; i++) {
    await renderPage(i, true)
  }
  
  await nextTick()
  
  // 根据新的页面高度计算新的滚动位置，保持显示同一页面
  if (containerRef.value && currentDisplayPage > 0) {
    const targetIndex = currentDisplayPage - 1
    let newScrollTop = 0
    for (let i = 0; i < targetIndex; i++) {
      newScrollTop += pageHeights[i] || 800
    }
    
    console.log(`缩放后滚动到 ${newScrollTop} (第 ${currentDisplayPage} 页)`)
    containerRef.value.scrollTop = newScrollTop
    currentPage.value = currentDisplayPage
  }
  
  renderVisiblePages()
}

const goToPage = () => {
  if (currentPage.value >= 1 && currentPage.value <= numPages.value) {
    scrollToPage(currentPage.value)
  }
}

const prevPage = () => {
  if (currentPage.value > 1) {
    scrollToPage(currentPage.value - 1)
  }
}

const nextPage = () => {
  if (currentPage.value < numPages.value) {
    scrollToPage(currentPage.value + 1)
  }
}

const scrollToPage = async (pageNum: number) => {
  console.log('scrollToPage called with pageNum:', pageNum)
  console.log('pageHeights:', pageHeights)
  console.log('current scale:', scale.value)
  
  if (!containerRef.value) {
    console.error('scrollToPage failed: containerRef is null')
    return
  }
  
  if (pageHeights.length === 0) {
    console.error('scrollToPage failed: pageHeights is empty')
    return
  }
  
  const targetIndex = pageNum - 1
  if (targetIndex < 0 || targetIndex >= pageHeights.length) {
    console.error('scrollToPage failed: invalid targetIndex', targetIndex)
    return
  }
  
  // 预渲染目标页面及其前后的页面（确保滚动时有足够高度）
  const preRenderStart = Math.max(0, targetIndex - 2)
  const preRenderEnd = Math.min(numPages.value - 1, targetIndex + 5)
  
  console.log(`预渲染页面 ${preRenderStart + 1} - ${preRenderEnd + 1}`)
  
  // 先渲染目标页面，确保有正确的高度
  for (let i = preRenderStart; i <= preRenderEnd; i++) {
    await renderPage(i)
  }
  
  // 等待渲染完成后再计算滚动位置
  await nextTick()
  
  // 确保所有页面高度都已更新
  await ensureAllPageHeights()
  
  // 计算目标滚动位置
  let targetScrollTop = 0
  for (let i = 0; i < targetIndex; i++) {
    targetScrollTop += (pageHeights[i] || 800)
  }
  
  console.log('targetScrollTop:', targetScrollTop)
  
  const container = containerRef.value
  
  // 直接设置 scrollTop
  container.scrollTop = targetScrollTop
  
  // 延迟检查并修正
  setTimeout(() => {
    console.log('scrollTop after:', container.scrollTop)
    if (Math.abs(container.scrollTop - targetScrollTop) > 10) {
      console.log('滚动位置不准确，重新设置')
      container.scrollTop = targetScrollTop
    }
  }, 100)
  
  currentPage.value = pageNum
}

// 确保所有页面高度都已计算
const ensureAllPageHeights = async () => {
  if (!pdfDoc) return
  
  for (let i = 0; i < numPages.value; i++) {
    if (!pageHeights[i]) {
      const page = await pdfDoc.getPage(i + 1)
      const viewport = page.getViewport({ scale: scale.value })
      pageHeights[i] = viewport.height
      pageWidths[i] = viewport.width
    }
  }
}

const searchText = async (text: string): Promise<number | null> => {
  console.log('搜索文本:', text)
  
  if (!pdfDoc || !text.trim()) {
    console.error('搜索失败：PDF未加载或搜索文本为空')
    return null
  }
  
  // 优化搜索策略：使用多个短文本片段进行搜索
  const searchFragments = [
    text.substring(0, 50),   // 前50字符
    text.substring(0, 30),   // 前30字符
    text.substring(0, 20),   // 前20字符
  ].filter(t => t.trim().length >= 10)  // 至少10字符
  
  console.log('搜索片段:', searchFragments)
  
  // 遍历所有页面查找匹配的文本
  for (let i = 0; i < numPages.value; i++) {
    try {
      const page = await pdfDoc.getPage(i + 1)
      const textContent = await page.getTextContent()
      const pageText = textContent.items.map((item: any) => item.str).join('')
      
      // 检查页面是否包含任一搜索片段
      for (const fragment of searchFragments) {
        if (pageText.includes(fragment)) {
          console.log(`在第 ${i + 1} 页找到匹配内容（片段: ${fragment.substring(0, 20)}...）`)
          scrollToPage(i + 1)
          return i + 1  // 返回找到的页码
        }
      }
    } catch (e) {
      console.error(`搜索第 ${i + 1} 页失败:`, e)
    }
  }
  
  console.log('未找到匹配内容')
  return null
}

watch(scale, () => {
  console.log('缩放变化:', scale.value)
})

watch(currentPage, (newPage) => {
  if (newPage >= 1 && newPage <= numPages.value && containerRef.value) {
    const scrollTop = pageHeights.slice(0, newPage - 1).reduce((a, b) => a + (b || 800), 0)
    containerRef.value.scrollTop = scrollTop
  }
})

watch(() => props.pdfUrl, () => {
  if (props.pdfUrl) {
    loadPdf()
  }
})

onMounted(() => {
  if (props.pdfUrl) {
    loadPdf()
  }
})

onUnmounted(() => {
  if (pdfDoc && typeof pdfDoc.destroy === 'function') {
    pdfDoc.destroy()
  }
})

defineExpose({
  scrollToPage,
  searchText
})
</script>

<style scoped>
.pdf-viewer-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: #525659;
  position: relative;
}

.pdf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 16px;
  background: #3c3f41;
  border-bottom: 1px solid #2a2d2f;
  position: relative;
  z-index: 10;
  flex-shrink: 0;
}

.page-selector {
  display: flex;
  align-items: center;
  gap: 6px;
}

.page-nav-btn {
  padding: 4px 8px;
  font-size: 12px;
}

.page-input {
  width: 50px;
  padding: 4px 8px;
  background: #4a4e51;
  border: 1px solid #5a5e61;
  border-radius: 4px;
  color: white;
  font-size: 14px;
  text-align: center;
  /* 隐藏数字输入框的原生箭头按钮 */
  -webkit-appearance: textfield;
  -moz-appearance: textfield;
}

.page-input::-webkit-outer-spin-button,
.page-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.page-input:focus {
  outline: none;
  border-color: #4a90d9;
}

.page-separator {
  color: #888;
  font-size: 14px;
}

.page-total {
  color: white;
  font-size: 14px;
}

.toolbar-spacer {
  flex: 1;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px 12px;
  background: #4a4e51;
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
  min-width: 32px;
}

.toolbar-btn:hover:not(:disabled) {
  background: #5a5e61;
}

.toolbar-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.zoom-level {
  color: white;
  font-size: 14px;
  min-width: 50px;
  text-align: center;
}

.pdf-container {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

.pdf-content {
  padding: 10px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pdf-canvas {
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  background: white;
}

.pdf-loading,
.pdf-error {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(82, 86, 89, 0.9);
  z-index: 20;
  gap: 16px;
}

.loading-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.pdf-loading p {
  color: white;
  margin: 0;
}

.pdf-progress {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(60, 63, 65, 0.9);
  border-radius: 8px;
  backdrop-filter: blur(8px);
  z-index: 20;
}

.progress-bar {
  width: 160px;
  height: 4px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px;
  transition: width 0.3s ease;
}

.progress-text {
  color: white;
  font-size: 12px;
  min-width: 36px;
}

.error-icon {
  font-size: 48px;
}

.pdf-error h3 {
  margin: 0 0 8px 0;
  color: white;
}

.pdf-error p {
  margin: 0;
  color: white;
  opacity: 0.8;
}
</style>
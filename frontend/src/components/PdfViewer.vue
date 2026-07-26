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
        <div
          v-for="i in numPages"
          :key="i - 1"
          class="pdf-page-shell"
          :class="{ 'citation-target': highlightedPage === i }"
          :style="pageShellStyle(i - 1)"
        >
          <canvas
            :ref="el => setCanvasRef(i - 1, el as HTMLCanvasElement | null)"
            class="pdf-canvas"
          />
        </div>
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
        <div class="progress-fill" :style="{ transform: `scaleX(${loadingProgress / 100})` }"></div>
      </div>
      <span class="progress-text">{{ loadingProgress }}%</span>
    </div>
    
    <!-- 错误状态 -->
    <div v-if="error" class="pdf-error">
      <div class="error-icon">⚠️</div>
      <h3>PDF 加载失败</h3>
      <p>{{ errorMessage }}</p>
      <button type="button" class="pdf-retry-button" @click="loadPdf">重新加载</button>
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

const emit = defineEmits<{
  'page-change': [page: number]
  'load-error': [message: string]
  'load-success': []
}>()

const containerRef = ref<HTMLElement | null>(null)
const contentRef = ref<HTMLElement | null>(null)
const canvasRefs = ref<(HTMLCanvasElement | null)[]>([])
const loading = ref(true)
const error = ref(false)
const errorMessage = ref('无法加载 PDF 文件')
const numPages = ref(0)
const scale = ref(1.0)
const currentPage = ref(1)
const highlightedPage = ref<number | null>(null)

let pdfDoc: any = null
let loadingTask: any = null
let loadSequence = 0
let pageHeights: number[] = []
let pageWidths: number[] = []
const renderedPages = new Set<number>()
const renderingPages = new Set<number>()
const loadingProgress = ref(0) // 加载进度 0-100
let renderedScale = 1
let scrollFrame: number | null = null
let highlightTimer: ReturnType<typeof setTimeout> | null = null

const setCanvasRef = (index: number, el: HTMLCanvasElement | null) => {
  canvasRefs.value[index] = el
}

const pageShellStyle = (index: number) => ({
  width: `${pageWidths[index] || 600}px`,
  height: `${pageHeights[index] || 800}px`
})

const updatePageElementSize = (index: number) => {
  const canvas = canvasRefs.value[index]
  if (!canvas) return
  const width = `${pageWidths[index] || 600}px`
  const height = `${pageHeights[index] || 800}px`
  canvas.style.width = width
  canvas.style.height = height
  if (canvas.parentElement) {
    canvas.parentElement.style.width = width
    canvas.parentElement.style.height = height
  }
}

const renderPage = async (pageIndex: number, forceRender = false) => {
  // 如果已经渲染过且不是强制渲染，则跳过
  if (!forceRender && renderedPages.has(pageIndex)) return
  if (renderingPages.has(pageIndex)) return
  
  renderingPages.add(pageIndex)
  
  try {
    const page = await pdfDoc.getPage(pageIndex + 1)
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
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
    updatePageElementSize(pageIndex)
    
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
    
    cumulativeHeight += pageHeight + 10
  }
  
  updateCurrentPage(scrollTop)
}

const prefetchNearbyPages = (pageIndex: number) => {
  for (const index of [pageIndex, pageIndex - 1, pageIndex + 1]) {
    if (index >= 0 && index < numPages.value && !renderedPages.has(index)) {
      void renderPage(index)
    }
  }
}

const updateCurrentPage = (scrollTop: number) => {
  let cumulativeHeight = 0
  for (let i = 0; i < numPages.value; i++) {
    cumulativeHeight += (pageHeights[i] || 800) + 10
    if (cumulativeHeight > scrollTop + 50) {
      const nextPage = i + 1
      if (currentPage.value !== nextPage) {
        currentPage.value = nextPage
        emit('page-change', nextPage)
      }
      break
    }
  }
}

const onScroll = () => {
  if (scrollFrame !== null) return
  scrollFrame = requestAnimationFrame(() => {
    scrollFrame = null
    renderVisiblePages()
  })
}

const loadPdf = async () => {
  const sequence = ++loadSequence
  loading.value = true
  error.value = false
  errorMessage.value = '无法加载 PDF 文件'
  numPages.value = 0
  renderedPages.clear()
  pageHeights = []
  pageWidths = []
  currentPage.value = 1
  
  try {
    if (loadingTask) {
      await loadingTask.destroy().catch(() => undefined)
      loadingTask = null
    }
    if (pdfDoc) {
      await pdfDoc.destroy().catch(() => undefined)
      pdfDoc = null
    }

    loadingTask = pdfjsLib.getDocument({
      url: props.pdfUrl,
      disableRange: false,
      disableStream: false,
      disableAutoFetch: false,
      rangeChunkSize: 1024 * 1024,
      verbosity: 0
    })
    const pdf = await loadingTask.promise
    if (sequence !== loadSequence) {
      await pdf.destroy()
      return
    }

    pdfDoc = pdf
    loadingTask = null
    const firstPage = await pdf.getPage(1)
    const firstViewport = firstPage.getViewport({ scale: scale.value })
    pageHeights = new Array(pdf.numPages).fill(firstViewport.height)
    pageWidths = new Array(pdf.numPages).fill(firstViewport.width)
    renderedScale = scale.value
    numPages.value = pdf.numPages
    
    await nextTick()
    canvasRefs.value.forEach((_, index) => updatePageElementSize(index))
    
    // 【第一步：立即渲染首页】不等待所有页面高度计算
    await renderPage(0)
    
    // 【第二步：立即显示首页】用户马上能看到内容
    loading.value = false
    loadingProgress.value = 100
    emit('load-success')
    renderVisiblePages()
    prefetchNearbyPages(0)
  } catch (e: any) {
    if (sequence !== loadSequence) return
    console.error('加载 PDF 失败:', e.message || e)
    loadingTask = null
    errorMessage.value = e?.message
      ? `无法读取 PDF：${e.message}`
      : '无法读取 PDF 文件，请重试'
    error.value = true
    loading.value = false
    emit('load-error', errorMessage.value)
  }
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
  
  scale.value = scale.value * containerWidth / firstPageWidth
  reRenderAll()
}

const reRenderAll = async () => {
  if (!pdfDoc) return

  const currentDisplayPage = currentPage.value
  const ratio = scale.value / renderedScale
  renderedScale = scale.value
  renderedPages.clear()

  for (let i = 0; i < numPages.value; i++) {
    pageHeights[i] = (pageHeights[i] || 800) * ratio
    pageWidths[i] = (pageWidths[i] || 600) * ratio
    const canvas = canvasRefs.value[i]
    if (canvas) {
      canvas.width = 1
      canvas.height = 1
      updatePageElementSize(i)
    }
  }

  await nextTick()

  if (containerRef.value && currentDisplayPage > 0) {
    const targetIndex = currentDisplayPage - 1
    let newScrollTop = 0
    for (let i = 0; i < targetIndex; i++) {
      newScrollTop += (pageHeights[i] || 800) + 10
    }
    containerRef.value.scrollTop = newScrollTop
  }

  await renderPage(currentDisplayPage - 1, true)
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
  
  // 计算目标滚动位置
  let targetScrollTop = 0
  for (let i = 0; i < targetIndex; i++) {
    targetScrollTop += (pageHeights[i] || 800) + 10
  }
  
  const container = containerRef.value
  
  // 直接设置 scrollTop
  container.scrollTop = targetScrollTop
  
  // 延迟检查并修正
  setTimeout(() => {
    if (Math.abs(container.scrollTop - targetScrollTop) > 10) {
      container.scrollTop = targetScrollTop
    }
  }, 100)
  
  currentPage.value = pageNum
  emit('page-change', pageNum)

  // 先完成导航反馈，再异步渲染目标页和相邻页，避免 Canvas 渲染阻塞点击。
  await nextTick()
  prefetchNearbyPages(targetIndex)
}

const highlightPage = (pageNum: number) => {
  if (highlightTimer) clearTimeout(highlightTimer)
  highlightedPage.value = pageNum
  highlightTimer = setTimeout(() => {
    highlightedPage.value = null
    highlightTimer = null
  }, 2600)
}

const normalizeSearchText = (value: string) => value
  .normalize('NFKC')
  .toLowerCase()
  .replace(/[^\p{L}\p{N}]+/gu, '')

const buildSearchFragments = (values: string[]): string[] => {
  const fragments = new Set<string>()
  for (const value of values) {
    const normalized = normalizeSearchText(value)
    if (normalized.length < 8) continue
    fragments.add(normalized)
    for (const length of [32, 24, 16, 12]) {
      if (normalized.length < length) continue
      const step = Math.max(6, Math.floor(length / 2))
      for (let start = 0; start + length <= normalized.length; start += step) {
        fragments.add(normalized.slice(start, start + length))
      }
      fragments.add(normalized.slice(-length))
    }
  }
  return Array.from(fragments).sort((a, b) => b.length - a.length)
}

const searchText = async (text: string | string[]): Promise<number | null> => {
  const searchValues = (Array.isArray(text) ? text : [text]).filter(value => value?.trim())

  if (!pdfDoc || searchValues.length === 0) {
    console.error('搜索失败：PDF未加载或搜索文本为空')
    return null
  }
  const searchFragments = buildSearchFragments(searchValues)

  // 遍历所有页面查找匹配的文本
  for (let i = 0; i < numPages.value; i++) {
    try {
      const page = await pdfDoc.getPage(i + 1)
      const textContent = await page.getTextContent()
      const pageText = normalizeSearchText(
        textContent.items.map((item: any) => item.str).join(' ')
      )
      
      // 检查页面是否包含任一搜索片段
      for (const fragment of searchFragments) {
        if (pageText.includes(fragment)) {
          await scrollToPage(i + 1)
          return i + 1  // 返回找到的页码
        }
      }
    } catch (e) {
      console.error(`搜索第 ${i + 1} 页失败:`, e)
    }
  }
  
  return null
}

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
  loadSequence += 1
  if (scrollFrame !== null) {
    cancelAnimationFrame(scrollFrame)
  }
  if (loadingTask && typeof loadingTask.destroy === 'function') loadingTask.destroy()
  if (pdfDoc && typeof pdfDoc.destroy === 'function') pdfDoc.destroy()
  if (highlightTimer) clearTimeout(highlightTimer)
})

defineExpose({
  scrollToPage,
  searchText,
  highlightPage,
  fitWidth
})
</script>

<style scoped>
.pdf-viewer-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
  background: oklch(0.36 0.012 45);
  position: relative;
}

.pdf-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 16px;
  background: var(--pa-toolbar);
  border-bottom: 1px solid oklch(0.22 0.015 45);
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
  background: var(--pa-toolbar-control);
  border: 1px solid oklch(0.46 0.018 45);
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
  border-color: oklch(0.72 0.14 55);
  box-shadow: 0 0 0 2px oklch(0.50 0.16 45 / 0.2);
}

.page-separator {
  color: oklch(0.76 0.01 55);
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
  background: var(--pa-toolbar-control);
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
  min-width: 32px;
}

.toolbar-btn:hover:not(:disabled) {
  background: oklch(0.43 0.022 45);
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
  display: block;
  width: 100%;
  height: 100%;
  background: white;
}

.pdf-page-shell {
  flex: 0 0 auto;
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  background: white;
}

.pdf-page-shell.citation-target {
  outline: 3px solid var(--pa-primary);
  outline-offset: 3px;
  animation: citation-page-pulse 1.3s cubic-bezier(0.25, 1, 0.5, 1) 2;
}

@keyframes citation-page-pulse {
  0%, 100% { box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3); }
  50% { box-shadow: 0 0 0 8px oklch(0.50 0.16 45 / 0.22), 0 4px 18px rgba(0, 0, 0, 0.38); }
}

@media (prefers-reduced-motion: reduce) {
  .pdf-page-shell.citation-target { animation: none; }
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
  background: var(--pa-toolbar);
  border-radius: 8px;
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
  width: 100%;
  height: 100%;
  background: var(--pa-primary);
  border-radius: 2px;
  transform-origin: left;
  transition: transform 0.3s ease;
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

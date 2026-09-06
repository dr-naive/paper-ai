<template>
  <div class="pdf-viewer-wrapper">
    <!-- 工具栏 -->
    <div class="pdf-toolbar" role="toolbar" aria-label="PDF 阅读工具">
      <div class="page-selector">
        <button type="button" class="toolbar-btn page-nav-btn" aria-label="上一页" title="上一页" @click="prevPage" :disabled="currentPage <= 1">
          <span aria-hidden="true">◀</span>
        </button>
        <input
          type="number"
          v-model.number="currentPage"
          @keydown.enter="goToPage"
          min="1"
          :max="numPages"
          class="page-input"
          aria-label="当前页码"
        />
        <span class="page-separator">/</span>
        <span class="page-total">{{ numPages }}</span>
        <button type="button" class="toolbar-btn page-nav-btn" aria-label="下一页" title="下一页" @click="nextPage" :disabled="currentPage >= numPages">
          <span aria-hidden="true">▶</span>
        </button>
      </div>
      <div class="toolbar-spacer"></div>
      <button type="button" class="toolbar-btn" aria-label="缩小 PDF" title="缩小" @click="zoomOut" :disabled="scale <= 0.5">
        <span aria-hidden="true">−</span>
      </button>
      <span class="zoom-level">{{ Math.round(scale * 100) }}%</span>
      <button type="button" class="toolbar-btn" aria-label="放大 PDF" title="放大" @click="zoomIn" :disabled="scale >= 3">
        <span aria-hidden="true">+</span>
      </button>
      <button type="button" class="toolbar-btn" aria-label="恢复原始缩放比例" @click="resetZoom">
        <span>100%</span>
      </button>
      <button type="button" class="toolbar-btn" aria-label="让 PDF 适应可用宽度" @click="fitWidth">
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
          <div
            v-if="citationHighlight?.page === i"
            class="citation-highlight-layer"
            aria-hidden="true"
          >
            <span
              v-for="(rect, rectIndex) in citationHighlight.rects"
              :key="rectIndex"
              class="citation-highlight-rect"
              :style="{
                left: `${rect.left}px`,
                top: `${rect.top}px`,
                width: `${rect.width}px`,
                height: `${rect.height}px`
              }"
            />
          </div>
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
import type { PdfLoadTelemetry } from '@/api/paper'
import {
  PDF_CACHE_NAME,
  paperIdFromPdfUrl,
  readCachedPdf,
  removeCachedPdf,
  writeCachedPdf
} from '@/utils/pdfCache'

pdfjsLib.GlobalWorkerOptions.workerPort = new pdfWorker()

const props = defineProps<{
  pdfUrl: string
}>()

const emit = defineEmits<{
  'page-change': [page: number]
  'load-error': [message: string]
  'load-success': [pages: number]
  'load-metrics': [metrics: PdfLoadTelemetry]
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
type CitationRect = { left: number; top: number; width: number; height: number }
type CitationLocation = { page: number; rects: CitationRect[]; precise: boolean }
const citationHighlight = ref<CitationLocation | null>(null)

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
let citationHighlightTimer: ReturnType<typeof setTimeout> | null = null

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

const withQueryParam = (url: string, name: string, value: string) => {
  const separator = url.includes('?') ? '&' : '?'
  return `${url}${separator}${encodeURIComponent(name)}=${encodeURIComponent(value)}`
}

const performanceNow = () => (
  typeof performance !== 'undefined' && typeof performance.now === 'function'
    ? performance.now()
    : Date.now()
)

const elapsedMilliseconds = (startedAt: number | null) => (
  startedAt === null ? 0 : Math.max(0, performanceNow() - startedAt)
)

const roundedMilliseconds = (value: number) => Math.round(Math.max(0, value) * 10) / 10

const countPdfNetworkRequests = (url: string) => {
  if (typeof performance === 'undefined' || typeof performance.getEntriesByType !== 'function') {
    return 0
  }
  try {
    const target = new URL(url, window.location.origin)
    return performance.getEntriesByType('resource').filter((entry) => {
      try {
        const entryUrl = new URL(entry.name)
        return entryUrl.origin === target.origin && entryUrl.pathname === target.pathname
      } catch {
        return false
      }
    }).length
  } catch {
    return 0
  }
}

const pdfRequestHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

const attachLoadingProgress = (task: any) => {
  if (!task) return
  task.onProgress = ({ loaded = 0, total = 0 }: { loaded?: number; total?: number }) => {
    if (total > 0) {
      // Keep 100% reserved for a successfully rendered first page.
      loadingProgress.value = Math.min(99, Math.max(0, Math.round((loaded / total) * 100)))
    }
  }
}

const scheduleCacheWarmup = (
  paperId: string,
  pdf: any,
  sequence: number,
  cachedData?: ArrayBuffer,
) => {
  const warmup = () => {
    if (sequence !== loadSequence) return
    if (cachedData) {
      void writeCachedPdf(paperId, new Uint8Array(cachedData))
      return
    }
    void pdf.getData()
      .then((data: Uint8Array) => writeCachedPdf(paperId, data))
      .catch((cacheError: unknown) => {
        console.warn('准备 PDF 本地缓存失败:', cacheError)
      })
  }

  const idleWindow = window as Window & {
    requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number
  }
  if (idleWindow.requestIdleCallback) {
    idleWindow.requestIdleCallback(warmup, { timeout: 2000 })
  } else {
    window.setTimeout(warmup, 250)
  }
}

const destroyLoadingTask = async () => {
  const task = loadingTask
  loadingTask = null
  if (task && typeof task.destroy === 'function') {
    await task.destroy().catch(() => undefined)
  }
}

const fetchPdfBytes = async (url: string): Promise<Uint8Array> => {
  const response = await fetch(
    withQueryParam(url, '_paperai_retry', `${Date.now()}-${Math.random().toString(36).slice(2)}`),
    {
      cache: 'no-store',
      headers: {
        Accept: 'application/pdf',
        ...pdfRequestHeaders()
      }
    }
  )
  if (!response.ok) {
    throw new Error(`PDF 请求失败（HTTP ${response.status}）`)
  }

  const declaredLength = Number(response.headers.get('content-length') || 0)
  const data = new Uint8Array(await response.arrayBuffer())
  if (declaredLength > 0 && declaredLength !== data.byteLength) {
    throw new Error(`PDF 响应长度不一致（声明 ${declaredLength} 字节，收到 ${data.byteLength} 字节）`)
  }
  if (
    data.byteLength < 5
    || data[0] !== 0x25
    || data[1] !== 0x50
    || data[2] !== 0x44
    || data[3] !== 0x46
    || data[4] !== 0x2d
  ) {
    throw new Error('服务器返回的内容不是有效 PDF')
  }
  return data
}

const loadPdfFromNetwork = async (url: string, sequence: number) => {
  try {
    // Keep PDF.js range/stream loading as the fast path.  It is important for
    // large papers and remains compatible with the existing PDF endpoint.
    loadingTask = pdfjsLib.getDocument({
      url,
      httpHeaders: pdfRequestHeaders(),
      disableRange: false,
      disableStream: false,
      // Let the first page request only the chunks it needs. Full-document
      // warming is scheduled after the first page so it cannot compete with
      // the interaction that makes the Reader feel ready.
      disableAutoFetch: true,
      rangeChunkSize: 2 * 1024 * 1024,
      verbosity: 0
    })
    attachLoadingProgress(loadingTask)
    return {
      pdf: await loadingTask.promise,
      source: 'range' as const
    }
  } catch (firstError) {
    await destroyLoadingTask()
    if (sequence !== loadSequence) throw firstError

    // A proxy/browser cache can truncate one of the range responses.  Retry
    // once with a cache-busted, complete response and pass verified bytes to
    // PDF.js so the worker no longer has to request additional ranges.
    const data = await fetchPdfBytes(url)
    if (sequence !== loadSequence) throw firstError
    loadingTask = pdfjsLib.getDocument({ data, verbosity: 0 })
    attachLoadingProgress(loadingTask)
    try {
      return {
        pdf: await loadingTask.promise,
        source: 'fallback' as const
      }
    } catch (fallbackError) {
      await destroyLoadingTask()
      throw fallbackError
    }
  }
}

const loadPdf = async () => {
  const sequence = ++loadSequence
  const loadStartedAt = performanceNow()
  loading.value = true
  error.value = false
  errorMessage.value = '无法加载 PDF 文件'
  numPages.value = 0
  loadingProgress.value = 0
  renderedPages.clear()
  pageHeights = []
  pageWidths = []
  currentPage.value = 1

  let cacheLookupMs = 0
  let documentMs = 0
  let firstPageRenderMs = 0
  let documentStartedAt: number | null = null
  let firstPageRenderStartedAt: number | null = null
  let source: PdfLoadTelemetry['source'] = 'range'
  let cacheBytes = 0
  const networkRequestsBefore = countPdfNetworkRequests(props.pdfUrl)
  
  try {
    await destroyLoadingTask()
    if (pdfDoc) {
      await pdfDoc.destroy().catch(() => undefined)
      pdfDoc = null
    }

    const paperId = paperIdFromPdfUrl(props.pdfUrl)
    const forceReload = new URL(props.pdfUrl, window.location.origin).searchParams.has('t')
    if (paperId && forceReload) await removeCachedPdf(paperId)
    const cacheLookupStartedAt = performanceNow()
    const cachedPdf = paperId && !forceReload
      ? await readCachedPdf(paperId)
      : null
    cacheLookupMs = elapsedMilliseconds(cacheLookupStartedAt)
    let loadedFromCache = false
    let pdf: any
    documentStartedAt = performanceNow()
    if (cachedPdf) {
      source = 'cache'
      cacheBytes = cachedPdf.data.byteLength
      try {
        loadingTask = pdfjsLib.getDocument({
          // PDF.js transfers the data buffer to its worker. Keep the cached
          // response intact so a legacy v1 entry can be promoted after load.
          data: new Uint8Array(cachedPdf.data.slice(0)),
          verbosity: 0
        })
        attachLoadingProgress(loadingTask)
        pdf = await loadingTask.promise
        loadedFromCache = true
      } catch {
        await destroyLoadingTask()
        await removeCachedPdf(paperId as string)
        if (sequence !== loadSequence) return
        source = 'range'
        cacheBytes = 0
        const networkLoad = await loadPdfFromNetwork(props.pdfUrl, sequence)
        pdf = networkLoad.pdf
        source = networkLoad.source
      }
    } else {
      const networkLoad = await loadPdfFromNetwork(props.pdfUrl, sequence)
      pdf = networkLoad.pdf
      source = networkLoad.source
    }
    documentMs = elapsedMilliseconds(documentStartedAt)
    if (sequence !== loadSequence) {
      await pdf.destroy()
      return
    }

    pdfDoc = pdf
    loadingTask = null
    firstPageRenderStartedAt = performanceNow()
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
    firstPageRenderMs = elapsedMilliseconds(firstPageRenderStartedAt)
    
    // 【第二步：立即显示首页】用户马上能看到内容
    loading.value = false
    loadingProgress.value = 100
    emit('load-success', pdf.numPages)
    emit('load-metrics', {
      outcome: 'success',
      source,
      total_ms: roundedMilliseconds(elapsedMilliseconds(loadStartedAt)),
      cache_lookup_ms: roundedMilliseconds(cacheLookupMs),
      document_ms: roundedMilliseconds(documentMs),
      first_page_render_ms: roundedMilliseconds(firstPageRenderMs),
      pages: pdf.numPages,
      network_requests: Math.max(0, countPdfNetworkRequests(props.pdfUrl) - networkRequestsBefore),
      cache_bytes: cacheBytes
    })
    renderVisiblePages()
    prefetchNearbyPages(0)

    if (paperId && loadedFromCache && cachedPdf && cachedPdf.cacheName !== PDF_CACHE_NAME) {
      scheduleCacheWarmup(paperId, pdf, sequence, cachedPdf.data)
    } else if (paperId && !loadedFromCache) {
      scheduleCacheWarmup(paperId, pdf, sequence)
    }
  } catch (e: any) {
    if (sequence !== loadSequence) return
    console.error('加载 PDF 失败:', e.message || e)
    documentMs = elapsedMilliseconds(documentStartedAt)
    firstPageRenderMs = elapsedMilliseconds(firstPageRenderStartedAt)
    loadingTask = null
    errorMessage.value = e?.message
      ? `无法读取 PDF：${e.message}`
      : '无法读取 PDF 文件，请重试'
    error.value = true
    loading.value = false
    emit('load-metrics', {
      outcome: 'error',
      source,
      total_ms: roundedMilliseconds(elapsedMilliseconds(loadStartedAt)),
      cache_lookup_ms: roundedMilliseconds(cacheLookupMs),
      document_ms: roundedMilliseconds(documentMs),
      first_page_render_ms: roundedMilliseconds(firstPageRenderMs),
      pages: 0,
      network_requests: Math.max(0, countPdfNetworkRequests(props.pdfUrl) - networkRequestsBefore),
      cache_bytes: cacheBytes,
      error: typeof e?.name === 'string' ? e.name : 'PDF_LOAD_ERROR'
    })
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

const fitWidth = async () => {
  if (!containerRef.value || pageWidths.length === 0) return
  
  const containerWidth = containerRef.value.clientWidth - 20
  const firstPageWidth = pageWidths[0] || 600
  
  scale.value = scale.value * containerWidth / firstPageWidth
  await reRenderAll()
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
  citationHighlight.value = null
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

type NormalizedTextMap = {
  text: string
  itemIndexes: number[]
  itemOffsets: number[]
  itemLengths: number[]
}

const buildNormalizedTextMap = (items: any[]): NormalizedTextMap => {
  let text = ''
  const itemIndexes: number[] = []
  const itemOffsets: number[] = []
  const itemLengths = items.map(item => Array.from(
    normalizeSearchText(String(item.str || ''))
  ).length)

  items.forEach((item, itemIndex) => {
    const normalized = Array.from(normalizeSearchText(String(item.str || '')))
    normalized.forEach((character, offset) => {
      text += character
      itemIndexes.push(itemIndex)
      itemOffsets.push(offset)
    })
  })

  return { text, itemIndexes, itemOffsets, itemLengths }
}

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

const findTextMatch = (
  items: any[],
  searchValues: string[]
): { start: number; end: number; map: NormalizedTextMap } | null => {
  const map = buildNormalizedTextMap(items)
  if (!map.text) return null

  for (const fragment of buildSearchFragments(searchValues)) {
    const start = map.text.indexOf(fragment)
    if (start >= 0) return { start, end: start + fragment.length, map }
  }
  return null
}

const itemRect = (
  item: any,
  viewport: any,
  styles: Record<string, any>,
  startRatio = 0,
  endRatio = 1
): CitationRect | null => {
  if (!item?.transform) return null
  const transformed = pdfjsLib.Util.transform(viewport.transform, item.transform)
  const fontHeight = Math.max(
    Math.hypot(transformed[2], transformed[3]),
    Number(item.height || 0) * viewport.scale,
    8
  )
  const fontStyle = styles?.[item.fontName] || {}
  const fontAscent = Number.isFinite(fontStyle.ascent)
    ? fontStyle.ascent * fontHeight
    : Number.isFinite(fontStyle.descent)
      ? (1 + fontStyle.descent) * fontHeight
      : fontHeight * 0.82
  const fullWidth = Math.max(
    Number(item.width || 0) * viewport.scale,
    fontHeight * 0.45
  )
  return {
    left: transformed[4] + fullWidth * startRatio,
    top: transformed[5] - fontAscent,
    width: Math.max(fullWidth * (endRatio - startRatio), 3),
    height: Math.max(fontHeight * 0.94, 6)
  }
}

const mergeLineRects = (rects: CitationRect[]): CitationRect[] => {
  const lines: CitationRect[] = []
  for (const rect of rects.sort((a, b) => a.top - b.top || a.left - b.left)) {
    const line = lines.find(existing => (
      Math.abs(existing.top - rect.top) <= Math.max(existing.height, rect.height) * 0.55
      && rect.left <= existing.left + existing.width + Math.max(existing.height, rect.height)
    ))
    if (!line) {
      lines.push({ ...rect })
      continue
    }
    const right = Math.max(line.left + line.width, rect.left + rect.width)
    const bottom = Math.max(line.top + line.height, rect.top + rect.height)
    line.left = Math.min(line.left, rect.left)
    line.top = Math.min(line.top, rect.top)
    line.width = right - line.left
    line.height = bottom - line.top
  }
  return lines
}

const matchRects = (
  items: any[],
  viewport: any,
  styles: Record<string, any>,
  match: { start: number; end: number; map: NormalizedTextMap }
): CitationRect[] => {
  const ranges = new Map<number, { start: number; end: number }>()
  for (let index = match.start; index < match.end; index += 1) {
    const itemIndex = match.map.itemIndexes[index]
    const offset = match.map.itemOffsets[index]
    if (itemIndex === undefined || offset === undefined) continue
    const range = ranges.get(itemIndex)
    if (range) {
      range.start = Math.min(range.start, offset)
      range.end = Math.max(range.end, offset + 1)
    } else {
      ranges.set(itemIndex, { start: offset, end: offset + 1 })
    }
  }

  const rects = Array.from(ranges.entries())
    .map(([itemIndex, range]) => {
      const length = Math.max(match.map.itemLengths[itemIndex] || 1, 1)
      return itemRect(
        items[itemIndex],
        viewport,
        styles,
        range.start / length,
        range.end / length
      )
    })
    .filter((rect): rect is CitationRect => Boolean(rect))
  return mergeLineRects(rects)
}

const pageScrollTop = (pageNum: number) => {
  let top = 0
  for (let index = 0; index < pageNum - 1; index += 1) {
    top += (pageHeights[index] || 800) + 10
  }
  return top
}

const showCitationHighlight = async (location: CitationLocation) => {
  if (citationHighlightTimer) clearTimeout(citationHighlightTimer)
  citationHighlight.value = location
  await nextTick()

  const container = containerRef.value
  const firstRect = location.rects[0]
  if (container && firstRect) {
    const target = pageScrollTop(location.page) + firstRect.top
      - container.clientHeight * 0.32
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    container.scrollTo({
      top: Math.max(0, target),
      behavior: reducedMotion ? 'auto' : 'smooth'
    })
  } else {
    await scrollToPage(location.page)
  }

  citationHighlightTimer = setTimeout(() => {
    citationHighlight.value = null
    citationHighlightTimer = null
  }, 8000)
}

const highlightCitation = async (
  preferredPage: number | null,
  text: string | string[]
): Promise<CitationLocation | null> => {
  const searchValues = (Array.isArray(text) ? text : [text])
    .map(value => String(value || '').trim())
    .filter(Boolean)
  if (!pdfDoc || searchValues.length === 0) return null

  const pageOrder: number[] = []
  if (preferredPage && preferredPage >= 1 && preferredPage <= numPages.value) {
    pageOrder.push(preferredPage)
  } else {
    for (let pageNum = 1; pageNum <= numPages.value; pageNum += 1) {
      pageOrder.push(pageNum)
    }
  }

  for (const pageNum of pageOrder) {
    try {
      const page = await pdfDoc.getPage(pageNum)
      const textContent = await page.getTextContent()
      const items = textContent.items || []
      const match = findTextMatch(items, searchValues)
      if (!match) continue
      const viewport = page.getViewport({ scale: scale.value })
      const rects = matchRects(items, viewport, textContent.styles || {}, match)
      if (!rects.length) continue

      const location: CitationLocation = {
        page: pageNum,
        rects,
        precise: true
      }
      await renderPage(pageNum - 1)
      await showCitationHighlight(location)
      currentPage.value = pageNum
      emit('page-change', pageNum)
      return location
    } catch (e) {
      console.error(`定位第 ${pageNum} 页引用失败:`, e)
    }
  }
  return null
}

const highlightBbox = async (
  pageNum: number,
  bbox: number[] | null,
  cellBboxes: number[][] = []
): Promise<CitationLocation | null> => {
  if (!pdfDoc || pageNum < 1 || pageNum > numPages.value) return null
  const sourceRects = cellBboxes.length ? cellBboxes : (bbox ? [bbox] : [])
  if (!sourceRects.length) return null
  try {
    const page = await pdfDoc.getPage(pageNum)
    const viewport = page.getViewport({ scale: scale.value })
    const rects = sourceRects
      .filter(rect => Array.isArray(rect) && rect.length === 4)
      .map(rect => ({
        left: Math.max(0, Number(rect[0]) * scale.value),
        top: Math.max(0, Number(rect[1]) * scale.value),
        width: Math.min(viewport.width, Math.max(2, (Number(rect[2]) - Number(rect[0])) * scale.value)),
        height: Math.min(viewport.height, Math.max(2, (Number(rect[3]) - Number(rect[1])) * scale.value))
      }))
    if (!rects.length) return null
    const location: CitationLocation = { page: pageNum, rects, precise: true }
    await renderPage(pageNum - 1)
    await showCitationHighlight(location)
    currentPage.value = pageNum
    emit('page-change', pageNum)
    return location
  } catch (e) {
    console.error(`按坐标定位第 ${pageNum} 页引用失败:`, e)
    return null
  }
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
  if (citationHighlightTimer) clearTimeout(citationHighlightTimer)
})

defineExpose({
  scrollToPage,
  searchText,
  highlightCitation,
  highlightBbox,
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
  background: var(--pa-reader-toolbar);
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
  background: var(--pa-reader-toolbar-control);
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
  background: var(--pa-reader-toolbar-control);
  border: none;
  border-radius: 4px;
  color: white;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
  min-width: 32px;
}

.toolbar-btn:focus-visible {
  outline: 2px solid oklch(0.88 0.08 70);
  outline-offset: 2px;
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
  scrollbar-width: auto;
  scrollbar-color: oklch(0.62 0.012 45) var(--pa-reader-toolbar);
}

.pdf-container::-webkit-scrollbar {
  width: 12px;
}

.pdf-container::-webkit-scrollbar-track {
  background: var(--pa-reader-toolbar);
}

.pdf-container::-webkit-scrollbar-thumb {
  min-height: 72px;
  border-radius: 6px;
  background: oklch(0.62 0.012 45);
}

.pdf-container::-webkit-scrollbar-thumb:hover {
  background: oklch(0.70 0.014 45);
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
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  background: white;
  contain: layout paint style;
  content-visibility: auto;
  contain-intrinsic-size: 600px 800px;
}

.citation-highlight-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 2;
}

.citation-highlight-rect {
  position: absolute;
  min-width: 3px;
  border-radius: 2px;
  background: oklch(0.84 0.16 82 / 0.48);
  box-shadow: inset 0 0 0 1px oklch(0.64 0.15 65 / 0.42);
  animation: citation-text-pulse 700ms cubic-bezier(0.25, 1, 0.5, 1);
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

@keyframes citation-text-pulse {
  0% { opacity: 0; transform: scaleY(0.72); }
  100% { opacity: 1; transform: scaleY(1); }
}

@media (prefers-reduced-motion: reduce) {
  .pdf-page-shell.citation-target { animation: none; }
  .citation-highlight-rect { animation: none; }
}

@media (pointer: coarse) {
  .toolbar-btn,
  .page-input {
    min-width: 44px;
    min-height: 44px;
  }
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
  background: var(--pa-reader-toolbar);
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

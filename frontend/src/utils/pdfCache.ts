const PDF_CACHE_NAME = 'paperai-pdf-v1'
const CACHE_PATH_PREFIX = '/__paperai_pdf_cache__/'

const cacheAvailable = () =>
  typeof window !== 'undefined'
  && window.isSecureContext
  && 'caches' in window

const cacheRequest = (paperId: string) =>
  new Request(`${CACHE_PATH_PREFIX}${encodeURIComponent(paperId)}`)

export const paperIdFromPdfUrl = (pdfUrl: string): string | null => {
  const match = pdfUrl.match(/\/api\/v1\/papers\/([^/?]+)\/pdf(?:[/?]|$)/)
  return match ? decodeURIComponent(match[1]) : null
}

export const readCachedPdf = async (paperId: string): Promise<ArrayBuffer | null> => {
  if (!cacheAvailable()) return null
  try {
    const cache = await caches.open(PDF_CACHE_NAME)
    const response = await cache.match(cacheRequest(paperId))
    return response ? await response.arrayBuffer() : null
  } catch (error) {
    console.warn('读取本地 PDF 缓存失败:', error)
    return null
  }
}

export const writeCachedPdf = async (paperId: string, data: Uint8Array) => {
  if (!cacheAvailable() || !data.byteLength) return
  try {
    const cache = await caches.open(PDF_CACHE_NAME)
    await cache.put(
      cacheRequest(paperId),
      new Response(data.slice(), {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Length': String(data.byteLength)
        }
      })
    )
  } catch (error) {
    // Cache quota or private browsing restrictions must never break reading.
    console.warn('保存本地 PDF 缓存失败:', error)
  }
}

export const removeCachedPdf = async (paperId: string) => {
  if (!cacheAvailable()) return
  try {
    const cache = await caches.open(PDF_CACHE_NAME)
    await cache.delete(cacheRequest(paperId))
  } catch (error) {
    console.warn('清理本地 PDF 缓存失败:', error)
  }
}

// Bump the cache namespace when the stored response representation changes.
// Keep the previous namespace readable so a valid PDF downloaded before a
// frontend deployment can be promoted instead of forcing another download.
export const PDF_CACHE_NAME = 'paperai-pdf-v2'
const LEGACY_PDF_CACHE_NAMES = ['paperai-pdf-v1']
const PDF_CACHE_NAMES = [PDF_CACHE_NAME, ...LEGACY_PDF_CACHE_NAMES]
const CACHE_PATH_PREFIX = '/__paperai_pdf_cache__/'

const cacheAvailable = () =>
  typeof window !== 'undefined'
  && 'caches' in window

export interface CachedPdf {
  data: ArrayBuffer
  cacheName: string
}

const cacheRequest = (paperId: string) =>
  new Request(new URL(
    `${CACHE_PATH_PREFIX}${encodeURIComponent(paperId)}`,
    window.location.origin,
  ))

const looksLikePdf = (data: ArrayBuffer) => {
  if (data.byteLength < 5) return false
  const header = new Uint8Array(data, 0, 5)
  return header[0] === 0x25 // %
    && header[1] === 0x50 // P
    && header[2] === 0x44 // D
    && header[3] === 0x46 // F
    && header[4] === 0x2d // -
}

export const paperIdFromPdfUrl = (pdfUrl: string): string | null => {
  const match = pdfUrl.match(/\/api\/v1\/papers\/([^/?]+)\/pdf(?:[/?]|$)/)
  return match ? decodeURIComponent(match[1]) : null
}

export const readCachedPdf = async (paperId: string): Promise<CachedPdf | null> => {
  if (!cacheAvailable()) return null
  for (const cacheName of PDF_CACHE_NAMES) {
    try {
      const cache = await caches.open(cacheName)
      const request = cacheRequest(paperId)
      const response = await cache.match(request)
      if (!response) continue
      const data = await response.arrayBuffer()
      if (!looksLikePdf(data)) {
        // A previously interrupted write must never be handed to PDF.js as a
        // document; remove it and let the caller fetch a fresh copy.
        await cache.delete(request)
        continue
      }
      return { data, cacheName }
    } catch (error) {
      // Cache Storage is unavailable in some insecure/private browsing
      // contexts. Try the next namespace and keep reading functional.
      console.warn(`读取本地 PDF 缓存失败（${cacheName}）:`, error)
    }
  }
  return null
}

export const writeCachedPdf = async (paperId: string, data: Uint8Array) => {
  if (!cacheAvailable() || !data.byteLength) return
  try {
    const cache = await caches.open(PDF_CACHE_NAME)
    await cache.put(
      cacheRequest(paperId),
      new Response(data.slice(), {
        headers: {
          'Content-Type': 'application/pdf'
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
  for (const cacheName of PDF_CACHE_NAMES) {
    try {
      const cache = await caches.open(cacheName)
      await cache.delete(cacheRequest(paperId))
    } catch (error) {
      console.warn(`清理本地 PDF 缓存失败（${cacheName}）:`, error)
    }
  }
}

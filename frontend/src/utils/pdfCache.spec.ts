import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  PDF_CACHE_NAME,
  paperIdFromPdfUrl,
  readCachedPdf,
  removeCachedPdf,
  writeCachedPdf,
} from './pdfCache'

const pdfBytes = new Uint8Array([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31, 0x2e, 0x37])

const createCache = (response?: Response) => ({
  match: vi.fn().mockResolvedValue(response),
  delete: vi.fn().mockResolvedValue(true),
  put: vi.fn().mockResolvedValue(undefined),
})

describe('pdf cache', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.stubGlobal('caches', { open: vi.fn() })
    Object.defineProperty(window, 'caches', {
      configurable: true,
      value: globalThis.caches,
    })
  })

  it('extracts the paper id from a stable PDF URL', () => {
    expect(paperIdFromPdfUrl('/api/v1/papers/paper%2F1/pdf?v=3')).toBe('paper/1')
    expect(paperIdFromPdfUrl('/api/v1/papers/paper-1/sections')).toBeNull()
  })

  it('reads a valid legacy cache entry so it can be promoted', async () => {
    const currentCache = createCache()
    const legacyCache = createCache(new Response(pdfBytes))
    vi.mocked(globalThis.caches.open).mockImplementation(async (name: string) => (
      name === PDF_CACHE_NAME ? currentCache : legacyCache
    ) as unknown as Cache)

    const cached = await readCachedPdf('paper-1')

    expect(cached?.cacheName).toBe('paperai-pdf-v1')
    expect(Array.from(new Uint8Array(cached!.data))).toEqual(Array.from(pdfBytes))
  })

  it('discards invalid bytes and tries the next cache namespace', async () => {
    const currentCache = createCache(new Response(new Uint8Array([1, 2, 3])))
    const legacyCache = createCache(new Response(pdfBytes))
    vi.mocked(globalThis.caches.open).mockImplementation(async (name: string) => (
      name === PDF_CACHE_NAME ? currentCache : legacyCache
    ) as unknown as Cache)

    const cached = await readCachedPdf('paper-1')

    expect(currentCache.delete).toHaveBeenCalledOnce()
    expect(cached?.cacheName).toBe('paperai-pdf-v1')
  })

  it('writes only the PDF representation without a hand-written length', async () => {
    const currentCache = createCache()
    vi.mocked(globalThis.caches.open).mockResolvedValue(currentCache as unknown as Cache)

    await writeCachedPdf('paper-1', pdfBytes)

    expect(vi.mocked(globalThis.caches.open)).toHaveBeenCalledWith(PDF_CACHE_NAME)
    const [, response] = currentCache.put.mock.calls[0]
    expect(response.headers.get('content-type')).toBe('application/pdf')
    expect(response.headers.get('content-length')).toBeNull()
    expect(Array.from(new Uint8Array(await response.arrayBuffer()))).toEqual(Array.from(pdfBytes))
  })

  it('removes both current and legacy entries on force reload', async () => {
    const currentCache = createCache()
    const legacyCache = createCache()
    vi.mocked(globalThis.caches.open).mockImplementation(async (name: string) => (
      name === PDF_CACHE_NAME ? currentCache : legacyCache
    ) as unknown as Cache)

    await removeCachedPdf('paper-1')

    expect(currentCache.delete).toHaveBeenCalledOnce()
    expect(legacyCache.delete).toHaveBeenCalledOnce()
  })
})

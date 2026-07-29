import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

const apiProxy = {
  '/api': {
    target: process.env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
    changeOrigin: true,
    configure: (proxy, _options) => {
      proxy.on('proxyRes', (proxyRes, req, _res) => {
        // Ensure binary content types are passed through correctly
        const contentType = proxyRes.headers['content-type'] || ''
        if (contentType.includes('application/pdf') || contentType.includes('octet-stream')) {
          proxyRes.headers['Access-Control-Allow-Origin'] = '*'
        }
      })
    }
  }
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src')
    }
  },
  server: {
    host: '0.0.0.0', 
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    watch: {
      usePolling: true
    },
    proxy: apiProxy
  },
  preview: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    allowedHosts: true,
    proxy: apiProxy
  }
})

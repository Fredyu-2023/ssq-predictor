import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 仅本机/局域网使用：开发时把 /api 代理到后端 8000 端口
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})

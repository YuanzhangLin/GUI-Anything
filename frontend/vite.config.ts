import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0', // 必须是 0.0.0.0 才能让容器外访问
    port: 5173,      // 容器内部端口保持不变
    strictPort: true, 
    watch: {
      usePolling: true
    }
  }
})
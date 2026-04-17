import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/cbcl/',
  build: {
    outDir: 'dist',
  },
  server: {
    proxy: {
      '/cbcl/api': {
        target: 'http://192.168.1.10:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/cbcl/, ''),
      },
    },
  },
})

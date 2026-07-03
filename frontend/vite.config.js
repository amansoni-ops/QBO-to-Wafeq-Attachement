import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev proxy → Flask backend (port 8000). In production, `vite build` output
// goes into Flask's static folder and is served same-origin, so proxy is dev-only.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/callback': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})

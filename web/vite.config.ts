import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Development: `npm run dev` proxies /api to the service (default localhost:8000).
// Production: `npm run build` writes web/dist, which the service serves at "/".
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.API_URL ?? 'http://localhost:8000', changeOrigin: true } },
  },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 900 },
  test: { environment: 'jsdom', globals: true, include: ['src/**/*.test.{ts,tsx}'] },
})

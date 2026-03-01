import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/gate/stream': {
        target: 'http://127.0.0.1:5000',
        changeOrigin: true,
        // Disable response buffering so SSE events flow through immediately
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
        },
      },
      '/gate': 'http://127.0.0.1:5000',
      '/parking': 'http://127.0.0.1:5000',
      '/admin/login': 'http://127.0.0.1:5000',
      '/admin/logout': 'http://127.0.0.1:5000',
      '/admin/gate-override': 'http://127.0.0.1:5000',
      '/admin/badges': 'http://127.0.0.1:5000',
      '/admin/cctv': 'http://127.0.0.1:5000',
      '/admin/events': 'http://127.0.0.1:5000',
      '/power': 'http://127.0.0.1:5000',
      '/status': 'http://127.0.0.1:5000',
      '/static': 'http://127.0.0.1:5000',
    },
  },
})

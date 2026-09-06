import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/evidence': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/data': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/samples': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/recordings-media': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/pwa': {
        target: 'http://localhost:5000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:5000',
        ws: true
      }
    }
  }
});

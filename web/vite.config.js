import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const api = process.env.HANDFONT_API || 'http://127.0.0.1:8788';
const proxyPaths = [
  '/history', '/library', '/api', '/files', '/download', '/bundle',
  '/template', '/prepare', '/confirm', '/preview', '/font', '/build',
];

export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === 'build' ? '/static/app/' : '/',
  server: {
    proxy: Object.fromEntries(proxyPaths.map((path) => [path, {
      target: api,
      bypass(req) {
        const pathname = (req.url || '').split('?')[0];
        if (pathname === '/download' || pathname.startsWith('/download/') || pathname.startsWith('/files/') || pathname.startsWith('/bundle/') || pathname.startsWith('/api/')) return;
        if ((req.headers.accept || '').includes('text/html')) return '/index.html';
      },
    }])),
  },
  build: {
    outDir: '../src/handfont/static/app',
    emptyOutDir: true,
  },
}));

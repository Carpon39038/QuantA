import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

function parsePort(rawValue: string | undefined, fallback: number): number {
  const parsed = Number.parseInt(rawValue ?? '', 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

const frontendHost = process.env.QUANTA_FRONTEND_HOST ?? '127.0.0.1';
const frontendPort = parsePort(process.env.QUANTA_FRONTEND_PORT, 4173);
const backendHost = process.env.QUANTA_BACKEND_HOST ?? '127.0.0.1';
const backendPort = parsePort(process.env.QUANTA_BACKEND_PORT, 8765);
const backendOrigin = `http://${backendHost}:${backendPort}`;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: frontendPort,
    host: frontendHost,
    strictPort: true,
    proxy: {
      '/api': {
        target: backendOrigin,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
});

import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import type { Plugin } from 'vite';
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
const frontendOrigin = `http://${frontendHost}:${frontendPort}`;

function frontendHealthPlugin(): Plugin {
  return {
    name: 'quanta-frontend-health',
    configureServer(server) {
      server.middlewares.use('/health', (req, res, next) => {
        if (req.method !== 'GET') {
          next();
          return;
        }

        const payload = JSON.stringify({
          status: 'ok',
          service: 'quanta-frontend',
          mode: server.config.mode,
          frontend_origin: frontendOrigin,
          backend_origin: backendOrigin,
        });

        res.statusCode = 200;
        res.setHeader('Content-Type', 'application/json; charset=utf-8');
        res.end(payload);
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), tailwindcss(), frontendHealthPlugin()],
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

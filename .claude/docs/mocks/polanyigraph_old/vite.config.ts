import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  root: path.resolve(__dirname, 'frontend'),
  server: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: 'all'
  }
});

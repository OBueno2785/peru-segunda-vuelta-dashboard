import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// En build (GitHub Pages) servimos bajo /peru-segunda-vuelta-dashboard/.
// En dev usamos '/' con proxy al backend local.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/peru-segunda-vuelta-dashboard/' : '/',
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8030',
    },
  },
}))

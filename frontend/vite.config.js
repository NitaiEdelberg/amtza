import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/health': 'http://localhost:8000',
      '/pair': 'http://localhost:8000',
      '/guess': 'http://localhost:8000',
      '/validate': 'http://localhost:8000',
      '/hint': 'http://localhost:8000',
    },
  },
})

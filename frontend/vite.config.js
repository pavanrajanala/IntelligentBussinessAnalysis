import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// During development the React app runs on :5173 and forwards every /api
// request to the FastAPI server on :8000, so no CORS setup is needed and the
// code can call plain "/api/..." paths (the same paths work in production).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})

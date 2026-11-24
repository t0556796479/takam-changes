import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development, calls to /api go to the FastAPI server, so the browser sees one origin.
const apiTarget = process.env.VITE_API_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': apiTarget } },
})

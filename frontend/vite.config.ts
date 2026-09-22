import { execSync } from "child_process"
import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Commit do build, para o rodapé de versão da tela de conferência. Netlify
// injeta COMMIT_REF no build; fora dele, o git local; sem nenhum, vazio (o
// rodapé diz "sem commit" em vez de inventar).
function commitDoBuild(): string {
  if (process.env.VITE_BUILD_COMMIT) return process.env.VITE_BUILD_COMMIT
  if (process.env.COMMIT_REF) return process.env.COMMIT_REF
  try {
    return execSync("git rev-parse HEAD", { stdio: ["ignore", "pipe", "ignore"] }).toString().trim()
  } catch {
    return ""
  }
}

export default defineConfig({
  plugins: [react()],
  define: {
    "import.meta.env.VITE_BUILD_COMMIT": JSON.stringify(commitDoBuild()),
  },
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      }
    }
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          query: ['@tanstack/react-query'],
          ui: ['framer-motion', 'lucide-react'],
        },
      },
    },
  },
})

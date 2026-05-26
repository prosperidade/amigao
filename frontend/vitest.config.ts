import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true,
    environment: "node",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    css: false,
    // PROMPT_9 — primeiros testes com jsdom (componentes). jsdom 27 puxa
    // `@asamuzakjp/css-color` (CJS) que require `@csstools/css-calc` (ESM),
    // o que Node 22.11 só aceita com flag experimental. A flag está nos
    // scripts npm de `test*` (Node binary direto), porque `execArgv` do
    // pool não cobre o load inicial do worker fork. Remover quando o
    // jsdom corrigir a dep CJS/ESM ou subirmos pra Node 22.12+ (que
    // ativou `require(esm)` por default).
    coverage: {
      provider: "v8",
      include: ["src/lib/**", "src/store/**", "src/utils/**"],
      exclude: ["src/test/**"],
    },
  },
})

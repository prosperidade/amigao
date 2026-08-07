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
    // Medido em 06/08, na `main` e neste ramo: a suíte falhava 4 testes por
    // rodada, em 3 de 3 rodadas, SEMPRE entre 5000 e 5300ms — o `testTimeout`
    // default de 5s. Os mesmos testes passam sozinhos (3 de 3), e o conjunto
    // que falha MUDA a cada rodada (AcaoCard, CredentialsTab, AlertaCard):
    // não é um teste ruim, é quem perde a disputa por CPU. `userEvent` dentro
    // do jsdom encadeia dezenas de eventos, e com os workers do pool
    // concorrendo cada evento custa milissegundos reais.
    //
    // 20s não afrouxa asserção nenhuma — só para de cronometrar a máquina
    // junto com o comportamento. Suíte que falha por sorteio não segura gate
    // nenhum, e este projeto exige gate com E2E do gesto humano.
    testTimeout: 20_000,
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

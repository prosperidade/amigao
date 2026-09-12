// Gate E2E da Frente J — o gesto humano na UI REAL contra a API REAL.
//
// Não roda no CI (exige a pilha inteira de pé: API + worker + Redis + MinIO +
// Postgres descartável + chave de LLM). Roda na máquina de quem fecha a
// frente, e o resultado (prints + payloads) é colado no relatório —
// `docs/trabalhos/fechamento_contrato.md`. Ver `tests/e2e/frente_j/README.md`.
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 10 * 60 * 1000,        // a extração real (LLM) leva minutos
  expect: { timeout: 30 * 1000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'e2e-report' }]],
  use: {
    baseURL: process.env.E2E_FRONTEND_URL ?? 'http://127.0.0.1:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    ...devices['Desktop Chrome'],
  },
  outputDir: 'e2e-results',
});

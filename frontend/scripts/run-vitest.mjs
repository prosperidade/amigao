#!/usr/bin/env node
/**
 * Runner cross-platform pro Vitest que injeta `--experimental-require-module`
 * no NODE_OPTIONS dos workers.
 *
 * Por quê? jsdom 27 (usado nos testes de componente) puxa `@asamuzakjp/css-color`
 * (CJS) que `require()` `@csstools/css-calc` (ESM). Em Node 22.11 isso falha
 * sem a flag. `package.json` script direto com `node --flag` não funciona porque
 * os workers do Vitest (Tinypool) são spawnados sem herdar a flag — só `NODE_OPTIONS`
 * (variável de ambiente) propaga.
 *
 * Esse script seta a env e re-exec o vitest CLI. Cross-platform porque usa
 * `process.env` em vez de `VAR=val cmd` (que não funciona no PowerShell).
 *
 * Remover quando o jsdom corrigir a dep CJS/ESM upstream, ou quando o projeto
 * subir pra Node 22.12+ (que ativou `require(esm)` por default).
 */

import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __filename = fileURLToPath(import.meta.url);
const frontendRoot = path.resolve(path.dirname(__filename), '..');
const vitestBin = path.join(frontendRoot, 'node_modules', 'vitest', 'vitest.mjs');

const args = process.argv.slice(2);

const env = {
  ...process.env,
  NODE_OPTIONS: [process.env.NODE_OPTIONS, '--experimental-require-module']
    .filter(Boolean)
    .join(' '),
};

const result = spawnSync(process.execPath, [vitestBin, ...args], {
  stdio: 'inherit',
  env,
  cwd: frontendRoot,
});

process.exit(result.status ?? 1);

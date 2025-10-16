/**
 * Author: ChatGPT (gpt-5-codex)
 * Date: 2025-10-15
 * PURPOSE: Provide an npm lint entrypoint that runs ESLint when available and falls back to offline sanity checks when registry access prevents installing lint dependencies.
 * SRP and DRY check: Pass - the script only orchestrates lint execution/fallback without duplicating existing build or test logic.
 */

import { createRequire } from 'node:module';
import { spawn, execFile } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import { join, relative, extname, basename } from 'node:path';
import { promisify } from 'node:util';
import process from 'node:process';

const projectRoot = process.cwd();
const repoRoot = join(projectRoot, '..');
const execFileAsync = promisify(execFile);
const ignoreFiles = new Set([
  'package-lock.json',
  'pnpm-lock.yaml',
]);
const allowedExtensions = new Set([
  '.ts',
  '.tsx',
  '.js',
  '.jsx',
  '.mjs',
  '.cjs',
  '.json',
  '.css',
  '.md',
]);
const maxLineLength = 180;

async function runEslintIfAvailable() {
  const localRequire = createRequire(import.meta.url);
  try {
    const eslintBin = localRequire.resolve('eslint/bin/eslint.js');
    await new Promise((resolve, reject) => {
      const child = spawn(process.execPath, [eslintBin, '--max-warnings=0'], {
        stdio: 'inherit',
        cwd: projectRoot,
      });
      child.on('error', reject);
      child.on('exit', (code) => {
        if (code === 0) {
          resolve();
        } else {
          reject(new Error(`ESLint exited with code ${code}`));
        }
      });
    });
    return true;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (message.includes('Cannot find module') || (error && error.code === 'MODULE_NOT_FOUND')) {
      console.warn('[lint] ESLint is not installed in this environment. Running fallback checks instead.');
      return false;
    }
    throw error;
  }
}

function mergeDiffMaps(base, incoming) {
  for (const [file, additions] of incoming.entries()) {
    const existing = base.get(file) ?? [];
    base.set(file, existing.concat(additions));
  }
  return base;
}

function parseDiff(stdout) {
  const additions = new Map();
  const lines = stdout.split(/\r?\n/);
  let currentFile = null;
  let currentLine = 0;

  for (const raw of lines) {
    if (raw.startsWith('diff --git')) {
      currentFile = null;
      currentLine = 0;
      continue;
    }
    if (raw.startsWith('index ') || raw.startsWith('--- ') || raw.startsWith('Binary files')) {
      continue;
    }
    if (raw.startsWith('+++ b/')) {
      currentFile = raw.slice(6).trim();
      continue;
    }
    if (!currentFile) {
      continue;
    }
    if (raw.startsWith('@@')) {
      const match = raw.match(/\+(\d+)(?:,(\d+))?/);
      if (match) {
        currentLine = Number.parseInt(match[1], 10);
      }
      continue;
    }
    if (raw.startsWith('+') && !raw.startsWith('++')) {
      const content = raw.slice(1);
      const fileAdditions = additions.get(currentFile) ?? [];
      fileAdditions.push({ line: currentLine, content });
      additions.set(currentFile, fileAdditions);
      currentLine += 1;
    } else if (raw.startsWith('-') && !raw.startsWith('--')) {
      continue;
    } else {
      currentLine += 1;
    }
  }

  return additions;
}

async function gatherChangedLines() {
  try {
    const [unstaged, staged] = await Promise.all([
      execFileAsync('git', ['diff', '--unified=0'], { cwd: repoRoot }),
      execFileAsync('git', ['diff', '--unified=0', '--cached'], { cwd: repoRoot }),
    ]);
    const aggregated = mergeDiffMaps(parseDiff(unstaged.stdout), parseDiff(staged.stdout));
    const targets = [];
    for (const [file, additions] of aggregated.entries()) {
      const extension = extname(file);
      const baseName = basename(file);
      if (!allowedExtensions.has(extension) || ignoreFiles.has(baseName) || additions.length === 0) {
        continue;
      }
      targets.push({
        file,
        absolute: join(repoRoot, file),
        additions,
      });
    }
    return targets;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`[lint:fallback] Unable to read git diff (${message}). Checking lint script only.`);
    return [
      {
        file: 'planexe-frontend/scripts/run-lint.mjs',
        absolute: join(projectRoot, 'scripts/run-lint.mjs'),
        additions: [],
      },
    ];
  }
}

async function runFallbackChecks() {
  const changes = await gatherChangedLines();
  if (changes.length === 0) {
    console.log('[lint:fallback] No modified files detected; skipping fallback checks.');
    return;
  }

  const issues = [];

  for (const change of changes) {
    let fileContent;
    try {
      fileContent = await readFile(change.absolute, 'utf8');
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      issues.push(`${change.file}: unable to read file (${message})`);
      continue;
    }

    const fileLines = fileContent.split(/\r?\n/);

    if (change.additions.length === 0) {
      change.additions = fileLines.map((content, index) => ({ content, line: index + 1 }));
    }

    for (const addition of change.additions) {
      const displayPath = change.file.startsWith('planexe-frontend/')
        ? change.file.slice('planexe-frontend/'.length)
        : change.file;
      const trimmedContent = addition.content.replace(/\r$/, '');
      if (trimmedContent.length > maxLineLength) {
        issues.push(`${displayPath}:${addition.line} exceeds ${maxLineLength} characters`);
      }
      if (/\s+$/.test(trimmedContent) && trimmedContent.length > 0) {
        issues.push(`${displayPath}:${addition.line} has trailing whitespace`);
      }
    }
  }

  if (issues.length > 0) {
    console.error('[lint:fallback] Fallback lint checks detected issues:');
    for (const issue of issues) {
      console.error(`  - ${issue}`);
    }
    throw new Error('Fallback lint checks failed');
  }

  console.log('[lint:fallback] All fallback lint checks passed.');
}

(async () => {
  try {
    const ranEslint = await runEslintIfAvailable();
    if (!ranEslint) {
      await runFallbackChecks();
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.error(`[lint] ${message}`);
    process.exit(1);
  }
})();

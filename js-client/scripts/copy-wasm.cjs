#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const DIST = path.join(ROOT, 'dist');

if (!fs.existsSync(DIST)) {
  fs.mkdirSync(DIST, { recursive: true });
}

const wasmSource = require.resolve('sql.js/dist/sql-wasm.wasm');
const wasmTarget = path.join(DIST, 'sql-wasm.wasm');
fs.copyFileSync(wasmSource, wasmTarget);

const filesToCopy = [
  ['README.md', 'README.md'],
  ['LICENSE', 'LICENSE']
];

for (const [source, target] of filesToCopy) {
  fs.copyFileSync(path.join(ROOT, source), path.join(DIST, target));
}

const packageJson = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
const distPackage = {
  name: packageJson.name,
  version: packageJson.version,
  type: 'module',
  main: './index.js',
  exports: {
    '.': './index.js',
    './wasm': './sql-wasm.wasm'
  },
  license: 'CC-BY-4.0',
  dependencies: packageJson.dependencies,
  description: 'Zero-dependency sql.js client for the Manabi Grammar SQLite bundle.',
  keywords: ['manabi', 'grammar', 'sqlite', 'sql.js'],
  repository: packageJson.repository,
  bugs: packageJson.bugs,
  homepage: packageJson.homepage
};

fs.writeFileSync(
  path.join(DIST, 'package.json'),
  JSON.stringify(distPackage, null, 2) + '\n',
  'utf8'
);

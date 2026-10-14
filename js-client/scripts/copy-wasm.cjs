#!/usr/bin/env node
const fs = require('node:fs');
const path = require('node:path');

const ROOT = fs.realpathSync(path.resolve(__dirname, '..'));
const DIST = path.join(ROOT, 'dist');
const runtimeDir = path.dirname(require.resolve('@sqlite.org/sqlite-wasm'));

function verifyTarget(target) {
    const existing = fs.existsSync(target) ? target : path.dirname(target);
    if (fs.realpathSync(existing) !== existing) throw new Error(`Unexpected symlink target: ${target}`);
}
verifyTarget(DIST);
fs.mkdirSync(DIST, { recursive: true });

// Preserve upstream modules unchanged, including the Node-specific entry.
for (const [source, target] of [
    ['index.mjs', 'sqlite3.mjs'],
    ['node.mjs', 'sqlite3-node.mjs'],
    ['sqlite3.wasm', 'sqlite3.wasm'],
    ['sqlite3-opfs-async-proxy.js', 'sqlite3-opfs-async-proxy.js'],
    ['sqlite3-worker1.mjs', 'sqlite3-worker1.mjs']
]) {
    const output = path.join(DIST, target);
    verifyTarget(output);
    fs.copyFileSync(path.join(runtimeDir, source), output);
}
for (const name of ['README.md', 'LICENSE']) {
    const target = path.join(DIST, name);
    verifyTarget(target);
    fs.copyFileSync(path.join(ROOT, name), target);
}
const packageJson = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
const distPackage = {
    name: packageJson.name,
    version: packageJson.version,
    type: 'module',
    main: './index.js',
    exports: { '.': './index.js', './wasm': './sqlite3.wasm' },
    license: packageJson.license,
    engines: { node: '>=22' },
    description: 'Read-only Manabi Grammar client using the official SQLite WASM engine.',
    keywords: ['manabi', 'grammar', 'sqlite', 'sqlite-wasm'],
    repository: packageJson.repository,
    bugs: packageJson.bugs,
    homepage: packageJson.homepage
};
const target = path.join(DIST, 'package.json');
verifyTarget(target);
fs.writeFileSync(target, JSON.stringify(distPackage, null, 2) + '\n');

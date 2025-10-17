import initSqlJs from 'sql.js/dist/sql-wasm.js';

let sqlModulePromise;

export function loadSqlJs() {
  if (!sqlModulePromise) {
    const override =
      typeof process !== 'undefined' && process.env && process.env.MANABI_SQLJS_WASM
        ? process.env.MANABI_SQLJS_WASM
        : null;
    sqlModulePromise = initSqlJs({
      locateFile: (file) => {
        if (override) {
          return override.endsWith('.wasm') ? override : `${override.replace(/\/$/, '')}/${file}`;
        }
        return new URL(`./${file}`, import.meta.url).href;
      }
    });
  }
  return sqlModulePromise;
}

export function __resetForTests() {
  sqlModulePromise = undefined;
}

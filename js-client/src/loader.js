let sqliteModulePromise;

export function loadSqlite() {
    if (!sqliteModulePromise) {
        const isNode = typeof process !== 'undefined' && Boolean(process.versions?.node);
        sqliteModulePromise = (isNode ? import('./sqlite3-node.mjs') : import('./sqlite3.mjs'))
            .then(({ default: initialize }) => initialize({
                locateFile: (file) => new URL(file, import.meta.url).href
            }))
            .catch((error) => {
                sqliteModulePromise = undefined;
                throw error;
            });
    }
    return sqliteModulePromise;
}

import { openReadonlySnapshot } from './snapshot.js';

// A prepared immutable JMdict index; no Yomitan importer or writable storage.
export class ManabiJmdictLexiconClient {
    #db;
    constructor(db) { this.#db = db; }

    static async fromUint8Array(bytes) {
        const db = await openReadonlySnapshot(bytes,
            'SELECT expression, reading, jmdictID, isSearchAlias FROM jmdict_terms LIMIT 0');
        try {
            const metadata = db.selectValue("SELECT value FROM lexicon_metadata WHERE key = 'schemaVersion'");
            if (metadata !== '1') throw new Error('Unsupported JMdict index schema');
            return new ManabiJmdictLexiconClient(db);
        } catch (error) { db.close(); throw error; }
    }

    metadata() {
        const db = this.#requireDb();
        return Object.fromEntries(db.selectArrays('SELECT key, value FROM lexicon_metadata'));
    }

    getCandidates(expression, reading) {
        if (typeof expression !== 'string' || (reading !== undefined && typeof reading !== 'string')) {
            throw new TypeError('JMdict expression/reading must be strings');
        }
        const stmt = this.#requireDb().prepare(`
            SELECT expression, reading, jmdictID, isSearchAlias FROM jmdict_terms
            WHERE expression = ? ${reading === undefined ? '' : "AND (reading = ? OR reading = '')"}
            ORDER BY jmdictID, reading, isSearchAlias LIMIT 513
        `);
        try {
            stmt.bind(reading === undefined ? [expression] : [expression, reading]);
            const candidates = [];
            while (stmt.step()) {
                const [expression, reading, jmdictID, isSearchAlias] = stmt.get([]);
                candidates.push({ expression, reading, jmdictID, isSearchAlias: Boolean(isSearchAlias) });
            }
            if (candidates.length > 512) throw new Error('JMdict candidate limit exceeded');
            return candidates;
        } finally { stmt.finalize(); }
    }

    #requireDb() {
        if (!this.#db) throw new Error('JMdict lexicon is closed');
        return this.#db;
    }

    close() { this.#db?.close(); this.#db = null; }
}

import { openReadonlySnapshot } from './snapshot.js';

// A prepared immutable JMdict index; no Yomitan importer or writable storage.
export class ManabiJmdictLexiconClient {
    #db;
    #hasCategories;
    constructor(db, hasCategories = false) { this.#db = db; this.#hasCategories = hasCategories; }

    static async fromUint8Array(bytes) {
        const db = await openReadonlySnapshot(bytes,
            'SELECT expression, reading, jmdictID, isSearchAlias FROM jmdict_terms LIMIT 0');
        try {
            const schema = db.selectValue("SELECT value FROM lexicon_metadata WHERE key = 'schemaVersion'");
            if (schema !== '1' && schema !== '2') throw new Error('Unsupported JMdict index schema');
            if (schema === '2') {
                const coverage = JSON.parse(db.selectValue("SELECT value FROM lexicon_metadata WHERE key = 'categoryCoverage'"));
                if (!Array.isArray(coverage) || !coverage.length || coverage.length > 64
                    || coverage.some((value, index) => typeof value !== 'string' || !/^[a-z][a-z0-9-]{0,31}$/.test(value)
                        || (index > 0 && coverage[index - 1] >= value))) throw new Error('Invalid JMdict category coverage');
                const types = db.selectArrays('SELECT categoryID, category FROM jmdict_category_types ORDER BY categoryID');
                if (types.length !== coverage.length || types.some(([id, category], index) => id !== index + 1 || category !== coverage[index])) {
                    throw new Error('JMdict category coverage mismatch');
                }
                if (db.selectValue(`SELECT 1 FROM jmdict_term_categories c
                    LEFT JOIN jmdict_category_types p ON p.categoryID=c.categoryID
                    WHERE typeof(c.expression)!='text' OR length(c.expression)=0
                        OR typeof(c.reading)!='text' OR length(c.reading)=0
                        OR typeof(c.jmdictID)!='integer' OR c.jmdictID<=0 OR c.jmdictID>2147483647
                        OR typeof(c.categoryID)!='integer' OR p.categoryID IS NULL
                        OR NOT EXISTS (SELECT 1 FROM jmdict_terms t WHERE t.expression=c.expression
                            AND t.reading=c.reading AND t.jmdictID=c.jmdictID AND t.isSearchAlias=0)
                    LIMIT 1`) !== undefined) throw new Error('Invalid JMdict exact category row');
            }
            return new ManabiJmdictLexiconClient(db, schema === '2');
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
            SELECT expression, reading, jmdictID, isSearchAlias ${this.#hasCategories ? `,
                (SELECT group_concat(category, ',') FROM (
                    SELECT p.category FROM jmdict_term_categories c
                    JOIN jmdict_category_types p USING(categoryID)
                    WHERE t.isSearchAlias=0 AND c.expression=t.expression
                        AND c.reading=t.reading AND c.jmdictID=t.jmdictID ORDER BY p.category))` : ''}
            FROM jmdict_terms t
            WHERE expression = ? ${reading === undefined ? '' : "AND (reading = ? OR reading = '')"}
            ORDER BY jmdictID, reading, isSearchAlias LIMIT 513
        `);
        try {
            stmt.bind(reading === undefined ? [expression] : [expression, reading]);
            const candidates = [];
            while (stmt.step()) {
                const [expression, reading, jmdictID, isSearchAlias, categories] = stmt.get([]);
                candidates.push({ expression, reading, jmdictID, isSearchAlias: Boolean(isSearchAlias),
                    ...(this.#hasCategories ? { applicableCategories: categories === null ? [] : categories.split(',') } : {}) });
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

import { openReadonlySnapshot } from './snapshot.js';
export { ManabiJmdictLexiconClient } from './lexicon.js';

const SELECT_ALL = `
    SELECT targetLanguage, headword, variant, data
    FROM grammar
    ORDER BY targetLanguage, headword, variant
`;

const SELECT_ONE = `
    SELECT targetLanguage, headword, variant, data
    FROM grammar
    WHERE targetLanguage = ? AND headword = ? AND variant = ?
    LIMIT 1
`;

function parseRow(row) {
    const [targetLanguage, headword, variant, data] = row;
    return { targetLanguage, headword, variant, data: JSON.parse(data) };
}

export class ManabiGrammarDbClient {
    #db;

    constructor(db) {
        this.#db = db;
    }

    static async fromUint8Array(bytes) {
        return new ManabiGrammarDbClient(await openReadonlySnapshot(bytes, `${SELECT_ALL} LIMIT 0`));
    }

    static async fromFile(filePath) {
        const { readFile } = await import('node:fs/promises');
        return this.fromUint8Array(await readFile(filePath));
    }

    #requireDb() {
        if (!this.#db) throw new Error('Grammar database is closed.');
        return this.#db;
    }

    all() {
        const stmt = this.#requireDb().prepare(SELECT_ALL);
        try {
            const rows = [];
            while (stmt.step()) rows.push(parseRow(stmt.get([])));
            return rows;
        } finally {
            stmt.finalize();
        }
    }

    get(targetLanguage, headword, variant = 1) {
        const stmt = this.#requireDb().prepare(SELECT_ONE);
        try {
            stmt.bind([targetLanguage, headword, variant]);
            return stmt.step() ? parseRow(stmt.get([])) : null;
        } finally {
            stmt.finalize();
        }
    }

    search(predicate) {
        if (typeof predicate !== 'function') throw new TypeError('predicate must be a function');
        return this.all().filter(predicate);
    }

    getByRuleID(ruleID) {
        if (typeof ruleID !== 'string') throw new TypeError('ruleID must be a string');
        const stmt = this.#requireDb().prepare(`
            SELECT targetLanguage, headword, variant, data FROM grammar
            WHERE json_extract(data, '$.ruleID') = ? LIMIT 2
        `);
        try {
            stmt.bind([ruleID]);
            if (!stmt.step()) return null;
            const entry = parseRow(stmt.get([]));
            if (stmt.step()) throw new Error('Ambiguous grammar rule identity');
            return entry;
        } finally { stmt.finalize(); }
    }

    close() {
        if (this.#db) {
            this.#db.close();
            this.#db = null;
        }
    }
}

export default ManabiGrammarDbClient;

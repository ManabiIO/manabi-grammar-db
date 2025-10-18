import { loadSqlJs } from './loader.js';

const SELECT_ALL = `
  SELECT target_language, headword, variant, data
  FROM grammar
  ORDER BY target_language, headword, variant
`;

const SELECT_ONE = `
  SELECT target_language, headword, variant, data
  FROM grammar
  WHERE target_language = ? AND headword = ? AND variant = ?
  LIMIT 1
`;

function parseRow(row) {
  const [target_language, headword, variant, data] = row;
  return {
    target_language,
    headword,
    variant,
    data: JSON.parse(data)
  };
}

export class ManabiGrammarDbClient {
  #db;
  #sql;

  constructor(db, sqlModule) {
    this.#db = db;
    this.#sql = sqlModule;
  }

  static async #instantiate(bytes) {
    const sql = await loadSqlJs();
    const database = new sql.Database(bytes);
    return new ManabiGrammarDbClient(database, sql);
  }

  static async fromUint8Array(bytes) {
    const view = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
    return ManabiGrammarDbClient.#instantiate(view);
  }

  static async fromFile(filePath) {
    const fs = await import('node:fs/promises');
    const buf = await fs.readFile(filePath);
    return ManabiGrammarDbClient.fromUint8Array(buf);
  }

  all() {
    const stmt = this.#db.prepare(SELECT_ALL);
    try {
      const rows = [];
      while (stmt.step()) {
        rows.push(parseRow(stmt.get()));
      }
      return rows;
    } finally {
      stmt.free();
    }
  }

  get(targetLanguage, headword, variant = 1) {
    const stmt = this.#db.prepare(SELECT_ONE);
    try {
      stmt.bind([targetLanguage, headword, variant]);
      if (stmt.step()) {
        return parseRow(stmt.get());
      }
      return null;
    } finally {
      stmt.free();
    }
  }

  search(predicate) {
    if (typeof predicate !== 'function') {
      throw new TypeError('predicate must be a function');
    }
    return this.all().filter((row) => predicate(row));
  }

  close() {
    if (this.#db) {
      this.#db.close();
      this.#db = null;
    }
  }
}

export default ManabiGrammarDbClient;

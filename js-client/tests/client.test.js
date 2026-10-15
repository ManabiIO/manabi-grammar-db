import { describe, expect, it, beforeAll, afterAll } from 'vitest';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { ManabiGrammarDbClient } from '../dist/index.js';
import { readFile } from 'node:fs/promises';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const DB_PATH = join(__dirname, '..', '..', 'dist', 'manabi-grammar.sqlite');

describe('ManabiGrammarDbClient', () => {
  let client;

  beforeAll(async () => {
    client = await ManabiGrammarDbClient.fromFile(DB_PATH);
  });

  afterAll(() => {
    client?.close();
  });

  it('returns all rows with parsed JSON', () => {
    const rows = client.all();
    expect(rows.length).toBeGreaterThan(0);
    const ga = rows.find((row) => row.headword === 'が');
    expect(ga).toBeDefined();
    expect(ga.variant).toBe(1);
    expect(ga.data).toHaveProperty('examples');
    expect(ga.data.alternativeForms).toContain('が');
    expect(ga.data.exampleSentences[0]).toMatchObject({
      sentence: '太郎が学校に行く。'
    });
    for (const field of ['pattern', 'compiledPattern', 'authoringPattern', 'analysisStatus', 'analysisSuppression', 'testData']) {
      expect(ga.data).not.toHaveProperty(field);
    }
    expect(ga.data.info.en.Guides[0]).toMatchObject({
      url: 'https://www.tofugu.com/japanese-grammar/particle-ga/',
      recommended: true
    });
    expect(ga.data.info.en.Meaning).toContain('subject');
  });

  it('gets a single headword', () => {
    const ha = client.get('ja', 'は', 1);
    expect(ha).not.toBeNull();
    expect(ha.headword).toBe('は');
    expect(ha.data.info.en.Guides[0].url).toContain('particle-wa');
  });

  it('looks up explanations by stable rule identity without interpreting SQL input', () => {
    const entry = client.getByRuleID('grammar.ja.ga.subject');
    expect(entry.headword).toBe('が');
    expect(entry.data.info.en.Meaning).toContain('subject');
    expect(client.getByRuleID('grammar.ja.missing')).toBeNull();
    expect(client.getByRuleID("grammar.ja.ga.subject' OR 1=1 --")).toBeNull();
  });

  it('search filters results', () => {
    const onlyGa = client.search((row) => row.headword === 'が');
    expect(onlyGa).toHaveLength(1);
    expect(onlyGa[0].data.info.en.Related).toHaveProperty('は');
  });

  it('returns null when headword missing', () => {
    const missing = client.get('ja', '不存在', 1);
    expect(missing).toBeNull();
  });
});


describe('official SQLite WASM database lifecycle', () => {
    it('handles a byte view with a nonzero offset without modifying the source', async () => {
        const bytes = await readFile(DB_PATH);
        const padded = new Uint8Array(bytes.length + 32);
        padded.set(bytes, 16);
        const view = padded.subarray(16, 16 + bytes.length);
        const snapshot = view.slice();
        const db = await ManabiGrammarDbClient.fromUint8Array(view);
        try {
            expect(db.get('ja', 'が', 1)?.headword).toBe('が');
            expect(view).toEqual(snapshot);
            expect(db.get('ja', "が' OR 1=1 --", 1)).toBeNull();
            expect(db.get('ja', 'が', 99)).toBeNull();
        } finally {
            db.close();
        }
    });

    it('keeps separate connections independent and closes idempotently', async () => {
        const bytes = await readFile(DB_PATH);
        const first = await ManabiGrammarDbClient.fromUint8Array(bytes);
        const second = await ManabiGrammarDbClient.fromUint8Array(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
        try {
            first.close();
            first.close();
            expect(() => first.all()).toThrow('closed');
            expect(second.get('ja', 'は')?.headword).toBe('は');
        } finally {
            first.close();
            second.close();
        }
    });

    it('rejects invalid inputs and WAL snapshots rather than silently losing transactions', async () => {
        const baseline = await ManabiGrammarDbClient.fromFile(DB_PATH);
        const expected = baseline.all();
        baseline.close();
        await expect(ManabiGrammarDbClient.fromUint8Array(new Uint8Array(100))).rejects.toThrow('header');
        await expect(ManabiGrammarDbClient.fromUint8Array('not bytes')).rejects.toThrow('Uint8Array');
        const wal = new Uint8Array(await readFile(DB_PATH));
        wal[18] = wal[19] = 2;
        await expect(ManabiGrammarDbClient.fromUint8Array(wal)).rejects.toThrow('WAL');
        const truncated = new Uint8Array(await readFile(DB_PATH)).subarray(0, 100);
        await expect(ManabiGrammarDbClient.fromUint8Array(truncated)).rejects.toThrow();
        const valid = await ManabiGrammarDbClient.fromFile(DB_PATH);
        expect(valid.all()).toEqual(expected);
        valid.close();
    });
});

import { describe, expect, it, beforeAll, afterAll } from 'vitest';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { ManabiGrammarDbClient } from '../src/client.js';
import { __resetForTests } from '../src/loader.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

process.env.MANABI_SQLJS_WASM = join(__dirname, '..', 'dist', 'sql-wasm.wasm');
const DB_PATH = join(__dirname, '..', '..', 'dist', 'manabi-grammar.sqlite');

describe('ManabiGrammarDbClient', () => {
  let client;

  beforeAll(async () => {
    client = await ManabiGrammarDbClient.fromFile(DB_PATH);
  });

  afterAll(() => {
    client?.close();
    __resetForTests();
  });

  it('returns all rows with parsed JSON', () => {
    const rows = client.all();
    expect(rows.length).toBeGreaterThan(0);
    const ga = rows.find((row) => row.headword === 'が');
    expect(ga).toBeDefined();
    expect(ga.variant).toBe(1);
    expect(ga.data).toHaveProperty('examples');
    expect(ga.data.alternativeForms).toContain('ガ');
    expect(ga.data.exampleSentences[0]).toMatchObject({
      sentence: '太郎が学校に行く。'
    });
    expect(ga.data.testData.nonMatchingSentences).toContain('太郎は学校に行く。');
    expect(ga.data.info.en.Guides[0]).toMatchObject({
      url: 'https://example.com/ga-guide',
      recommended: true
    });
    expect(ga.data.info.en.Meaning).toContain('subject');
  });

  it('gets a single headword', () => {
    const ha = client.get('ja', 'は', 1);
    expect(ha).not.toBeNull();
    expect(ha.headword).toBe('は');
    expect(ha.data.info.en['Q&A'][0].url).toContain('stackexchange-ha');
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

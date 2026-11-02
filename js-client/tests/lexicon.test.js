import { expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { ManabiJmdictLexiconClient } from '../dist/index.js';

// Real SQLite bytes exercise exact joins and deserialize admission together.
// Fixtures stay in memory; imported dictionary content is not committed.
function snapshot({ schema = '2', mutation = '' } = {}) {
    return execFileSync('python3', ['-c', `
import sqlite3,sys
db=sqlite3.connect(':memory:')
db.executescript('''
CREATE TABLE lexicon_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE jmdict_terms(expression TEXT,reading TEXT,jmdictID INTEGER,isSearchAlias INTEGER,
 PRIMARY KEY(expression,reading,jmdictID,isSearchAlias)) WITHOUT ROWID;
INSERT INTO jmdict_terms VALUES ('甲','こう',1,0),('甲','こう',1,1),('甲','かぶと',1,0),
 ('乙','おつ',1,0),('甲','こう',2,0),('別名','',1,1);
''')
db.execute('INSERT INTO lexicon_metadata VALUES (?,?)',('schemaVersion',sys.argv[1]))
if sys.argv[1]=='2':
 db.executescript('''
 INSERT INTO lexicon_metadata VALUES ('categoryCoverage','["adj-i","n"]');
 CREATE TABLE jmdict_category_types(categoryID INTEGER PRIMARY KEY,category TEXT UNIQUE);
 INSERT INTO jmdict_category_types VALUES (1,'adj-i'),(2,'n');
 CREATE TABLE jmdict_term_categories(expression TEXT,reading TEXT,jmdictID INTEGER,categoryID INTEGER,
  PRIMARY KEY(expression,reading,jmdictID,categoryID)) WITHOUT ROWID;
 INSERT INTO jmdict_term_categories VALUES ('甲','こう',1,1),('甲','こう',1,2),('乙','おつ',1,2);
 ''')
db.executescript(sys.argv[2])
sys.stdout.buffer.write(db.serialize())
`, schema, mutation]);
}

it('keeps categories on the exact spelling, reading and ID, never aliases', async () => {
    const client = await ManabiJmdictLexiconClient.fromUint8Array(snapshot());
    try {
        expect(client.getCandidates('甲', 'こう')).toEqual([
            { expression: '甲', reading: 'こう', jmdictID: 1, isSearchAlias: false, applicableCategories: ['adj-i', 'n'] },
            { expression: '甲', reading: 'こう', jmdictID: 1, isSearchAlias: true, applicableCategories: [] },
            { expression: '甲', reading: 'こう', jmdictID: 2, isSearchAlias: false, applicableCategories: [] },
        ]);
        expect(client.getCandidates('甲', 'かぶと')[0].applicableCategories).toEqual([]);
        expect(client.getCandidates('乙')[0].applicableCategories).toEqual(['n']);
        expect(client.getCandidates('別名', 'べつめい')[0].applicableCategories).toEqual([]);
        const first = client.getCandidates('甲', 'こう');
        first[0].applicableCategories.push('fake');
        expect(client.getCandidates('甲', 'こう')[0].applicableCategories).toEqual(['adj-i', 'n']);
        expect(client.getCandidates("甲' OR 1=1 --")).toEqual([]);
    } finally { client.close(); }
});

it('retains legacy schema without claiming category coverage', async () => {
    const client = await ManabiJmdictLexiconClient.fromUint8Array(snapshot({ schema: '1' }));
    try {
        expect(client.metadata()).not.toHaveProperty('categoryCoverage');
        expect(client.getCandidates('甲')[0]).not.toHaveProperty('applicableCategories');
    } finally { client.close(); }
});

it.each([
    `UPDATE lexicon_metadata SET value='["adj-i","adj-i"]' WHERE key='categoryCoverage';`,
    `UPDATE lexicon_metadata SET value='["n","adj-i"]' WHERE key='categoryCoverage';`,
    `UPDATE lexicon_metadata SET value='["adj-i"]' WHERE key='categoryCoverage';`,
    `DELETE FROM lexicon_metadata WHERE key='categoryCoverage';`,
    `UPDATE jmdict_category_types SET categoryID=3 WHERE categoryID=2;`,
    `UPDATE jmdict_term_categories SET categoryID=999 WHERE expression='乙';`,
    `INSERT INTO jmdict_term_categories VALUES ('別名','べつめい',1,1);`,
    `DELETE FROM jmdict_terms WHERE expression='甲' AND isSearchAlias=0;`,
])('rejects corrupt or unsupported category evidence: %s', async mutation => {
    await expect(ManabiJmdictLexiconClient.fromUint8Array(snapshot({ mutation }))).rejects.toThrow();
});

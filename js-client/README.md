# manabi-grammar-db-client

Read-only client for the Manabi Grammar SQLite bundle using the [official SQLite WASM engine](https://github.com/sqlite/sqlite-wasm), pinned to `@sqlite.org/sqlite-wasm@3.53.4-build2` (SQLite 3.53.4).

## Install

```bash
npm install manabi-grammar-db-client
# or
bun add manabi-grammar-db-client
```

## Usage

```js
import { ManabiGrammarDbClient } from 'manabi-grammar-db-client';

const client = await ManabiGrammarDbClient.fromFile('manabi-grammar.sqlite');
const allRows = client.all();
const ga = client.get('ja', 'が');

const guides = ga.data.info.en.Guides;
console.log(guides[0].name);

client.close();
```

If you already have the SQLite file loaded as a `Uint8Array`, call `ManabiGrammarDbClient.fromUint8Array(bytes)` instead of `fromFile`.

## API

- `static async fromFile(path: string)` – load from a SQLite file on disk in Node 22+ or Bun.
- `static async fromUint8Array(bytes: Uint8Array | ArrayBuffer)` – load from bytes in memory.
- `all(): Array<Row>` – return every grammar row. `Row` includes `targetLanguage`, `headword`, `variant`, and parsed JSON `data`.
- `get(targetLanguage: string, headword: string, variant = 1): Row | null` – fetch a single row.
- `getByRuleID(ruleID: string): Row | null` – resolve a grammar match's explanation by stable identity. Uses a bound indexed query; rejects ambiguous IDs in older catalogs. Use the same catalog snapshot as the matcher and verify `data.ruleVersion`.
- `search(predicate: (row) => boolean): Array<Row>` – filter rows using a callback.
- `close(): void` – dispose of the connection and its WASM database buffer; repeated calls are safe. Queries after close throw.

## Runtime and distribution

`ManabiJmdictLexiconClient` opens the prepared, definition-free JMdict SQLite
index using the same official read-only snapshot backend. Its separate schema
contains expression/reading pairs, positive canonical JMdict IDs and alias flags.
Use `getCandidates(expression, reading?)` for all alternatives, `metadata()` for
source provenance, and `close()` to release it. Queries bind inputs and fail if
more than 512 candidates would be returned. Search aliases with no reading are
eligible for a reading-filtered lookup and retain their empty reading plus
`isSearchAlias`. This class does not import Yomitan ZIPs or manage downloads.

Schema 2 additionally declares `categoryCoverage` in its metadata and returns
`applicableCategories` on each candidate. Categories belong to the exact spelling,
reading and entry ID; aliases always return an empty category array. An empty
array means this projection contains no applicable category for that candidate.
Schema 1 remains readable and omits this field, indicating unavailable category
evidence. Consumers that require categories must check declared coverage before
interpreting an empty lookup. Category membership does not select a contextual sense.

The self-contained `dist/` bundle selects `sqlite3-node.mjs` in Node/Bun and `sqlite3.mjs` in browsers. Keep those modules and `sqlite3.wasm` beside `index.js`; serve `.wasm` as `application/wasm`. The upstream runtime modules are copied unchanged, including their license notices. Browser module workers can fetch the database and pass its bytes to `fromUint8Array` without COOP/COEP headers:

```js
const response = await fetch('/manabi-grammar.sqlite');
if (!response.ok) throw new Error(`Database request failed: ${response.status}`);
const client = await ManabiGrammarDbClient.fromUint8Array(await response.arrayBuffer());
try {
    console.log(client.get('ja', 'が', 1));
} finally {
    client.close();
}
```

Connections use SQLite OO1 and `sqlite3_deserialize` with `SQLITE_DESERIALIZE_READONLY`, plus `PRAGMA query_only=ON`. Input bytes are copied without modifying the source. The generated database uses DELETE journal mode. WAL-mode files are rejected: deserialize does not support WAL snapshots, and changing a header could discard transactions.

No persistent VFS is installed. For future editable/offline dictionary storage, evaluate the official [OPFS SAH Pool VFS](https://sqlite.org/wasm/doc/trunk/persistence.md#sahpool), which avoids cross-origin isolation headers but requires coordination for exclusive access across tabs.

Build the client before testing: `mise run build-db` from the database repository builds the distribution, generates the snapshot, and runs client tests. `mise run client-build` only rebuilds the client.

Public grammar SQLite snapshots contain explanation content and reference bindings only. Matching definitions are a separate private build input. The generic read-only client does not install or execute them.

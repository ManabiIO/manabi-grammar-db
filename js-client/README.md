# manabi-grammar-db-client

Client utility for reading the Manabi Grammar SQLite bundle using [`sql.js`](https://github.com/sql-js/sql.js).

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

- `static async fromFile(path: string)` – load from a SQLite file on disk.
- `static async fromUint8Array(bytes: Uint8Array | ArrayBuffer)` – load from bytes in memory.
- `all(): Array<Row>` – return every grammar row. `Row` includes `target_language`, `headword`, and parsed JSON `data`.
- `get(targetLanguage: string, headword: string): Row | null` – fetch a single row.
- `search(predicate: (row) => boolean): Array<Row>` – filter rows using a callback.
- `close(): void` – dispose of the underlying database.

When bundling for the browser, ensure `sql-wasm.wasm` is served alongside the ESM bundle. The client resolves the wasm path relative to the module URL.

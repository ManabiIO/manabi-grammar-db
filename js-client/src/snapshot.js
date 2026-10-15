import { loadSqlite } from './loader.js';

export async function openReadonlySnapshot(bytes, validationSQL) {
    const borrowed = bytes instanceof Uint8Array ? bytes
        : bytes instanceof ArrayBuffer ? new Uint8Array(bytes) : null;
    if (!borrowed) throw new TypeError('Expected a Uint8Array or ArrayBuffer.');
    if (borrowed.byteLength > 0x7fffffff) throw new RangeError('Database exceeds the supported WASM buffer size.');
    // Own the exact view before validation or the first await. Callers may
    // mutate/transfer their buffer, and a WASM-backed view may detach on growth.
    // Construct a plain array: Buffer.slice() would retain borrowed storage.
    const view = new Uint8Array(borrowed);
    if (view.byteLength < 100 || new TextDecoder().decode(view.subarray(0, 16)) !== 'SQLite format 3\0') {
        throw new Error('Invalid SQLite database header.');
    }
    if (view[18] === 2 || view[19] === 2) {
        throw new Error('WAL-mode snapshots cannot be deserialized. Rebuild the database with mise run db-build.');
    }
    if (view.byteLength > 0x7fffffff) throw new RangeError('Database exceeds the supported WASM buffer size.');

    const sqlite3 = await loadSqlite();
    const { capi, wasm } = sqlite3;
    const db = new sqlite3.oo1.DB(':memory:', 'c');
    const pointer = capi.sqlite3_malloc(view.byteLength);
    if (!pointer) {
        db.close();
        throw new Error('Unable to allocate the SQLite database buffer.');
    }
    // The client owns this fixed buffer; SQLite only reads it. Do not pass
    // FREEONCLOSE/RESIZEABLE, which would transfer buffer ownership to SQLite.
    db.onclose = { after: () => capi.sqlite3_free(pointer) };
    try {
        wasm.heap8u().set(view, pointer);
        db.checkRc(capi.sqlite3_deserialize(
            db.pointer, 'main', pointer, view.byteLength, view.byteLength,
            capi.SQLITE_DESERIALIZE_READONLY
        ));
        db.exec('PRAGMA query_only=ON');
        // Validate the database/schema before returning a usable client.
        db.exec(validationSQL);
        return db;
    } catch (error) {
        db.close();
        throw error;
    }
}

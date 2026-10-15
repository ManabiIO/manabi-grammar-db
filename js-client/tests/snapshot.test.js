import { expect, it, vi } from 'vitest';

const bootstrap = vi.hoisted(() => ({ load: null }));
vi.mock('../src/loader.js', () => ({ loadSqlite: () => bootstrap.load() }));
import { openReadonlySnapshot } from '../src/snapshot.js';

it.each(['array', 'buffer', 'arraybuffer', 'transfer', 'wasm-growth'])('owns snapshot before asynchronous initialization: %s', async kind => {
    const original = new Uint8Array(128);
    original.set(new TextEncoder().encode('SQLite format 3\0'));
    original[18] = original[19] = 1;
    let input, memory;
    if (kind === 'buffer') input = Buffer.from(original);
    else if (kind === 'arraybuffer') input = original.slice().buffer;
    else if (kind === 'wasm-growth') {
        memory = new WebAssembly.Memory({ initial: 1 });
        input = new Uint8Array(memory.buffer, 16, original.length);
        input.set(original);
    } else {
        const padded = new Uint8Array(160);
        padded.set(original, 16);
        input = padded.subarray(16, 144);
    }
    let resume;
    const heap = new Uint8Array(1024);
    const free = vi.fn();
    bootstrap.load = () => new Promise(resolve => { resume = resolve; });
    const pending = openReadonlySnapshot(input, 'SELECT 1');
    if (kind === 'transfer') structuredClone(input.buffer, { transfer: [input.buffer] });
    else if (kind === 'wasm-growth') memory.grow(1);
    else new Uint8Array(input.buffer ?? input, input.byteOffset ?? 0, input.byteLength).fill(0);
    class DB {
        pointer = 1;
        checkRc(code) { expect(code).toBe(0); }
        exec() {}
        close() { this.onclose.after(); }
    }
    resume({ oo1: { DB }, wasm: { heap8u: () => heap }, capi: {
        sqlite3_malloc: () => 64, sqlite3_free: free, SQLITE_DESERIALIZE_READONLY: 4,
        sqlite3_deserialize: (_db, _schema, pointer, length, capacity, flags) => {
            expect(heap.slice(pointer, pointer + length)).toEqual(original);
            expect(capacity).toBe(original.length);
            expect(flags).toBe(4);
            return 0;
        }
    } });
    const db = await pending;
    db.close();
    expect(free).toHaveBeenCalledExactlyOnceWith(64);
});

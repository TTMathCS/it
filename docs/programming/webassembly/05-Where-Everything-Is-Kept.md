# 5. Where everything is kept

*Four different things end up on your computer when a page runs PostgreSQL: the downloaded files, the compiled
machine code, the running database, and (only if the page asks for it) a saved copy of the database. Each lives in a
different place, lasts a different time, and is cleared a different way. All the sizes below were measured in
Chromium 153.*

!!! abstract "In this chapter"
    - the HTTP cache: the 16 MB of files, and when they are downloaded again
    - the code cache: the compiled PostgreSQL
    - the tab's memory: where the database lives by default, and why a reload empties it
    - IndexedDB and OPFS: the two places a page can save the database
    - how to see and clear each one in DevTools

## 5.1 The four places at a glance

| What | Where | How long it stays | Measured |
| --- | --- | --- | --- |
| the downloaded files (`.js`, `.wasm`, `.data`) | the browser's **HTTP cache**, on disk | until the cache needs the room or you clear it; re-checked with the server when the server's "fresh for" time runs out | 16 MB |
| PostgreSQL compiled to your CPU's code | the browser's **code cache** (Chrome) | like the HTTP cache | 7.9 MB |
| the running database | the tab's **memory** (the module's linear memory) | until the tab reloads or closes | about 190 MB of memory per database |
| a saved database (`idb://...`) | **IndexedDB**, on disk | until the site or you delete it | 13.3 MB for one tiny table |
| a saved database (`opfs-ahp://...`) | the **Origin Private File System**, on disk | until the site or you delete it | 40 MB for one tiny table |

Everything in the last four rows belongs to **one origin** (scheme, host and port, for example
`https://it.akadian.ca`). Another site cannot read it, and the files never leave your computer.

## 5.2 The downloaded files: the HTTP cache

The `.js`, `.wasm` and `.data` files are ordinary web downloads and go into the same cache as pictures and style
sheets. How long the browser may reuse them without asking is set by the server. GitHub Pages, which serves
it.akadian.ca, sends (checked on 12 November 2026):

```text
cache-control: max-age=600
etag: "6af60513-4c68"
```

So for 10 minutes the browser uses its copy without asking. After that it asks "has this changed?" by sending the
ETag back (`If-None-Match`), and the server answers `304 Not Modified`, a few hundred bytes, instead of the file.

Tested with a small server that answers the same way, loading a PGlite page three times:

| Load | Normal browser profile | Private-style profile (kept in memory only) |
| --- | --- | --- |
| 1st | all 12 files downloaded (16 MB) | all 12 files downloaded |
| 2nd, within the fresh time | **no requests at all** | `pglite.wasm` (9 MB) downloaded **again**; the rest from cache |
| 3rd, after the fresh time | 12 small `304` answers, nothing downloaded | `pglite.wasm` downloaded again; the rest `304` |

The private-style profile is what a private (incognito) window uses: its cache lives in memory, and in this test it
did not keep the 9 MB file. In a normal window the files are downloaded once and then reused.

## 5.3 The compiled code: the code cache

Compiling 9 MB of WebAssembly takes time, so Chrome also keeps the **result**, the x86-64 or ARM machine code, in a
separate code cache next to the HTTP cache. After these tests the Chromium profile held 7.9 MB in its
`Code Cache/wasm` folder. Other browsers have similar caches; their details were not checked here.

## 5.4 The running database: the tab's memory

`new PGlite()` with no address keeps the database in Emscripten's **in-memory file system**, inside the module's
linear memory, like a `tmpfs`. PostgreSQL thinks it is writing to `/pglite/data` (its `PGDATA`); the bytes go into an
`ArrayBuffer`.

Measured: one PGlite instance had **197,722,112 bytes** of linear memory after starting, and the same after loading
the course's sample database. That memory is freed when the tab closes or reloads, and so is the database:

```js
// page.html: create a table if needed, add a row, count the rows
await db.exec(`CREATE TABLE IF NOT EXISTS visits (id serial PRIMARY KEY, at timestamptz DEFAULT now());
               INSERT INTO visits DEFAULT VALUES;`);
```

| Mode | Count on 1st load | Count after reload |
| --- | --- | --- |
| `new PGlite()` (memory) | 1 | **1**: the table was gone, created again |
| `new PGlite('idb://playground')` | 1 | **2**: the row from the first visit was still there |

For a learning playground, memory is the right choice: every visitor, every reload, starts from the same clean data,
and nothing is left behind.

## 5.5 Saving the database: IndexedDB

**IndexedDB** is a database built into every browser for pages to store data in, keyed by origin. PGlite uses it when
the address starts with `idb://`:

```js
const db = new PGlite('idb://playground');
```

PGlite still runs PostgreSQL on the in-memory file system, and copies the database files to IndexedDB after
queries, and back from IndexedDB when the page starts again. In the test, the IndexedDB database was named
`/pglite/playground` and the origin's storage use was **13.3 MB** after one tiny table: an empty PostgreSQL cluster
is mostly system catalogs. On the second visit the database started in 1.05 s instead of about 2 s, because
`initdb` did not run again.

## 5.6 Saving the database: OPFS

The **Origin Private File System** is a newer browser feature: a private folder tree per origin, with fast,
synchronous file access, but only from a Web Worker (a background thread of the page). PGlite uses it with the
`opfs-ahp://` prefix, and only inside a worker:

```js
// worker.js, started with new Worker('worker.js', { type: 'module' })
import { PGlite } from './pglite/index.js';
const db = await PGlite.create('opfs-ahp://playground');
```

In the test the worker's database became an OPFS folder `playground/` holding a `state.txt` file (about 110 KB) and a
`data/` folder, **40 MB** in all, and the row count went from 1 to 2 across two loads, as with IndexedDB. Which of
the two is faster was not measured here; IndexedDB is simpler, because it also works without a worker.

## 5.7 Where the folders are on disk

Chromium keeps each kind of storage in its own folder inside the browser profile. Measured on Linux after these
tests (profile folder `Default/`):

| Folder | Holds | Measured |
| --- | --- | --- |
| `Default/Cache/Cache_Data/` | the HTTP cache | 16 MB |
| `Default/Code Cache/wasm/` | compiled WebAssembly | 7.9 MB |
| `Default/IndexedDB/http_127.0.0.1_8765.indexeddb.leveldb/` and `.blob/` | IndexedDB, one folder pair per origin | 8.0 MB + 4.9 MB |
| `Default/File System/` | OPFS | 39 MB |

On a Mac, Google Chrome uses the same folder names under `~/Library/Application Support/Google/Chrome/Default/`
and `~/Library/Caches/Google/Chrome/Default/` (not checked on a Mac for these pages). The files are the browser's own
formats (LevelDB for IndexedDB, for example), so DevTools is the way to look at them, not the folders.

## 5.8 Seeing and clearing them in DevTools

Open DevTools with **⌥⌘I** on a Mac or **F12** elsewhere.

| To | Do this |
| --- | --- |
| see which files came from the cache | **Network** panel, reload: the Size column says `(disk cache)` or `(memory cache)` instead of a size |
| download everything again | **Network** panel, tick **Disable cache**, reload |
| see a saved database | **Application** panel, **Storage**, **IndexedDB**: `/pglite/playground` |
| see how much a site stores | **Application** panel, **Storage**: the usage chart and quota |
| delete everything the site stored | **Application** panel, **Storage**, **Clear site data** |
| see a tab's memory | Chrome's own **Task Manager** (Window menu, Task Manager) |

The same from the **Console**, tested in Chromium 153 (paste one line at a time; `await` works at the top of the
console):

```js
await navigator.storage.estimate()            // { quota, usage, usageDetails: { indexedDB, fileSystem } }
await indexedDB.databases()                   // [ { name: '/pglite/playground', version: 21 } ]
indexedDB.deleteDatabase('/pglite/playground')                                // delete the saved database
for await (const [name, h] of (await navigator.storage.getDirectory()).entries()) console.log(name, h.kind)   // list OPFS
await (await navigator.storage.getDirectory()).removeEntry('playground', { recursive: true })                // delete an OPFS folder
```

## 5.9 Saved does not mean safe forever

A browser may delete a site's saved data when the disk is short of space, unless the page has asked for, and been
granted, persistent storage (`navigator.storage.persist()`; in the test `navigator.storage.persisted()` was
`false`). Safari also deletes script-written storage for sites you have not visited for a while. Private windows
delete everything when they close. So anything that matters should be exported: PGlite's `dumpDataDir()` gives a
`.tar.gz` file of the whole database ([chapter 7](07-Build-Your-Own-Playground.md#73-a-prebuilt-snapshot-for-large-data)), and
plain SQL text can be copied out of any playground.

Next: [6. Is it safe?](06-Is-It-Safe.md)

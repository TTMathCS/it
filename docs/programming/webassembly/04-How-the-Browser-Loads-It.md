# 4. How the browser loads it

*Between opening a page and running the first query, the browser downloads about 16 MB in 12 files, compiles 9 MB of
WebAssembly into real machine code, unpacks a folder tree into memory, and runs `initdb`. This chapter follows those
steps in order, with the times measured in Chromium, and shows the four lines of JavaScript at the centre of it.*

!!! abstract "In this chapter"
    - the four steps: fetch, compile, instantiate, call
    - how a page brings in JavaScript today: ES modules and `import`
    - every file a PGlite page downloads, with its type and size
    - the timeline of a first visit and of a second one
    - how a query gets in and a result gets out

## 4.1 The four steps

Loading any WebAssembly module is the same four steps. Here they are for the 66-byte module of chapter 2, as a
complete web page ([add-demo.html](src/add-demo.html)):

```html
<!doctype html>
<meta charset="utf-8">
<p id="out">loading…</p>
<script type="module">
  // 1. what the module may call: one JavaScript function, under the names it imports
  const imports = { env: { show: n => console.log('the module called show(' + n + ')') } };
  // 2. download, compile and instantiate in one step, while the bytes arrive
  const { instance } = await WebAssembly.instantiateStreaming(fetch('add.wasm'), imports);
  // 3. call the function the module exports
  document.getElementById('out').textContent = 'add(2, 3) = ' + instance.exports.add(2, 3);
</script>
```

Tested in Chromium 153: the page shows `add(2, 3) = 5` and the console shows `the module called show(5)`.

<figure class="mars-fig wide" markdown="0">
<svg viewBox="0 0 680 150" role="img" aria-label="Four boxes in a row with arrows: fetch (HTTP GET of the .wasm file, served as application/wasm), compile (the browser checks the bytes and turns them into x86-64 or ARM machine code), instantiate (create the memory, connect the imports, run the start function), call (JavaScript calls the exports). Fetch and compile overlap when the streaming call is used.">
<g font-size="12" fill="currentColor">
<rect x="10" y="30" width="150" height="80" rx="8" class="soft" stroke="currentColor"/>
<text x="85" y="55" text-anchor="middle" font-weight="bold">1. fetch</text>
<text x="85" y="75" text-anchor="middle" font-size="11">HTTP GET add.wasm</text>
<text x="85" y="91" text-anchor="middle" font-size="11">application/wasm</text>
<rect x="180" y="30" width="150" height="80" rx="8" class="soft" stroke="currentColor"/>
<text x="255" y="55" text-anchor="middle" font-weight="bold">2. compile</text>
<text x="255" y="75" text-anchor="middle" font-size="11">check every byte, then</text>
<text x="255" y="91" text-anchor="middle" font-size="11">make x86-64 / ARM code</text>
<rect x="350" y="30" width="150" height="80" rx="8" class="soft" stroke="currentColor"/>
<text x="425" y="55" text-anchor="middle" font-weight="bold">3. instantiate</text>
<text x="425" y="75" text-anchor="middle" font-size="11">create the memory,</text>
<text x="425" y="91" text-anchor="middle" font-size="11">connect the imports</text>
<rect x="520" y="30" width="150" height="80" rx="8" class="soft-acc"/>
<text x="595" y="55" text-anchor="middle" font-weight="bold">4. call</text>
<text x="595" y="75" text-anchor="middle" font-size="11">JavaScript calls</text>
<text x="595" y="91" text-anchor="middle" font-size="11">instance.exports.add</text>
<g stroke="currentColor"><path d="M160 70 H180"/><path d="M330 70 H350"/><path d="M500 70 H520"/></g>
<path d="M10 128 H330" class="acc" stroke-width="2"/>
<text x="170" y="145" text-anchor="middle" font-size="11">instantiateStreaming: steps 1 and 2 overlap</text>
</g>
</svg>
<figcaption>Every WebAssembly module, from 66 bytes to 9 MB, is loaded this way.</figcaption>
</figure>

Three details worth knowing:

- **`instantiateStreaming`** compiles while the bytes are still arriving. It needs the server to send the file with
  `Content-Type: application/wasm`; with any other type it refuses. Emscripten's standard loader then falls back to
  downloading the whole file first (`fetch`, then `arrayBuffer()`, then `WebAssembly.instantiate`). PGlite 0.5.16's
  own browser loader does not: served as `application/octet-stream`, it stopped with *Failed to execute 'compile' on
  'WebAssembly': Incorrect response MIME type. Expected 'application/wasm'*, and the database never started. A server
  hosting it must send the right type.
- **Compile checks before it runs.** The browser validates the whole module first: every instruction, every type,
  every memory access pattern. A module that fails the check never runs at all.
- **`await` and `type="module"`.** A `<script type="module">` is a modern JavaScript module: it can use `import` and a
  top-level `await`, which waits for a promise (a result that arrives later) without freezing the page.

## 4.2 How a page brings in a library today

If you last wrote web pages with `<script src="jquery.js">`, the newer way is **ES modules**. A page imports what it
needs, by URL, and the browser fetches each file and everything that file imports:

```html
<script type="module">
  import { PGlite } from './pglite/index.js';
  const db = await PGlite.create();
</script>
```

`./pglite/index.js` is the library's entry file, 520 bytes, which imports its chunk files, which import others. The
browser follows the chain. No build step is needed, and the files are cached like any others.

PGlite finds its other files **next to its own JavaScript**: its code asks for
`new URL("./pglite.wasm", import.meta.url)`, where `import.meta.url` is the address of the module file itself. So if
the JavaScript is at `https://it.akadian.ca/assets/pglite/index.js`, the browser fetches
`https://it.akadian.ca/assets/pglite/pglite.wasm`. Self-hosting therefore means copying the package's `dist/` folder,
as it is, to one place on your own site.

## 4.3 What a PGlite page downloads

Measured in Chromium 153, loading the page from a local server with an empty cache:

| File | Content-Type | Bytes | gzip -9 | What it is |
| --- | --- | --- | --- | --- |
| `index.js` + 8 chunk files | `text/javascript` | 504,401 | | PGlite's API, the wire-protocol parser and Emscripten's glue (the largest chunk is 375,491 bytes) |
| `pglite.wasm` | `application/wasm` | 9,086,480 | 3,245,952 | PostgreSQL 18.6, compiled |
| `pglite.data` | `application/octet-stream` | 6,242,272 | 1,860,995 | the 699 files PostgreSQL expects on disk |
| `initdb.wasm` | `application/wasm` | 298,788 | 128,991 | `initdb`, to create a new, empty database |
| **total** | | **16,131,941** | | about 5.4 MB if the server compresses with gzip |

Whether a given web server compresses `.wasm` and `.data` files depends on that server's settings; the gzip column is
what compression would save. GitHub Pages, which serves this site, does compress them, and sends `.wasm` as
`application/wasm` (checked on 12 November 2026). This site's own playground uses the slightly older PGlite 0.5.10,
whose files are a little larger ([chapter 7.7](07-Build-Your-Own-Playground.md#77-the-playground-on-this-site)). Nothing else is downloaded: no extension files (unless the page asks for one), and no
requests at all while queries run (checked with the browser's request log during a series of queries).

## 4.4 The timeline of a first visit

<figure class="mars-fig wide" markdown="0">
<svg viewBox="0 0 680 270" role="img" aria-label="A timeline. The page and index.js load first. At about 50 milliseconds PGlite starts three downloads at once: pglite.wasm, pglite.data and initdb.wasm. pglite.wasm is compiled while it downloads. Then the data files are unpacked into the in-memory file system, initdb creates a new database, and PostgreSQL starts. Ready at about 2.2 seconds on a fast local connection.">
<g font-size="12" fill="currentColor">
<path d="M20 240 H660" stroke="currentColor"/>
<g font-size="11" text-anchor="middle"><text x="20" y="258">0 s</text><text x="148" y="258">0.5 s</text><text x="276" y="258">1 s</text><text x="404" y="258">1.5 s</text><text x="532" y="258">2 s</text><text x="660" y="258">2.5 s</text></g>
<rect x="20" y="20" width="6" height="22" class="soft" stroke="currentColor"/><text x="38" y="36">page.html, index.js and chunks</text>
<rect x="34" y="52" width="23" height="22" class="soft-acc"/><text x="66" y="68">pglite.wasm: download, compiled while it arrives</text>
<rect x="34" y="84" width="11" height="22" class="soft" stroke="currentColor"/><text x="66" y="100">pglite.data: download</text>
<rect x="34" y="116" width="3" height="22" class="soft" stroke="currentColor"/><text x="66" y="132">initdb.wasm: download</text>
<rect x="57" y="148" width="91" height="22" class="soft" stroke="currentColor"/><text x="156" y="164">instantiate, unpack the 699 files into memory</text>
<rect x="148" y="180" width="392" height="22" class="soft-acc"/><text x="344" y="196" text-anchor="middle">initdb: create the database cluster in /pglite/data</text>
<rect x="540" y="212" width="43" height="22" class="soft" stroke="currentColor"/><text x="532" y="228" text-anchor="end">start PostgreSQL, ready</text>
</g>
</svg>
<figcaption>Measured on a local server, so downloads take milliseconds. Over the internet, add the time to download about 16 MB (5 MB compressed) on the first visit. The split of the 2 seconds after the downloads is drawn approximately; the totals are measured.</figcaption>
</figure>

Measured totals, from the start of the page to "ready", in Chromium:

| Visit | Ready after | Why |
| --- | --- | --- |
| first, empty cache, new in-memory database | 2.2 s | downloads (fast here), compile, unpack, `initdb` |
| again, files cached, new in-memory database | 1.6 to 1.9 s | no downloads, but `initdb` runs again: a memory database starts empty every time |
| from a snapshot (`loadDataDir`, chapter 7) | 0.5 to 0.7 s | no `initdb`: the database files are unpacked instead |
| saved in IndexedDB, second visit | 1.05 s | no `initdb`: the database is read back from IndexedDB |

Most of the time on a repeat visit is `initdb`, which builds the system catalogs of a new cluster. A playground
that wants to start faster loads a ready-made cluster instead (chapter 7).

PGlite also starts all three downloads at once, before it needs them, and keeps the compiled module in memory: a
second `PGlite` in the same page (for example after a "Reset" button) reuses it without compiling again.

## 4.5 How a query goes in and a result comes out

PostgreSQL normally talks to clients over a socket using its **wire protocol**: binary messages such as `Query`,
`RowDescription`, `DataRow`, `CommandComplete`, `ErrorResponse`. PGlite keeps that protocol and replaces only the
socket:

1. `db.query('SELECT ...')` in JavaScript builds the same protocol message `psql` would send.
2. The message is copied into the module's linear memory and an exported function is called.
3. PostgreSQL parses, plans and runs the query exactly as on a server, and writes its reply messages into memory.
4. JavaScript reads the reply bytes out of memory, parses them (the same message format), converts each column to a
   JavaScript value (`int4` to a number, `text` to a string, `date` to a `Date`, `json` to an object) and resolves
   the promise with `{ rows, fields }`.

```js
const r = await db.query('SELECT city, count(*) AS n FROM customers GROUP BY city ORDER BY city');
console.log(r.rows);
```

```text
[ { city: 'Montreal', n: 1 }, { city: 'Toronto', n: 2 } ]
```

(Run in Node.js on a three-row table; `count(*)` is a `bigint`, which PGlite returns as a JavaScript number while it
fits.) Errors come back the same way, as PostgreSQL's own `ErrorResponse` with its code and message, for example
`syntax error at or near "SELEC"`.

All of this runs **on the page's main thread** unless the page moves PGlite into a Web Worker (PGlite provides
`PGliteWorker` for that). On the main thread, a long query freezes the page until it finishes: in a test, a 5.4-second
`count(*)` over 20 million rows let a 10-millisecond timer fire **zero** times. For playground-sized tables this does
not matter.

Next: [5. Where everything is kept](05-Where-Everything-Is-Kept.md).

# 3. From C source to .wasm

*A `.wasm` file is made the way any binary is made: compile each C file to an object file, then link the object files
into one program. The only differences are the target (`wasm32`) and what happens to the functions the program
cannot find, such as `printf` or `open`. They become imports, and something has to supply them. That something is
Emscripten.*

!!! abstract "In this chapter"
    - compile and link a C function to WebAssembly with plain clang, and run it
    - why `#include <stdio.h>` fails, and how a missing function turns into an import
    - what Emscripten adds: a C library, a JavaScript "glue" file, and a packed file system
    - how PostgreSQL becomes the PGlite package

## 3.1 One C function, compiled with clang

[squares.c](src/squares.c):

```c
// squares.c: one C function, and one function it borrows from the page
__attribute__((import_module("env"), import_name("show")))
void show(int n);                 /* written in JavaScript, given to the module */

__attribute__((export_name("sum_squares")))
int sum_squares(int n) {          /* 1*1 + 2*2 + ... + n*n */
    int total = 0;
    for (int i = 1; i <= n; i++)
        total += i * i;
    show(total);
    return total;
}
```

The two `__attribute__` lines say which function comes from outside (`env.show`) and which one the module offers
(`sum_squares`). Compiling and linking with clang 18, in two steps, exactly as for a Linux program:

```bash
clang --target=wasm32 -O2 -c squares.c -o squares.o        # compile: C -> object file
wasm-ld --no-entry --strip-all squares.o -o squares.wasm   # link: object files -> one module
```

| File | Size | What `file` says |
| --- | --- | --- |
| `squares.o` | 406 bytes | `WebAssembly (wasm) binary module version 0x1 (MVP)` |
| `squares.wasm` | 177 bytes | the linked module |

The object file is already WebAssembly (it starts with `00 61 73 6d`), with extra sections the linker needs.
`--no-entry` says there is no `main`, it is a library; `--strip-all` drops the names kept for debuggers. Running it in
Node.js:

```js
const { instance } = await WebAssembly.instantiate(require('fs').readFileSync('squares.wasm'),
                                                   { env: { show: n => console.log('C says:', n) } });
console.log('returned', instance.exports.sum_squares(10));
```

```text
C says: 385
returned 385
```

The linked module also exports its `memory` (2 pages of 64 KB to start with), which the page can read and write.

## 3.2 Where printf goes

Try the classic first program:

```c
#include <stdio.h>
int main(void) { printf("hi\n"); return 0; }
```

```text
hello.c:1:10: fatal error: 'stdio.h' file not found
```

Plain clang has a compiler for WebAssembly but **no C library** for it: there is no `stdio.h`, no `malloc`, no `open`.
Declare the function yourself and the linker cannot find it:

```text
wasm-ld-18: error: /tmp/hello2-a69b7a.o: undefined symbol: puts
```

Tell the linker to allow it (`-Wl,--allow-undefined`) and the missing function becomes an **import**:

```text
[ { module: 'env', name: 'puts', kind: 'function' } ]
```

That is the whole trick behind running large C programs: everything the program cannot do inside its own memory
(print, open a file, read the time) ends up as an import, and the page supplies a JavaScript function for each one.
Doing that by hand for a program the size of PostgreSQL is impossible. Emscripten does it.

## 3.3 What Emscripten adds

[Emscripten](https://emscripten.org/) is a compiler toolchain built around the same clang and wasm-ld. Its command,
`emcc`, is used like `gcc`. On top of the compiler it brings:

1. **A C library** (based on musl) compiled to WebAssembly, so `printf`, `malloc`, `fopen`, `qsort` and the rest exist.
   Its lowest layer, the system calls, are left as imports (`__syscall_openat`, `fd_write` ...).
2. **A JavaScript glue file**, written next to the `.wasm`, which supplies those imports: a Unix-like file system kept
   in memory (MEMFS), a console that sends `stdout` to `console.log`, clocks, random numbers, `dlopen` for loading more
   wasm modules, and the code that downloads, compiles and starts the module.
3. **A file packager**, which takes folders the program expects to find on disk and packs them into one `.data` file,
   with the list of names and offsets written into the glue ([chapter 2.5](02-Inside-a-wasm-File.md#25-the-other-file-pglitedata-a-folder-in-one-file)).

The usual commands, from Emscripten's documentation (Emscripten itself could not be installed on the machine used for
these pages, so these lines were not run here; the PGlite files they describe were):

```bash
emcc hello.c -o hello.js                         # writes hello.js (glue) and hello.wasm
emcc hello.c -o hello.html                       # the same, plus a test page that loads them
emcc app.c -o app.js --preload-file assets/      # also writes app.data, holding the assets/ folder
```

<figure class="mars-fig wide" markdown="0">
<svg viewBox="0 0 680 250" role="img" aria-label="The build: PostgreSQL's C files are compiled by emcc into object files, then linked with Emscripten's C library into pglite.wasm. emcc also writes the JavaScript glue. The file packager packs PostgreSQL's share and lib folders into pglite.data. PGlite's own TypeScript wraps the glue, and the npm package ships the JavaScript, pglite.wasm, pglite.data and initdb.wasm.">
<g font-size="12" fill="currentColor">
<rect x="10" y="20" width="140" height="40" rx="6" class="soft" stroke="currentColor"/><text x="80" y="38" text-anchor="middle" font-weight="bold">PostgreSQL 18.6</text><text x="80" y="52" text-anchor="middle" font-size="11">C source, patched</text>
<rect x="10" y="110" width="140" height="40" rx="6" class="soft" stroke="currentColor"/><text x="80" y="128" text-anchor="middle" font-weight="bold">share/ and lib/</text><text x="80" y="142" text-anchor="middle" font-size="11">files Postgres reads</text>
<rect x="10" y="190" width="140" height="40" rx="6" class="soft" stroke="currentColor"/><text x="80" y="208" text-anchor="middle" font-weight="bold">PGlite TypeScript</text><text x="80" y="222" text-anchor="middle" font-size="11">query(), exec() ...</text>
<rect x="200" y="20" width="150" height="40" rx="6" stroke="currentColor" fill="none"/><text x="275" y="38" text-anchor="middle">emcc: compile + link</text><text x="275" y="52" text-anchor="middle" font-size="11">with Emscripten's libc</text>
<rect x="200" y="110" width="150" height="40" rx="6" stroke="currentColor" fill="none"/><text x="275" y="134" text-anchor="middle">file packager</text>
<rect x="200" y="190" width="150" height="40" rx="6" stroke="currentColor" fill="none"/><text x="275" y="214" text-anchor="middle">TypeScript build</text>
<g stroke="currentColor" fill="none"><path d="M150 40 H200"/><path d="M150 130 H200"/><path d="M150 210 H200"/><path d="M350 30 H410"/><path d="M350 50 L410 80"/><path d="M350 130 H410"/><path d="M275 60 L275 75 L410 75" stroke-dasharray="3 3"/><path d="M350 210 H410"/></g>
<rect x="410" y="12" width="250" height="34" rx="6" class="soft-acc"/><text x="535" y="34" text-anchor="middle" font-weight="bold">pglite.wasm  9.1 MB</text>
<rect x="410" y="62" width="250" height="34" rx="6" class="soft-acc"/><text x="535" y="84" text-anchor="middle">glue JavaScript (in the chunks)</text>
<rect x="410" y="113" width="250" height="34" rx="6" class="soft-acc"/><text x="535" y="135" text-anchor="middle" font-weight="bold">pglite.data  6.2 MB</text>
<rect x="410" y="193" width="250" height="34" rx="6" class="soft-acc"/><text x="535" y="215" text-anchor="middle">index.js + chunks, ~0.5 MB</text>
<text x="535" y="168" text-anchor="middle" font-size="11">initdb.wasm 0.3 MB: initdb, built the same way</text>
</g>
</svg>
<figcaption>How the files in the PGlite package are made. The sizes are those of PGlite 0.5.16.</figcaption>
</figure>

## 3.4 PostgreSQL as PGlite

A normal PostgreSQL server is several processes: the postmaster listens on port 5432 and forks one backend process
per connection, next to background writers. WebAssembly in a page has no processes and no listening sockets, so
PGlite's authors patch PostgreSQL to run as **one process, inside one module, serving one connection**, and to take
its queries from JavaScript instead of from a socket. The version string says what was built and how:

```sql
SELECT version();
```

```text
PostgreSQL 18.6 (PGlite 0.5.16) on wasm32-unknown-emscripten, compiled by emcc (Emscripten gcc/clang-like
replacement + linker emulating GNU ld) 6.0.13 (e13ee988ce3d87a738dd8f3661d02223308c412a), 32-bit
```

`wasm32-unknown-emscripten` is the target, in the same form as `x86_64-pc-linux-gnu` on a Linux server, and
`32-bit` means pointers are 4 bytes, so one instance can address at most 4 GB of memory.

The npm package `@electric-sql/pglite` 0.5.16 (licence Apache-2.0) ships, in its `dist/` folder: `pglite.wasm`,
`pglite.data`, `initdb.wasm` (PostgreSQL's `initdb` program, built separately and run to create a fresh database),
the JavaScript (an `index.js` entry point of 520 bytes that pulls in eight chunk files), and one `.tar.gz` per optional
extension (`pgcrypto`, `hstore`, `pg_trgm`, `uuid-ossp` and others), which are only downloaded if a page asks for
that extension.

Next: [4. How the browser loads it](04-How-the-Browser-Loads-It.md).

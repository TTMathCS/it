# 6. Is it safe?

*A program as big as PostgreSQL, downloaded and run inside your browser, sounds risky. It is much less risky than it
sounds, because a WebAssembly module starts with no access to anything at all: not your files, not the network, not
the page. It gets only what the page hands it. This chapter lists what PGlite is handed, tries the things a
database superuser could do on a real server, and then names the risks that remain, which are about the page and the
files, not the module.*

!!! abstract "In this chapter"
    - the sandbox: bounds-checked memory, imports only, the same rules as the page's JavaScript
    - what PostgreSQL inside can reach: a pretend file system with five folders, and no network port
    - superuser powers that do nothing outside the tab: files, programs, `/etc/passwd`
    - the real risks: freezing the tab, the page's own code, and where the files come from
    - a checklist for a safe playground

## 6.1 The short answer

The module runs **inside the same sandbox as the page's JavaScript**, with fewer rights than that JavaScript. It can
compute inside its own block of memory and call the functions it was given. Everything PostgreSQL does to "the disk"
happens in that memory. Nothing in the module can open a file on your computer, start a program, or read another
site's data, because the browser offers no way to do those things to any page.

The remaining risks are ordinary web risks: a heavy query can freeze the tab, a careless page could display a result
in an unsafe way, and the files must come from a trustworthy source.

## 6.2 What PostgreSQL can reach

Three rules come from WebAssembly itself, and all three were tried:

**1. Memory is bounds-checked.** A module can read and write only its own linear memory. A 55-byte test module with
one 64 KB page:

```text
peek(65535) = 0
peek(65536) -> RuntimeError: memory access out of bounds
peek(-1)    -> RuntimeError: memory access out of bounds
```

There is no pointer trick that reaches the browser's own memory, or the page's: the address is checked on every load
and store.

**2. Only imports, and only if supplied.** [Chapter 2](02-Inside-a-wasm-File.md#22-the-same-module-in-binary-66-bytes)
showed a module refusing to start without its one import. `pglite.wasm` imports 135 functions, all supplied by
PGlite's own JavaScript. By group:

| Imports | What they do in PGlite |
| --- | --- |
| file calls: `__syscall_openat`, `fd_read`, `fd_write`, `__syscall_mkdirat`, `__syscall_unlinkat` ... | act on Emscripten's file system **in memory** (or the IndexedDB / OPFS copy of chapter 5) |
| `clock_time_get`, `emscripten_date_now`, `random_get` | the browser's clock and its secure random numbers |
| `_dlopen_js`, `_dlsym_js` | load another WebAssembly module from the in-memory file system (PostgreSQL's extensions) |
| `__syscall_socket`, `__syscall_connect`, `__syscall_bind`, `__syscall_listen` ... | handled by the JavaScript glue; a page cannot open a raw network socket, so at most these could become the same browser requests any script on the page can make |
| `exit`, `_abort_js`, `invoke_*` | stop the program; emulate C's error jumps |

**3. The module has no window on the page.** It has no import for the page's content (the DOM), cookies, or
storage; only the JavaScript around it can touch those.

And PGlite runs no server: there is no port to connect to. Asked where it listens:

```sql
SELECT inet_server_addr(), inet_server_port();
```

```text
 inet_server_addr | inet_server_port
------------------+------------------
                  |
```

Both are NULL, as for a connection over a Unix socket: there is no network address.

## 6.3 A superuser in a box

Inside PGlite you are the PostgreSQL superuser:

```sql
SELECT current_user, rolsuper FROM pg_roles WHERE rolname = current_user;
```

```text
 current_user | rolsuper
--------------+----------
 postgres     | t
```

On a real server a superuser can read and write the server's files and run programs as the server's operating-system
user. Here is what those powers reach in PGlite 0.5.16 (all run in Node.js; the first, second and last also in Chromium 153, with the same results):

| Try | Result |
| --- | --- |
| `SELECT pg_ls_dir('/')` | `tmp`, `home`, `dev`, `proc`, `pglite`: the whole pretend disk, five folders |
| `SELECT pg_read_file('/etc/passwd')` | `could not open file "/etc/passwd" for reading: No such file or directory` |
| `COPY t TO '/tmp/t.csv' WITH (FORMAT csv)`, then `SELECT pg_read_file('/tmp/t.csv')` | works, and returns `1\n2\n`: the file was written **into memory**, nowhere else |
| `COPY t TO PROGRAM 'ls'` | there are no programs and no processes. No error came back, but the database answered **nothing** afterwards (an empty result even for `SELECT count(*)`), until it was started again |

Try them yourself, in the same PostgreSQL that the SQL course pages use (it starts when you first press Run):

<div class="sqlplay-free" data-db="empty" data-start="SELECT current_user, d AS folder FROM pg_ls_dir('/') AS d;
"></div>

So the superuser's powers are real, over a computer that exists only inside the tab. The last row matters for a
playground: it should have a **Reset** button that starts a fresh database, for this and for the simpler accidents
(`DROP TABLE customers`).

The package also contains a `.pgpass` file and a default password (the word `password`). They are the same in every
copy and protect nothing, which is fine: nothing outside the page can connect.

## 6.4 Rules the browser adds

- **Same origin.** Pages from `it.akadian.ca` can read only `it.akadian.ca`'s storage; another site cannot read the
  IndexedDB database of chapter 5, and this site cannot read anyone else's.
- **Content Security Policy.** A site can declare which code its pages may run. Compiling WebAssembly needs one
  explicit word, `'wasm-unsafe-eval'`. Tested in Chromium 153 with the 66-byte module:

    | Policy | Result |
    | --- | --- |
    | `script-src 'self' 'unsafe-inline'` | refused: *Compiling or instantiating WebAssembly module violates the following Content Security policy directive* |
    | `script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'` | `add(2, 3) = 5` |

    `'wasm-unsafe-eval'` allows compiling WebAssembly and nothing more; it does **not** allow JavaScript's `eval`.
- **Validation.** The browser checks every byte of a module before running it ([chapter 4](04-How-the-Browser-Loads-It.md#41-the-four-steps)).

## 6.5 The risks that remain

| Risk | What happens | What to do |
| --- | --- | --- |
| a heavy query | runs on the page's main thread and freezes the tab until it ends: a 20-million-row `count(*)` took 5.4 s, during which a 10 ms timer fired zero times | small tables; close or reload the tab to stop it; or run PGlite in a Web Worker (`PGliteWorker`) so the page stays responsive |
| memory | each database instance holds about 190 MB | one instance per page, shared by all the run boxes on it, not one per box |
| the page shows results unsafely | a result is just text, but if a page put it into the page as HTML (`innerHTML`), text such as `<img src=x onerror=...>` typed into a table would run as code | show results with `textContent` or by building table cells; never as HTML |
| where the files come from | the `.wasm` and `.js` run with the page's rights; a tampered copy could do anything the page can | take them from the official package, pin the version, check the hash, serve them from your own site (6.6) |
| your data | queries and rows never leave the computer: a request log kept during a series of queries showed **zero** requests | nothing to do; but nothing is backed up either (chapter 5.9) |

## 6.6 Checking the files

The official package is `@electric-sql/pglite` on the npm registry, from the electric-sql project
(`github.com/electric-sql/pglite`, licence Apache-2.0). The registry publishes a SHA-512 hash of each version's
tarball, and the downloaded file can be checked against it:

```bash
npm view @electric-sql/pglite@0.5.16 dist.integrity dist.tarball
curl -sSO https://registry.npmjs.org/@electric-sql/pglite/-/pglite-0.5.16.tgz
openssl dgst -sha512 -binary pglite-0.5.16.tgz | base64 -w0      # on a Mac: base64 without -w0
```

Run on 12 November 2026, both gave the same value:

```text
sha512-Nj8KcIsJL748W408U2N8q4+9IlONdpRIU8MJypIAAINMJ5nqKyqpX7Mgg/5XKkXiAib3AoZGR6hnJFlrlLBrcg==
Nj8KcIsJL748W408U2N8q4+9IlONdpRIU8MJypIAAINMJ5nqKyqpX7Mgg/5XKkXiAib3AoZGR6hnJFlrlLBrcg==
```

The tarball is 9,308,373 bytes. Unpack it with `tar xzf` (not `npm install`, so no package scripts run), copy the
`package/dist/` files a page needs to your own site, and record the version, hash, source and date next to them. Once
the files are on your own site, the page loads nothing from anyone else.

## 6.7 A checklist for a safe playground

1. PGlite from the official npm package, one exact version, hash checked, files served from your own site.
2. The server sends `.wasm` as `application/wasm` (PGlite will not start otherwise, [chapter 4](04-How-the-Browser-Loads-It.md#41-the-four-steps)).
3. A Content Security Policy that allows `'wasm-unsafe-eval'` and nothing wider than the site needs.
4. Results shown as text, never as HTML.
5. One database per page, in memory, with a Reset button.
6. Small practice tables, so no query runs for long.
7. Check the browser's request log once: after the files load, running queries makes no requests.

Next: [7. Build your own playground](07-Build-Your-Own-Playground.md).

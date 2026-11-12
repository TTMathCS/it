# 2. Inside a .wasm file, byte by byte

*A `.wasm` file is binary, not text. This chapter writes the smallest useful module by hand, 66 bytes, and reads every
byte of it. Then it opens the real PostgreSQL module (9 MB) with the same eyes, and the 6 MB `.data` file that comes
with it, which turns out to be a whole folder tree glued into one file.*

!!! abstract "In this chapter"
    - the text form (`.wat`) and the binary form (`.wasm`) of the same module
    - the header and the numbered sections, read byte by byte
    - what is inside `pglite.wasm`: 2,016 exported functions, 135 imports, 6.5 MB of code
    - what `pglite.data` is: 699 files laid end to end, with their names and offsets kept in the JavaScript

## 2.1 A module in text form

WebAssembly has a text form for people, `.wat`, and a binary form for machines, `.wasm`. They say the same thing; a
tool (`wat2wasm` from the wabt toolkit) turns one into the other. Here is a whole module in text form,
[add.wat](src/add.wat):

```wasm
(module
  (import "env" "show" (func $show (param i32)))
  (func (export "add") (param $a i32) (param $b i32) (result i32)
    local.get $a
    local.get $b
    i32.add
    call $show
    local.get $a
    local.get $b
    i32.add))
```

Read it as: *this module needs one function from outside, `env.show`, which takes a 32-bit integer. It offers one
function, `add`, which takes two 32-bit integers and returns one.* Inside `add`, WebAssembly is a **stack machine**:
`local.get` pushes a value, `i32.add` pops two and pushes their sum, `call $show` pops one and passes it to `show`.
So `add` adds the numbers, shows the sum, adds them again and returns it.

## 2.2 The same module in binary: 66 bytes

Assembled, it is [add.wasm](src/add.wasm), 66 bytes. Here they are, in hexadecimal, 16 to a line:

```text
00 61 73 6d 01 00 00 00 01 0b 02 60 01 7f 00 60
02 7f 7f 01 7f 02 0c 01 03 65 6e 76 04 73 68 6f
77 00 00 03 02 01 01 07 07 01 03 61 64 64 00 01
0a 10 01 0e 00 20 00 20 01 6a 10 00 20 00 20 01
6a 0b
```

The file is a header and then **sections**. Each section is one byte saying which kind it is, then its length, then
its contents. Numbers are stored in a variable-length form (LEB128), so small numbers take one byte.

| Bytes | Meaning |
| --- | --- |
| `00 61 73 6d` | the magic number: a zero byte and the letters `asm`. Every `.wasm` file starts with it |
| `01 00 00 00` | format version 1 |
| `01 0b` | **section 1, types**, 11 bytes long |
| `02` | two function shapes follow |
| `60 01 7f 00` | shape 0: a function (`60`) with 1 parameter of type i32 (`7f`) and 0 results |
| `60 02 7f 7f 01 7f` | shape 1: a function with 2 i32 parameters and 1 i32 result |
| `02 0c` | **section 2, imports**, 12 bytes |
| `01` | one import |
| `03 65 6e 76` | a 3-letter module name: `env` |
| `04 73 68 6f 77` | a 4-letter name: `show` |
| `00 00` | it is a function (`00`) of shape 0 |
| `03 02 01 01` | **section 3, functions**, 2 bytes: one function of my own, of shape 1 |
| `07 07` | **section 7, exports**, 7 bytes |
| `01 03 61 64 64 00 01` | one export, named `add` (3 letters), a function, number 1 (number 0 is the import) |
| `0a 10` | **section 10, code**, 16 bytes |
| `01 0e 00` | one function body, 14 bytes long, no extra local variables |
| `20 00` `20 01` | `local.get 0`, `local.get 1` |
| `6a` | `i32.add` |
| `10 00` | `call 0` (the imported `show`) |
| `20 00 20 01 6a` | `local.get 0`, `local.get 1`, `i32.add` again |
| `0b` | `end` |

That is all there is: 8 + 13 + 14 + 4 + 9 + 18 = 66 bytes. No text, no names except the import and export names,
nothing a person would recognise as `a` and `b`. Running it in Node.js 22:

```js
const bytes = require('fs').readFileSync('add.wasm');
const { instance } = await WebAssembly.instantiate(bytes, { env: { show: n => console.log('show', n) } });
console.log('add(2,3) =', instance.exports.add(2, 3));
```

```text
show 5
add(2,3) = 5
```

And with no imports supplied, it refuses to start:

```text
TypeError: WebAssembly.instantiate(): Import #0 module="env": module is not an object or function
```

This is already the heart of the security model of [chapter 6](06-Is-It-Safe.md): the module can call only what it
lists in its import section, and only if the page supplies it.

The same module, loaded by a real web page: [add-demo.html](src/add-demo.html) (open it, the page shows `add(2, 3) = 5`;
the `show` call appears in the browser's console).

## 2.3 The other kinds of section

A module made by a real compiler has more of the numbered sections. All of them, as the
[specification](https://webassembly.github.io/spec/core/binary/modules.html) numbers them:

| Id | Section | Holds |
| --- | --- | --- |
| 0 | custom | anything a tool wants: function names for debuggers, the compiler's name, linking information |
| 1 | type | the function shapes (parameters and results) |
| 2 | import | what the module needs from outside: functions, memory, tables, globals |
| 3 | function | which shape each of the module's own functions has |
| 4 | table | tables of function references, used for calls through function pointers |
| 5 | memory | the module's own linear memory, if it does not import one: starting and maximum size in 64 KB pages |
| 6 | global | global variables |
| 7 | export | what the module offers, by name |
| 8 | start | a function to run as soon as the module starts |
| 9 | element | the initial contents of the tables |
| 10 | code | the bodies of the functions: the program itself |
| 11 | data | bytes to copy into linear memory at start: C string constants, static arrays |
| 12 | data count | how many data segments there are (helps the browser check the code in one pass) |

## 2.4 The real thing: pglite.wasm

The same section walk over `pglite.wasm` from PGlite 0.5.16 (9,086,480 bytes):

| Section | Size | What it is |
| --- | --- | --- |
| custom `dylink.0` | 25 B | marks it as a module that can load other modules (PostgreSQL's extensions) |
| type | 2.3 KB | function shapes |
| import | 3.1 KB | **135 functions and 1 memory** it needs from outside |
| function | 13.8 KB | one entry per function |
| table, global | 0.9 KB | |
| export | 41.5 KB | **2,016 functions** offered by name, for example `ExecutorRun`, `SPI_execute`, `pgl_startPGlite` |
| start | 2 B | |
| element | 14.0 KB | the function-pointer table |
| data count | 2 B | |
| code | **6,451,730 B** | PostgreSQL itself, compiled: about 71% of the file |
| data | **2,559,093 B** | PostgreSQL's constants and static tables, copied into memory at start |

The first 32 bytes of the file, as `od -A x -t x1z` shows them:

```text
000000 00 61 73 6d 01 00 00 00 00 19 08 64 79 6c 69 6e  >.asm.......dylin<
000010 6b 2e 30 01 05 00 0c c3 36 00 06 07 06 77 61 73  >k.0.....6....was<
```

The same magic number and version, then section 0 (custom, `19` = 25 bytes) named `dylink.0`.

Its 135 imported functions are the only way PostgreSQL can reach anything outside its memory. They come from two
modules: `env` (122) and `wasi_snapshot_preview1` (13), a standard set of system-call shapes. Apart from 56 small
`invoke_...` helpers (used to emulate C's `setjmp`/`longjmp` error handling, which PostgreSQL relies on), they are
the system calls you would expect from a Unix program: `__syscall_openat`, `fd_read`, `fd_write`, `__syscall_mkdirat`,
`__syscall_unlinkat`, `clock_time_get`, `random_get`, `_dlopen_js`, and also `__syscall_socket` and
`__syscall_connect`. [Chapter 6](06-Is-It-Safe.md#62-what-postgresql-can-reach) looks at what each group really does.

The memory is **imported**, not declared: the JavaScript creates the `ArrayBuffer` and hands it over, so it can read
query results straight out of it.

## 2.5 The other file: pglite.data, a folder in one file

PostgreSQL expects a disk with files on it: the catalog template that `initdb` uses (`postgres.bki`), time-zone
data, the SQL for `information_schema`, text-search dictionaries, and the extension libraries (`.so` files) it loads
with `dlopen`. A browser has no disk to put them on, so Emscripten's **file packager** puts them all in one file.

`pglite.data` (6,242,272 bytes) has no header and no table of contents. It is simply **699 files laid end to end**.
The list of names and byte ranges is written into the JavaScript glue instead, as `{filename, start, end}` entries.
The first three:

```text
filename:"/home/postgres/.pgpass", start:0,   end:204
filename:"/pglite/bin/initdb",     start:204, end:223
filename:"/pglite/bin/pg_dump",    start:223, end:242
```

At start, the glue downloads the `.data` file, creates each path in the in-memory file system, and copies each byte
range into it. Measured contents, by folder:

| Folder | Files | Bytes | What |
| --- | --- | --- | --- |
| `/pglite/lib/postgresql` | 38 | 3,161,648 | extension libraries: PL/pgSQL, the Snowball stemmers, character-set converters |
| `/pglite/share/postgresql/postgres.bki` | 1 | 973,769 | the system catalog `initdb` builds every new database from |
| `/pglite/icu` | 3 | 942,999 | ICU collation data (sorting rules for many languages) |
| `/pglite/share/postgresql/timezone` | 598 | 704,788 | the time-zone database |
| the rest of `/pglite/share/postgresql` | 51 | 458,736 | `information_schema.sql`, system views, sample configs, dictionaries |
| small files | 8 | 332 | a default password file, placeholders |

Two details show how literal the "disk image" is:

- the `.so` libraries are themselves WebAssembly modules. `plpgsql.so` starts at byte 2,096,602 of `pglite.data`,
  and its first bytes are `00 61 73 6d 01 00 00 00`. PostgreSQL loads it with `dlopen`, which the glue turns into
  "compile this wasm module and link it in".
- `/pglite/bin/postgres` is 19 bytes of text, `PGlite is the best!`: a placeholder so that PostgreSQL finds a file
  where it expects its own program. The real program is `pglite.wasm`.

## 2.6 Looking at a .wasm file yourself

| Tool | What it shows |
| --- | --- |
| `od -A x -t x1z file.wasm \| head` (or `xxd`, `hexdump -C`) | the raw bytes |
| `wasm-objdump -h file.wasm` (wabt) | the section list with sizes |
| `wasm2wat file.wasm` (wabt) | the text form; for a 9 MB module, millions of lines |
| `WebAssembly.Module.imports(m)` / `.exports(m)` in Node.js or the browser console | the import and export lists |
| Chrome DevTools, Sources panel | each wasm function, disassembled, with breakpoints |

The section walk in 2.4 was a 15-line Node.js script that reads the header and then each section's id and length;
the import and export counts came from `WebAssembly.Module.imports` and `WebAssembly.Module.exports`.

Next: [3. From C source to .wasm](03-From-C-Source-to-wasm.md).

# WebAssembly: real programs inside a web page

*How a program written in C, such as PostgreSQL, ends up running inside a browser tab: what WebAssembly is, what the
downloaded files are and what is inside them, how the browser loads them, where everything is kept afterwards, how
safe it is, and how to build your own SQL playground with tables and data already in it. Written for someone who
knows servers, Linux and databases well but has not followed what browsers learned to do in the last ten years.*

**About the examples.** Everything on these pages was run before it was written down, on 12 November 2026:
PGlite 0.5.16 (PostgreSQL 18.6 compiled to WebAssembly) in Node.js 22 and in Chromium 153, a hand-written 66-byte
module assembled with wabt, and a C file compiled with clang 18. Sizes, timings and file lists are the measured ones.
Where something was not checked, the page says so.

## The short answers

| Question | Answer | Chapter |
| --- | --- | --- |
| What is WebAssembly? | A machine language for an imaginary CPU, which every modern browser can run safely and fast. Compilers turn C, C++, Rust and Go into it. | [1](01-What-WebAssembly-Is.md) |
| What format is a `.wasm` file? | Binary. It starts with the 4 bytes `00 61 73 6D` ("\0asm"), then version 1, then numbered sections: types, imports, functions, exports, code, data. | [2](02-Inside-a-wasm-File.md) |
| How is it put together? | A compiler (clang, usually through Emscripten) compiles the C source for the `wasm32` target and links it into one `.wasm` file, plus a JavaScript "glue" file that gives it a file system, a clock and so on. | [3](03-From-C-Source-to-wasm.md) |
| What files does a PostgreSQL page download? | For PGlite 0.5.16: `pglite.wasm` (9.1 MB, PostgreSQL itself), `pglite.data` (6.2 MB, the files PostgreSQL needs on disk), `initdb.wasm` (0.3 MB, makes a new database) and about 0.5 MB of JavaScript. | [4](04-How-the-Browser-Loads-It.md) |
| How does the browser run it? | `fetch` the bytes, `compile` them to the real CPU's code, `instantiate` with the functions the module may call, then JavaScript calls the module's exported functions. | [4](04-How-the-Browser-Loads-It.md) |
| Where is it kept after loading? | The downloaded files in the browser's HTTP cache; the compiled machine code in the code cache; the database in the tab's memory, gone on reload, unless you choose IndexedDB or OPFS. | [5](05-Where-Everything-Is-Kept.md) |
| Is it safe? | The module runs in the same sandbox as the page's JavaScript. It can touch only its own memory and call only the functions the page hands it. PostgreSQL inside sees a pretend file system with five folders. | [6](06-Is-It-Safe.md) |
| How do I preload tables and data? | Run a seed `.sql` file when the page starts (small data, best for learning), or load a snapshot made with `dumpDataDir()` (big data). | [7](07-Build-Your-Own-Playground.md) |

## The chapters

| Chapter | The question it answers |
| --- | --- |
| [1. What WebAssembly is](01-What-WebAssembly-Is.md) | What changed in browsers, and why a database can now run in one? |
| [2. Inside a .wasm file, byte by byte](02-Inside-a-wasm-File.md) | What exactly is in the binary file? |
| [3. From C source to .wasm](03-From-C-Source-to-wasm.md) | How is a C program turned into one, and what does Emscripten add? |
| [4. How the browser loads it](04-How-the-Browser-Loads-It.md) | What happens, step by step, between opening the page and the first query? |
| [5. Where everything is kept](05-Where-Everything-Is-Kept.md) | Where do the files and the database live on my computer, and how do I see and clear them? |
| [6. Is it safe?](06-Is-It-Safe.md) | What can the code inside do, and what can it not do? |
| [7. Build your own playground](07-Build-Your-Own-Playground.md) | How do I start the database with my own tables and rows already in it? |

The SQL to type into a playground is taught in the [SQL course](../../databases/sql/index.md); its sample database,
[shop.sql](../../databases/sql/sample-database.md), is the one loaded in the examples of chapter 7.

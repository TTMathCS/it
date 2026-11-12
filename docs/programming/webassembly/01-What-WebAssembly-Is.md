# 1. What WebAssembly is

*For twenty years a web page could run exactly one programming language: JavaScript. Since 2017 every major browser
can also run WebAssembly, a compact machine language for a CPU that does not exist. Compilers for C, C++, Rust and Go
can produce it, so programs that were never written for the web, PostgreSQL among them, can be compiled once more and
run inside a tab.*

!!! abstract "In this chapter"
    - what a browser could run before, and what it can run now
    - WebAssembly in four words: module, memory, imports, exports
    - the same ideas in server terms: binary, address space, syscalls
    - how fast it is, measured on one query

## 1.1 What a browser used to run

A web page is three kinds of text: **HTML** (what is on the page), **CSS** (how it looks) and **JavaScript** (what it
does). The browser downloads the text and runs the JavaScript with its own engine (V8 in Chrome and Edge,
SpiderMonkey in Firefox, JavaScriptCore in Safari). Any program you wanted in a page had to be written in JavaScript,
or translated into it.

That rules out most of the software in the world, which is written in C, C++, Java, Rust or Go. PostgreSQL, for
example, is about a million lines of C. Rewriting it in JavaScript is out of the question.

## 1.2 What changed

Browser makers agreed on a second language that the engine runs next to JavaScript: **WebAssembly**, "wasm" for short.
It shipped in Chrome, Firefox, Safari and Edge in 2017 and became a W3C standard in 2019. It is not a language people
write by hand (though they can, as chapter 2 shows). It is a **target for compilers**, like x86-64 or ARM64:

<figure class="mars-fig wide" markdown="0">
<svg viewBox="0 0 660 200" role="img" aria-label="The same C source code goes to three compilers. One makes an x86-64 program for a Linux server, one makes an ARM64 program for a Mac, and one makes a wasm32 module that any browser can run, on any computer.">
<g font-size="13" fill="currentColor">
<rect x="10" y="78" width="130" height="44" rx="6" class="soft" stroke="currentColor"/>
<text x="75" y="98" text-anchor="middle" font-weight="bold">C source</text>
<text x="75" y="114" text-anchor="middle" font-size="11">postgres/*.c</text>
<g stroke="currentColor" fill="none"><path d="M140 100 L250 32"/><path d="M140 100 L250 100"/><path d="M140 100 L250 168" class="acc" stroke-width="2"/></g>
<rect x="250" y="12" width="150" height="40" rx="6" stroke="currentColor" fill="none"/>
<text x="325" y="37" text-anchor="middle">compile for x86-64</text>
<rect x="250" y="80" width="150" height="40" rx="6" stroke="currentColor" fill="none"/>
<text x="325" y="105" text-anchor="middle">compile for ARM64</text>
<rect x="250" y="148" width="150" height="40" rx="6" class="soft-acc"/>
<text x="325" y="173" text-anchor="middle" font-weight="bold">compile for wasm32</text>
<g stroke="currentColor" fill="none"><path d="M400 32 L450 32"/><path d="M400 100 L450 100"/><path d="M400 168 L450 168" class="acc" stroke-width="2"/></g>
<text x="458" y="28">ELF binary</text><text x="458" y="43" font-size="11">runs on one Linux server</text>
<text x="458" y="96">Mach-O binary</text><text x="458" y="111" font-size="11">runs on one Mac</text>
<text x="458" y="164" font-weight="bold">.wasm module</text><text x="458" y="179" font-size="11">runs in any browser, any computer</text>
</g>
</svg>
<figcaption>WebAssembly is one more compile target. The difference: the "CPU" it targets is built into every browser.</figcaption>
</figure>

When a page loads a `.wasm` file, the browser does not interpret it instruction by instruction. It **compiles** it, a
second time, into the real machine code of your CPU (x86-64 or Apple's ARM), and then runs that. This is why it is
fast, and why the first load takes a moment.

## 1.3 Four words: module, memory, imports, exports

Everything about WebAssembly fits around four ideas.

**Module.** The `.wasm` file: compiled code plus a description of what it needs and what it offers. It is to the
browser what an ELF file is to Linux.

**Memory.** A module's working memory is one flat block of bytes, called **linear memory**. In JavaScript it is an
ordinary `ArrayBuffer`. All of the program's C variables, its heap, its stack and, for PGlite, the whole database
when kept in memory live inside it. The program cannot address a single byte outside it. Measured: one PGlite
instance had **197,722,112 bytes** (about 190 MB) of linear memory right after starting.

**Imports.** A module cannot do anything on its own except compute. It cannot open a file, read the clock, or print a
line. For each of those it must **import** a function by name, and the page must supply that function when it starts
the module. If the page does not supply it, the module does not start.

**Exports.** The functions (and memory) the module offers back. The page's JavaScript calls them like ordinary
functions.

<figure class="mars-fig wide" markdown="0">
<svg viewBox="0 0 660 230" role="img" aria-label="A browser tab. Inside it, the page's JavaScript on the left and a WebAssembly instance on the right. The instance holds its compiled code and its linear memory, one block of bytes. Arrows: JavaScript calls the instance's exports; the instance calls only the functions JavaScript handed it as imports. Nothing goes from the instance to the computer directly.">
<g font-size="13" fill="currentColor">
<rect x="6" y="6" width="648" height="218" rx="10" stroke="currentColor" fill="none" stroke-dasharray="5 4"/>
<text x="18" y="26" font-weight="bold">one browser tab</text>
<rect x="30" y="50" width="200" height="150" rx="8" class="soft" stroke="currentColor"/>
<text x="130" y="74" text-anchor="middle" font-weight="bold">page JavaScript</text>
<text x="130" y="100" text-anchor="middle" font-size="12">the "glue" code</text>
<text x="130" y="122" text-anchor="middle" font-size="12">file system in memory,</text>
<text x="130" y="138" text-anchor="middle" font-size="12">clock, random numbers,</text>
<text x="130" y="154" text-anchor="middle" font-size="12">console output</text>
<rect x="400" y="50" width="230" height="150" rx="8" class="soft-acc"/>
<text x="515" y="74" text-anchor="middle" font-weight="bold">WebAssembly instance</text>
<rect x="420" y="88" width="190" height="40" rx="4" stroke="currentColor" fill="none"/>
<text x="515" y="113" text-anchor="middle" font-size="12">compiled code (PostgreSQL)</text>
<rect x="420" y="140" width="190" height="44" rx="4" stroke="currentColor" fill="none"/>
<text x="515" y="158" text-anchor="middle" font-size="12">linear memory</text>
<text x="515" y="175" text-anchor="middle" font-size="11">one ArrayBuffer, ~190 MB</text>
<g stroke="currentColor" fill="none" stroke-width="1.5"><path d="M232 90 L396 90"/><path d="M396 160 L232 160"/></g>
<path d="M396 90 l-8 -4 v8 z M232 160 l8 -4 v8 z" fill="currentColor"/>
<text x="314" y="82" text-anchor="middle" font-size="12">calls exports</text>
<text x="314" y="106" text-anchor="middle" font-size="11">pgl_startPGlite ...</text>
<text x="314" y="152" text-anchor="middle" font-size="12">calls imports</text>
<text x="314" y="176" text-anchor="middle" font-size="11">openat, clock, random ...</text>
</g>
</svg>
<figcaption>The module can only compute inside its own memory and call what it was handed. Everything else goes through JavaScript.</figcaption>
</figure>

## 1.4 The same ideas in server terms

If you run Linux servers, you already know each piece under another name.

| WebAssembly | On a Linux server | Note |
| --- | --- | --- |
| `.wasm` module | an ELF binary | for a CPU called `wasm32`, which every browser emulates by compiling |
| the browser's wasm engine | the CPU plus the program loader | checks the file, compiles it, starts it |
| linear memory | the process's address space | but one flat block, and nothing outside it can be addressed |
| imports | system calls | only the ones the page supplies, like a strict seccomp allow-list |
| JavaScript glue | libc plus a small kernel | turns "open this file" into something the browser can do |
| in-memory file system | `tmpfs` | gone when the tab closes, unless saved somewhere (chapter 5) |
| `.data` file | a disk image or container layer | the files the program expects to find at start |

There is no `fork`, no other processes, no threads unless the page sets them up specially, and no network sockets of
its own. Chapter 6 shows what that means for a database.

## 1.5 How fast

Fast enough for a playground. One measurement, the same query on the same 4-core cloud machine:

```sql
SELECT count(*) FROM generate_series(1, 20000000);
```

| Where | Time (warm runs) |
| --- | --- |
| PostgreSQL 16, native, no parallel workers | 2.3 s |
| PGlite 0.5.16 (PostgreSQL 18.6) in Node.js 22 | 5.5 to 5.9 s |
| PGlite 0.5.16 in Chromium 153 | 5.4 s (one run) |

So about two and a half times slower than the native server on this one query. The versions differ (16 against 18)
and other queries will give other ratios; the course's practice tables have tens of rows, where every query answers
in milliseconds.

WebAssembly also runs outside browsers (Node.js, Deno, Cloudflare Workers, standalone runtimes such as wasmtime),
which is how the same PGlite package was tested in Node.js here.

## 1.6 Read more

- MDN, [WebAssembly concepts](https://developer.mozilla.org/en-US/docs/WebAssembly/Guides/Concepts)
- The [WebAssembly specification](https://webassembly.github.io/spec/core/)
- [PGlite](https://pglite.dev/), the PostgreSQL build used here

Next: [2. Inside a .wasm file, byte by byte](02-Inside-a-wasm-File.md).

# 7. Build your own playground

*A SQL playground is a text box, a Run button, a result table, and a database that already has the right tables and
rows in it when the page opens. This chapter builds one in about 40 lines and then shows the three ways to preload the
data: run a seed SQL file at start, load a ready-made snapshot, or keep the visitor's own database between visits.
Every example was run in Chromium 153 with PGlite 0.5.16.*

!!! abstract "In this chapter"
    - a complete playground page: Run, Reset, errors
    - way 1, a seed `.sql` file: the best choice for learning
    - way 2, a snapshot made with `dumpDataDir()`: for large data
    - way 3, a database saved in IndexedDB: for work that should survive a reload
    - presets: several datasets, schemas, a read-only role, generated rows

## 7.1 Three ways to start with data

| Way | Download | Start time (measured) | Best for |
| --- | --- | --- | --- |
| seed SQL run at start | the `.sql` file: 5.8 KB for the course's [shop.sql](../../databases/sql/sample-database.md) | 2.1 s (fresh `initdb` + 24 ms of SQL) | lessons, practice tasks, anything up to a few thousand rows |
| snapshot (`loadDataDir`) | a `.tar.gz` of the whole data folder: **4.6 MB** for the same tables | 0.5 to 0.7 s | large data that would take long to insert |
| saved in IndexedDB | nothing extra after the first visit | 1.05 s on later visits | a scratch database that should keep the visitor's changes |

The PGlite files themselves (chapter 4) are the same 16 MB in every case, cached after the first visit.

## 7.2 Way 1: a seed SQL file

The whole page. It needs the PGlite `dist/` files copied to a folder `pglite/` next to it, and the seed file
`shop.sql`:

```html
<!doctype html>
<meta charset="utf-8">
<textarea id="sql">SELECT city, count(*) AS customers
FROM customers
GROUP BY city
ORDER BY customers DESC, city;</textarea>
<button id="run">Run</button> <button id="reset">Reset</button>
<pre id="out">starting PostgreSQL…</pre>
<script type="module">
  import { PGlite } from './pglite/index.js';

  const out = document.getElementById('out');
  const seed = await (await fetch('shop.sql')).text();   // the tables and rows every visitor starts with
  let db;

  async function fresh() {
    if (db) await db.close();
    db = await PGlite.create();       // a new, empty database in memory
    await db.exec(seed);              // CREATE TABLE ... ; INSERT ... ;
    out.textContent = 'ready';
  }

  async function run() {
    try {
      const results = await db.exec(document.getElementById('sql').value);
      const last = results.at(-1);     // one result per statement; show the last
      out.textContent = last.fields.map(f => f.name).join(' | ') + '\n' +
        last.rows.map(r => Object.values(r).join(' | ')).join('\n');
    } catch (e) {
      out.textContent = 'ERROR: ' + e.message;
    }
  }

  document.getElementById('run').onclick = run;
  document.getElementById('reset').onclick = fresh;
  await fresh();
</script>
```

What it showed after pressing Run:

```text
city | customers
Toronto | 3
Lagos | 1
Lisbon | 1
Osaka | 1
Prague | 1
Seoul | 1
Shanghai | 1
 | 1
```

(The last row is the customer whose city is NULL; a real playground would print `NULL` and draw a table.) Typing
`SELEC 1` showed `ERROR: syntax error at or near "SELEC"`, and after Reset, `SELECT count(*) FROM customers` gave 10
again whatever had been deleted before.

Three things to know about seed files:

- **`exec` runs the whole text as one implicit transaction.** If any statement fails, none of them stays: after
  `exec('CREATE TABLE a (x int); INSERT INTO a VALUES (1); SELECT 1/0')` failed with `division by zero`, table `a`
  did not exist. And
  statements that cannot run inside a transaction must go in their own `exec` call: `exec('CREATE TABLE ...; VACUUM')`
  failed with `VACUUM cannot run inside a transaction block`, while `exec('VACUUM')` alone worked.
- **It is plain PostgreSQL.** Anything `psql -f seed.sql` accepts as SQL works, except `psql`'s own backslash commands
  (`\copy`, `\i`), which belong to `psql`, not to the server.
- **Results are shown with `textContent`**, never as HTML ([chapter 6.5](06-Is-It-Safe.md#65-the-risks-that-remain)).

## 7.3 A prebuilt snapshot, for large data

Instead of inserting the rows at every visit, insert them once, on your own computer, and ship PostgreSQL's data
folder. Make it with Node.js (`npm install @electric-sql/pglite@0.5.16` first, the same version the page uses):

```js
// make-snapshot.mjs: run once with Node.js, next to shop.sql
import { PGlite } from '@electric-sql/pglite';
import fs from 'node:fs';

const db = await PGlite.create();                       // a new database, in memory
await db.exec(fs.readFileSync('shop.sql', 'utf8'));     // your tables and rows
const snapshot = await db.dumpDataDir('gzip');          // the whole data folder as a .tar.gz
fs.writeFileSync('shop.tar.gz', Buffer.from(await snapshot.arrayBuffer()));
await db.close();
console.log('wrote shop.tar.gz,', snapshot.size, 'bytes');
```

```text
wrote shop.tar.gz, 4597997 bytes
```

Then the page starts from it:

```html
<script type="module">
  import { PGlite } from './pglite/index.js';
  const snapshot = await (await fetch('shop.tar.gz')).blob();      // made once with dumpDataDir()
  const db = await PGlite.create({ loadDataDir: snapshot });      // starts with the tables already there
  const r = await db.query('SELECT count(*)::int AS n FROM orders');
</script>
```

It started, with all 20 orders, in 0.47 to 0.71 s over several runs, against about 2.1 s for a fresh database plus
seed. The price is the size: the archive is the **whole cluster**, 1,009 files, 40.6 MB unpacked (three databases of
about 7 MB each, mostly system catalogs, and a 16 MB write-ahead-log segment), 4.6 MB compressed, whether the tables
hold 50 rows or 50,000. So:

- for lesson-sized data, a seed file is almost 800 times smaller and only about 1.5 s slower to start;
- for data that takes many seconds to insert, a snapshot wins;
- make the snapshot with the **same PGlite version** the page loads; whether another version can read it was not
  tested here.

## 7.4 Keeping the visitor's changes

Give the database an IndexedDB address and seed it only on the first visit:

```html
<script type="module">
  import { PGlite } from './pglite/index.js';
  const db = await PGlite.create('idb://sql-playground');   // kept in IndexedDB
  const { rows } = await db.query("SELECT to_regclass('public.customers') IS NOT NULL AS seeded");
  if (!rows[0].seeded) {
    await db.exec(await (await fetch('shop.sql')).text());     // only on the first visit
  }
</script>
```

In the test, the first visit seeded the tables and added one row (11 customers); the second visit found the tables,
skipped the seed, and added another (12 customers). To start over, delete the saved database
(`indexedDB.deleteDatabase('/pglite/sql-playground')`, see [chapter 5.8](05-Where-Everything-Is-Kept.md#58-seeing-and-clearing-them-in-devtools))
and reload.

## 7.5 Presets: datasets, schemas, roles, generated rows

All of these are ordinary PostgreSQL, run in the seed, and all were tested in PGlite 0.5.16.

**One seed per lesson.** Keep several small files (`shop.sql`, `hr.sql`, `sensors.sql`) and let each page say which
one it loads, for example with an attribute on the box: `<div class="playground" data-seed="hr.sql">`.

**Several datasets in one database: schemas.**

```sql
CREATE SCHEMA hr;
CREATE TABLE hr.staff (id int PRIMARY KEY, name text, team text);
INSERT INTO hr.staff VALUES (1, 'Ana', 'data'), (2, 'Ben', 'web');
SET search_path = hr, public;
SELECT count(*) AS staff FROM staff;      -- 2: "staff" is found in hr
```

**A read-only learner.** Create a role that can only read, and switch to it at the end of the seed:

```sql
CREATE ROLE learner;
GRANT USAGE ON SCHEMA public TO learner;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO learner;
SET ROLE learner;
```

| Then | Result |
| --- | --- |
| `SELECT count(*) FROM customers` | 10 |
| `DELETE FROM customers` | `permission denied for table customers` |
| `DROP TABLE orders` | `must be owner of table orders` |
| `RESET ROLE; SELECT current_user` | `postgres` |

The last row shows its limit: the visitor can switch back, because the session itself belongs to the superuser. It
protects against accidents, not against someone who means it; the Reset button is the real safety net, and nothing
outside the tab is at risk anyway (chapter 6).

**Many rows without a big file.** Generate them in the seed, with a fixed random seed so every visitor gets the same
"random" data:

```sql
SELECT setseed(0.42);
CREATE TABLE sales AS
SELECT g AS sale_id,
       DATE '2026-01-01' + (g % 365) AS sale_date,
       (ARRAY['Toronto','Lisbon','Osaka','Lagos'])[1 + floor(random() * 4)::int] AS city,
       round((random() * 100)::numeric, 2) AS amount
FROM generate_series(1, 100000) AS g;
```

That made 100,000 rows over 4 cities from 2026-01-01 to 2026-12-31, from under 300 bytes of SQL. Running
`SELECT setseed(0.42)` and then three `random()` cities twice gave `Osaka, Lisbon, Lagos` both times.

## 7.6 Ideas for a fuller playground

- **A Check button:** run the visitor's query and the model answer, and compare the two lists of rows.
- **One database for the whole page,** shared by every run box on it (each instance holds about 190 MB).
- **A results table** built cell by cell, with `NULL` shown as `NULL`.
- **Run with Ctrl+Enter** in the text box, and a short message with the row count and time.
- **A Web Worker** (`PGliteWorker`), if long queries should not freeze the page.

## 7.7 The playground on this site

The **Run this** buttons on the [SQL course](../../databases/sql/index.md) pages and the **Try it** boxes in the
[Codility practice](../../interview/codility/index.md) are built the way this chapter describes. What is really there
(read from the site's repository and checked on the live site on 12 November 2026):

| Part | What it is |
| --- | --- |
| [`/assets/pglite/`](https://github.com/TTMathCS/it/tree/main/docs/assets/pglite) | PGlite **0.5.10**, copied unchanged from the npm tarball: `pglite.wasm` (10,498,455 bytes), `pglite.data` (6,248,214), `initdb.wasm` (300,129), `index.js` and 7 chunks (2,057,065 together; in this version the glue is inside `index.js`) |
| [`PROVENANCE.txt`](https://github.com/TTMathCS/it/blob/main/docs/assets/pglite/PROVENANCE.txt) | the version, source address, the registry's SHA-512 (matched), a SHA-256 for every file, and the licence |
| [`sql-play.js`](https://github.com/TTMathCS/it/blob/main/docs/javascripts/sql-play.js) | the playground: loads PGlite only when a Run button is first pressed, **one database per page**, shared by every box |
| the seed | `shop.sql` for the course pages; each practice task's own tables for the Codility pages |
| a clean start for every run | each run is `BEGIN`, drop and re-create the `public` schema, run the seed, run your query, `ROLLBACK`: whatever you change is undone, so every run sees the same data |
| the security policy | a `Content-Security-Policy` in every page that allows `'wasm-unsafe-eval'` and loads scripts only from this site and www.akadian.ca |

Measured on the live site from a cloud machine with Chromium 153: GitHub Pages sends the `.wasm` files as
`application/wasm` and compresses all four big files with gzip (3.7 MB, 1.8 MB, 0.13 MB and 0.29 MB on the wire,
about 6 MB in all). The first Run on a page answered after **4.0 to 4.5 s**, downloads included, and its requests went
only to it.akadian.ca (the PGlite files and `shop.sql`). The second Run answered in **0.26 s** with **no** requests.

And here is one, loaded with the shop database. Try `SELECT version();`, or open your browser's Network panel before
the first Run and watch the files of chapter 4 arrive:

<div class="sqlplay-free" data-db="shop"></div>

Back to [the course page](index.md) · the SQL to try in a playground: [the SQL course](../../databases/sql/index.md).

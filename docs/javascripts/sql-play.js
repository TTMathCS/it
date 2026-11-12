/* SQL playground: a real PostgreSQL (PGlite, Apache-2.0, self-hosted in assets/pglite/) running in the browser.
 *
 * 1. Codility practice pages: every SQL task (a heading followed by "Tables" and "Your query should return") gets a
 *    "Try it here" box loaded with that task's tables and example rows, with Run and Check.
 * 2. SQL course pages (/databases/sql/): every SQL example gets a "Run" button that opens a box under it, loaded
 *    with the course's sample shop database (shop.sql).
 * 3. Any page with <div class="sqlplay-free" data-db="shop|empty"></div> gets a free playground.
 *
 * PostgreSQL itself (about 5 MB to download) is loaded only when a box is first run, once per page.
 * Each run happens inside a transaction that is rolled back, so the tables are always back to the start.
 */
(function () {
  "use strict";
  var ROOT = (function () {
    var s = document.currentScript && document.currentScript.src;
    return s ? s.replace(/javascripts\/sql-play\.js.*$/, "") : "/";
  })();
  var dbPromise = null;
  var shopSql = null;
  var MAX_ROWS = 200;
  // every run starts from an empty database, even if an earlier run committed something
  var CLEAN = "DROP SCHEMA IF EXISTS public CASCADE;\nCREATE SCHEMA public;\nGRANT ALL ON SCHEMA public TO PUBLIC;\nSET search_path TO public;\n";

  function getDb() {
    if (!dbPromise) {
      dbPromise = import(ROOT + "assets/pglite/index.js").then(function (m) {
        return m.PGlite.create();
      });
      dbPromise.catch(function () { dbPromise = null; });
    }
    return dbPromise;
  }

  function getShop() {
    if (!shopSql) {
      shopSql = fetch(ROOT + "databases/sql/shop.sql").then(function (r) {
        if (!r.ok) throw new Error("could not load shop.sql");
        return r.text();
      });
      shopSql.catch(function () { shopSql = null; });
    }
    return shopSql;
  }

  // every value comes back as the text PostgreSQL prints, so dates and numbers look as they do in psql
  var TEXT = function (x) { return x; };
  var PARSERS = { 20: TEXT, 21: TEXT, 23: TEXT, 700: TEXT, 701: TEXT, 1700: TEXT, 1082: TEXT, 1083: TEXT,
    1114: TEXT, 1184: TEXT, 1186: TEXT, 16: TEXT, 114: TEXT, 3802: TEXT, 1009: TEXT, 1007: TEXT, 1016: TEXT };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function store(key, val) {
    try {
      if (val === undefined) return window.localStorage.getItem(key);
      if (val === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, val);
    } catch (e) { return null; }
    return null;
  }

  function quote(v) { return "'" + String(v).replace(/'/g, "''") + "'"; }

  function tableNames(ddl) {
    var out = [], re = /CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?("?[\w.]+"?)/gi, m;
    while ((m = re.exec(ddl))) out.push(m[1]);
    return out;
  }

  function show(out, res, ms) {
    out.innerHTML = "";
    var last = null;
    for (var i = res.length - 1; i >= 0; i--) {
      if (res[i].fields && res[i].fields.length) { last = res[i]; break; }
    }
    if (!last) {
      var aff = res.length ? res[res.length - 1].affectedRows : 0;
      out.appendChild(el("p", "sqlplay-note", "Done in " + ms + " ms" + (aff ? ", " + aff + " rows changed." : ". No rows to show.")));
      return null;
    }
    var rows = last.rows;
    var wrap = el("div", "sqlplay-table");
    var t = el("table");
    var hr = el("tr");
    last.fields.forEach(function (f) { hr.appendChild(el("th", null, f.name)); });
    var th = el("thead"); th.appendChild(hr); t.appendChild(th);
    var tb = el("tbody");
    rows.slice(0, MAX_ROWS).forEach(function (r) {
      var tr = el("tr");
      r.forEach(function (v) {
        var td = el("td", v === null ? "sqlplay-null" : null, v === null ? "NULL" : (typeof v === "object" ? JSON.stringify(v) : String(v)));
        tr.appendChild(td);
      });
      tb.appendChild(tr);
    });
    t.appendChild(tb); wrap.appendChild(t);
    out.appendChild(el("p", "sqlplay-note", rows.length + (rows.length === 1 ? " row" : " rows") + " in " + ms + " ms" +
      (rows.length > MAX_ROWS ? " (first " + MAX_ROWS + " shown)" : "")));
    out.appendChild(wrap);
    return { cols: last.fields.map(function (f) { return f.name; }), rows: rows };
  }

  function showError(out, e) {
    out.innerHTML = "";
    var msg = (e && e.message) ? e.message : String(e);
    var p = el("p", "sqlplay-error", "ERROR: " + msg);
    out.appendChild(p);
    if (e && e.hint) out.appendChild(el("p", "sqlplay-note", "Hint: " + e.hint));
  }

  // ---- comparing a result with the expected table
  function normCell(v) {
    if (v === null || v === undefined) return null;
    var s = String(v).trim();
    if (s === "NULL" || s === "") return null;   // a hand-written table sometimes leaves a NULL cell empty
    if (/^(t|true)$/i.test(s)) return "true";
    if (/^(f|false)$/i.test(s)) return "false";
    if (/^[-+]?\d+(\.\d+)?$/.test(s)) return parseFloat(s);
    return s;
  }
  function same(a, b) {
    a = normCell(a); b = normCell(b);
    if (typeof a === "number" && typeof b === "number") return Math.abs(a - b) < 1e-4;
    return a === b;
  }
  function rowKey(r) {
    return JSON.stringify(r.map(function (v) { var n = normCell(v); return typeof n === "number" ? Math.round(n * 10000) / 10000 : n; }));
  }
  function compare(got, exp, unordered) {
    if (unordered && got.cols.length === exp.cols.length && got.rows.length === exp.rows.length) {
      // the task asks for no order: compare the rows as a set (with repeats)
      var a = got.rows.map(rowKey).sort(), b = exp.rows.map(rowKey).sort();
      var k = 0;
      while (k < a.length && a[k] === b[k]) k++;
      if (k === a.length) {
        var nm = got.cols.filter(function (c, i) { return c !== exp.cols[i]; });
        return nm.length ? "names" : "";
      }
      return "Some rows differ from the expected result (the order does not matter here). Look at the rows with " +
        "NULLs, ties and the edges of your filters.";
    }
    if (got.cols.length !== exp.cols.length)
      return "Your result has " + got.cols.length + " column(s); the expected result has " + exp.cols.length +
        " (" + exp.cols.join(", ") + ").";
    if (got.rows.length !== exp.rows.length)
      return "Your result has " + got.rows.length + " row(s); the expected result has " + exp.rows.length + ".";
    for (var i = 0; i < exp.rows.length; i++) {
      for (var j = 0; j < exp.cols.length; j++) {
        if (!same(got.rows[i][j], exp.rows[i][j])) {
          var sameSet = exp.rows.some(function (r) {
            return r.every(function (c, k) { return same(got.rows[i][k], c); });
          });
          return "Row " + (i + 1) + ", column " + (j + 1) + " (" + exp.cols[j] + "): you have " +
            fmt(got.rows[i][j]) + ", expected " + fmt(exp.rows[i][j]) + "." +
            (sameSet ? " That row does appear in the expected result: check the ORDER BY." : "");
        }
      }
    }
    var names = got.cols.map(function (c, k) { return c === exp.cols[k] ? null : c; }).filter(Boolean);
    return names.length ? "names" : "";
  }
  function fmt(v) { return v === null ? "NULL" : JSON.stringify(String(v)); }

  // ---- reading a task from the page
  function htmlTable(t) {
    var cols = [], rows = [];
    t.querySelectorAll("thead th").forEach(function (th) { cols.push(th.textContent.trim()); });
    t.querySelectorAll("tbody tr").forEach(function (tr) {
      var r = [];
      tr.querySelectorAll("td").forEach(function (td) { r.push(td.textContent.trim()); });
      // a marker comment inside an answer box can turn into an empty last row: leave it out
      if (r.some(function (v) { return v !== ""; })) rows.push(r);
    });
    return { cols: cols, rows: rows };
  }
  function tableAfter(node, stop) {
    // the first <table> (or "(no rows)") after node, before stop
    for (var n = node.nextElementSibling; n && n !== stop; n = n.nextElementSibling) {
      var t = n.tagName === "TABLE" ? n : n.querySelector && n.querySelector("table");
      if (t) return t;
      if (/^\(no rows\)$/.test(n.textContent.trim())) return "none";
      if (/^H[1-4]$/.test(n.tagName) || (n.tagName === "DETAILS")) return null;
    }
    return null;
  }
  function codeAfter(node) {
    for (var n = node.nextElementSibling; n; n = n.nextElementSibling) {
      var c = n.querySelector && n.querySelector("pre code");
      if (c) return c.textContent;
      if (/^H[1-4]$/.test(n.tagName)) return null;
    }
    return null;
  }

  function readTask(h) {
    var nodes = [], n = h.nextElementSibling;
    while (n && !/^H[1-3]$/.test(n.tagName)) { nodes.push(n); n = n.nextElementSibling; }
    var stop = n;
    var ddl = null, inserts = [], expected = null, solution = null;
    nodes.forEach(function (p) {
      if (p.tagName === "DETAILS" && !solution) solution = p;
      if (p.tagName !== "P") return;
      var s = p.textContent.trim();
      if (/^Tables( and example data)?$/.test(s) && ddl === null) ddl = codeAfter(p);
      var code = p.querySelector("code");
      if (code && s === code.textContent.trim() && /^[A-Za-z_][\w]*$/.test(s) && ddl !== null && expected === null) {
        var t = tableAfter(p, stop);
        if (t && t !== "none") {
          var d = htmlTable(t);
          d.rows.forEach(function (r) {
            inserts.push("INSERT INTO " + s + " (" + d.cols.join(", ") + ") VALUES (" +
              r.map(function (v) { return v === "NULL" ? "NULL" : quote(v); }).join(", ") + ");");
          });
        }
      }
      if (/^Your query should return$/.test(s)) {
        var e = tableAfter(p, stop);
        if (e === "none") expected = { cols: [], rows: [], none: true };
        else if (e) expected = htmlTable(e);
      }
    });
    if (!ddl || !expected) return null;
    if (expected.none) {
      // the header of an empty expected table is still shown on the page
      var tb = null;
      nodes.forEach(function (p) { if (/^Your query should return$/.test(p.textContent.trim())) tb = p; });
      var t2 = tb && tb.nextElementSibling && tb.nextElementSibling.tagName === "TABLE" ? tb.nextElementSibling : null;
      if (t2) expected.cols = htmlTable(t2).cols;
    }
    return { setup: ddl + "\n" + inserts.join("\n"), names: tableNames(ddl), expected: expected, solution: solution };
  }

  // ---- one box
  function makeBox(opts) {
    var box = el("div", "sqlplay");
    var head = el("div", "sqlplay-head");
    head.appendChild(el("span", "sqlplay-title", opts.title || "Try it here"));
    head.appendChild(el("span", "sqlplay-sub", opts.sub || "PostgreSQL in your browser"));
    box.appendChild(head);
    var ta = el("textarea", "sqlplay-edit");
    ta.spellcheck = false;
    ta.setAttribute("autocapitalize", "off");
    ta.setAttribute("autocomplete", "off");
    ta.setAttribute("aria-label", "SQL query");
    var saved = opts.key ? store(opts.key) : null;
    ta.value = saved != null ? saved : (opts.start || "");
    ta.rows = Math.min(16, Math.max(5, ta.value.split("\n").length + 1));
    box.appendChild(ta);
    var bar = el("div", "sqlplay-bar");
    var run = el("button", "md-button md-button--primary sqlplay-run", "Run");
    run.type = "button";
    run.title = "Run (Ctrl+Enter or Cmd+Enter)";
    bar.appendChild(run);
    var check = null;
    if (opts.expected) {
      check = el("button", "md-button sqlplay-check", "Check");
      check.type = "button";
      check.title = "Run and compare with the expected result";
      bar.appendChild(check);
    }
    var tables = null;
    if (opts.names && opts.names.length) {
      tables = el("button", "md-button sqlplay-tables", "Show tables");
      tables.type = "button";
      bar.appendChild(tables);
    }
    var reset = el("button", "md-button sqlplay-reset", "Reset");
    reset.type = "button";
    reset.title = "Put back the starting text";
    bar.appendChild(reset);
    var status = el("span", "sqlplay-status", "");
    bar.appendChild(status);
    box.appendChild(bar);
    var verdict = el("div", "sqlplay-verdict");
    box.appendChild(verdict);
    var out = el("div", "sqlplay-out");
    box.appendChild(out);
    if (opts.help) box.appendChild(el("p", "sqlplay-help", opts.help));

    var busy = false;
    function exec(sql) {
      if (busy) return Promise.resolve(null);
      busy = true;
      run.disabled = true; if (check) check.disabled = true;
      var first = !dbPromise;
      status.textContent = first ? "Starting PostgreSQL (first time on this page: a few seconds)..." : "Running...";
      var setupP = opts.shop ? getShop() : Promise.resolve(opts.setup || "");
      var extraP = opts.extra ? opts.extra() : Promise.resolve("");
      return Promise.all([getDb(), setupP, extraP]).then(function (a) {
        var db = a[0], setup = a[1] + "\n" + a[2];
        var t0 = performance.now();
        return db.exec("BEGIN;").then(function () {
          return db.exec(CLEAN + setup);
        }).then(function () {
          t0 = performance.now();
          return db.exec(sql, { rowMode: "array", parsers: PARSERS });
        }).then(function (res) {
          var ms = Math.round(performance.now() - t0);
          return db.exec("ROLLBACK;").then(function () { return { res: res, ms: ms }; });
        }, function (err) {
          return db.exec("ROLLBACK;").then(function () { throw err; }, function () { throw err; });
        });
      }).then(function (r) {
        status.textContent = "";
        return show(out, r.res, r.ms);
      }, function (err) {
        status.textContent = "";
        showError(out, err);
        return null;
      }).then(function (x) {
        busy = false; run.disabled = false; if (check) check.disabled = false;
        return x;
      });
    }
    function save() { if (opts.key) store(opts.key, ta.value === opts.start ? null : ta.value); }
    run.addEventListener("click", function () { verdict.innerHTML = ""; save(); exec(ta.value); });
    if (check) check.addEventListener("click", function () {
      save();
      verdict.innerHTML = "";
      exec(ta.value).then(function (got) {
        if (!got) {
          verdict.appendChild(el("p", "sqlplay-bad", "Not yet: your query did not return rows."));
          return;
        }
        var why = compare(got, opts.expected, opts.unordered);
        if (why === "" || why === "names") {
          verdict.appendChild(el("p", "sqlplay-good", "Matches the expected result on the example rows" +
            (why === "names" ? " (values and order match; some column names differ from the task's, so use the task's names)." : ".") +
            " The hidden tests use other data: add edge-case rows (INSERT before your SELECT) and check it still holds."));
        } else {
          verdict.appendChild(el("p", "sqlplay-bad", "Not yet. " + why));
        }
      });
    });
    if (tables) tables.addEventListener("click", function () {
      if (busy) return;
      busy = true;
      verdict.innerHTML = "";
      status.textContent = dbPromise ? "Running..." : "Starting PostgreSQL (first time on this page: a few seconds)...";
      getDb().then(function (db) {
        var rs = [];
        return db.exec("BEGIN;").then(function () {
          return db.exec(CLEAN + opts.setup);
        }).then(function () {
          return opts.names.reduce(function (pr, n) {
            return pr.then(function () {
              return db.query("SELECT * FROM " + n, [], { rowMode: "array", parsers: PARSERS }).then(function (r) { rs.push(r); });
            });
          }, Promise.resolve());
        }).then(function () {
          return db.exec("ROLLBACK;").then(function () { return rs; });
        }, function (err) {
          return db.exec("ROLLBACK;").then(function () { throw err; }, function () { throw err; });
        });
      }).then(function (rs) {
        out.innerHTML = "";
        rs.forEach(function (r, i) {
          out.appendChild(el("p", "sqlplay-tname", opts.names[i] + " (" + r.rows.length + (r.rows.length === 1 ? " row)" : " rows)")));
          var holder = el("div");
          out.appendChild(holder);
          show(holder, [r], 0);
          holder.querySelectorAll(".sqlplay-note").forEach(function (x) { x.remove(); });
        });
      }, function (e) { showError(out, e); }).then(function () { busy = false; status.textContent = ""; });
    });
    reset.addEventListener("click", function () {
      ta.value = opts.start || ""; save(); out.innerHTML = ""; verdict.innerHTML = "";
    });
    ta.addEventListener("keydown", function (e) {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); run.click(); return; }
      if (e.key === "Tab" && !e.shiftKey) {
        e.preventDefault();
        var s = ta.selectionStart;
        ta.value = ta.value.slice(0, s) + "    " + ta.value.slice(ta.selectionEnd);
        ta.selectionStart = ta.selectionEnd = s + 4;
      }
    });
    ta.addEventListener("input", function () {
      var lines = ta.value.split("\n").length + 1;
      if (lines > ta.rows && lines <= 30) ta.rows = lines;
    });
    var timer = null;
    ta.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(save, 600); });
    return box;
  }

  // ---- wiring the page
  function practicePage(content) {
    var path = location.pathname.replace(/\.html$/, "");
    content.querySelectorAll("h2, h3").forEach(function (h) {
      var task = readTask(h);
      if (!task) return;
      var start = "-- Write your query here. Ctrl+Enter (Cmd+Enter on a Mac) runs it.\n" +
        "-- The tables hold the example rows above; every run starts from them again.\n\nSELECT *\nFROM " +
        (task.names[0] || "") + ";\n";
      var box = makeBox({
        start: start, setup: task.setup, names: task.names, expected: task.expected,
        key: "sqlplay:" + path + "#" + (h.id || h.textContent),
        help: "Your edge cases: write INSERT, UPDATE or DELETE statements before your SELECT, separated by ;" +
          " and only the last result is shown and checked."
      });
      if (task.solution) task.solution.parentNode.insertBefore(box, task.solution);
    });
  }

  // the course marks each example with <!-- sql flags --> (tools/sqlrun.py): "sqlite" alone = SQLite only (no box);
  // "setup", "keep" and "raw" blocks stay for the rest of the page, so a later example runs after them.
  function sqlMarks(root) {
    var out = [], w = document.createTreeWalker(root, NodeFilter.SHOW_COMMENT), c;
    while ((c = w.nextNode())) {
      var m = /^\s*sql((?: [a-z]+)*)\s*$/.exec(c.data);
      if (!m) continue;
      var n = c.nextSibling;
      while (n && n.nodeType !== 1) n = n.nextSibling;
      // inside an answer box the marker ends up alone in a <p>, and the code block comes after that <p>
      if (!n && c.parentNode && c.parentNode.tagName === "P") n = c.parentNode.nextElementSibling;
      var code = n && n.querySelector && n.querySelector("pre code");
      if (!code) continue;
      var f = m[1].trim().split(/\s+/);
      out.push({ div: n, code: code.textContent.replace(/\s+$/, ""),
        pg: f.indexOf("sqlite") < 0 || f.indexOf("pg") >= 0,
        kept: (f.indexOf("setup") >= 0 || f.indexOf("keep") >= 0 || f.indexOf("raw") >= 0) &&
          f.indexOf("error") < 0 && f.indexOf("pgerror") < 0 });
    }
    return out;
  }
  var fullPage = null;
  function wholePageMarks() {
    // the reader shows long chapters in parts, so read the whole page once to know every earlier "kept" block
    if (!fullPage) {
      fullPage = fetch(location.pathname).then(function (r) { return r.text(); }).then(function (html) {
        var d = new DOMParser().parseFromString(html, "text/html");
        return sqlMarks(d.querySelector("article") || d.body);
      });
      fullPage.catch(function () { fullPage = null; });
    }
    return fullPage;
  }
  function prelude(code) {
    return wholePageMarks().then(function (all) {
      var pre = [];
      for (var i = 0; i < all.length; i++) {
        if (all[i].code === code) break;
        if (all[i].kept && all[i].pg) pre.push(all[i].code);
      }
      return pre.join(";\n") + (pre.length ? ";\n" : "");
    });
  }

  // an exercise: a <details> "Answer" whose first runnable block is followed by its real result table
  function topLevelOrderBy(sql) {
    var depth = 0, flat = "";
    for (var i = 0; i < sql.length; i++) {
      var c = sql[i];
      if (c === "(") depth++;
      else if (c === ")") depth--;
      else if (depth === 0) flat += c;
    }
    return /\border\s+by\b/i.test(flat.replace(/--[^\n]*/g, ""));
  }
  function exerciseBoxes(content, marks) {
    content.querySelectorAll("details").forEach(function (d) {
      var sum = d.querySelector("summary");
      if (!sum || !/^(Answer|Solution)/.test(sum.textContent.trim())) return;
      var b = null;
      for (var i = 0; i < marks.length; i++) if (d.contains(marks[i].div) && marks[i].pg) { b = marks[i]; break; }
      if (!b || b.div.parentNode !== d) return;
      var t = null;
      for (var n = b.div.nextElementSibling; n; n = n.nextElementSibling) {
        if (n.tagName === "TABLE") { t = n; break; }
        if (n.querySelector && n.querySelector("table")) { t = n.querySelector("table"); break; }
        if (n.querySelector && n.querySelector("pre code")) return;
      }
      if (!t) return;
      var exp = htmlTable(t);
      if (exp.rows.length === 1 && /no rows/.test(exp.rows[0].join(" "))) exp.rows = [];
      var path = location.pathname.replace(/\.html$/, "");
      var box = makeBox({ title: "Try it here", sub: "PostgreSQL in your browser, with the shop database",
        start: "-- Your answer here. Ctrl+Enter (Cmd+Enter on a Mac) runs it.\n\n", shop: true,
        extra: function () { return prelude(b.code); }, expected: exp, unordered: !topLevelOrderBy(b.code),
        key: "sqlplay:" + path + "#" + (d.previousElementSibling ? d.previousElementSibling.textContent.slice(0, 40) : i),
        help: "Check compares your result with the answer's result. Every run starts from the same shop data." });
      d.parentNode.insertBefore(box, d);
    });
  }

  function coursePage(content) {
    var marks = sqlMarks(content);
    exerciseBoxes(content, marks);
    marks.forEach(function (b) {
      if (!b.pg || b.div.closest(".sqlplay")) return;
      var btn = el("button", "md-button sqlplay-open", "Run this \u25b8");
      btn.type = "button";
      btn.title = "Run this example on the sample shop database, and change it";
      var row = el("div", "sqlplay-openrow");
      row.appendChild(btn);
      b.div.parentNode.insertBefore(row, b.div.nextSibling);
      var box = null;
      btn.addEventListener("click", function () {
        if (box) { box.hidden = !box.hidden; btn.textContent = box.hidden ? "Run this \u25b8" : "Hide \u25be"; return; }
        box = makeBox({ title: "Run and change it", sub: "PostgreSQL in your browser, with the shop database",
          start: b.code + "\n", shop: true, extra: function () { return prelude(b.code); },
          help: "Real PostgreSQL with the course's shop database (and any tables this page created above). " +
            "Every run starts from the same data." });
        row.parentNode.insertBefore(box, row.nextSibling);
        btn.textContent = "Hide \u25be";
        box.querySelector(".sqlplay-run").click();
      });
    });
  }

  function freeBoxes(content) {
    content.querySelectorAll("div.sqlplay-free").forEach(function (div) {
      var shop = div.getAttribute("data-db") === "shop";
      var box = makeBox({ title: shop ? "Playground: the shop database" : "Playground: an empty database",
        start: div.getAttribute("data-start") || (shop ? "SELECT * FROM customers;\n" :
          "CREATE TABLE t (id INTEGER, name TEXT);\nINSERT INTO t VALUES (1, 'a'), (2, NULL);\nSELECT * FROM t;\n"),
        shop: shop, key: "sqlplay:free:" + (shop ? "shop" : "empty"),
        help: shop ? "Every run starts from the same shop data; changes are rolled back after each run." :
          "Each run starts from an empty database: create your tables, insert rows and query them in one go." });
      div.appendChild(box);
    });
  }

  function init() {
    var content = document.querySelector("article.md-content__inner") || document.querySelector(".md-content");
    if (!content) return;
    freeBoxes(content);
    if (/\/interview\/codility\//.test(location.pathname)) practicePage(content);
    else if (/\/databases\/sql\//.test(location.pathname) && !/\/databases\/sql\/(glossary|index)\b/.test(location.pathname))
      coursePage(content);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

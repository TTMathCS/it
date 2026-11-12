/* Python run boxes, for the Python practice tasks and the Python tasks of the mock tests only (never on the SQL
 * course pages). Python runs in the browser with Pyodide (self-hosted in assets/pyodide/), inside a Web Worker
 * started only when Run is first pressed (about 6 MB to download, once). A run that takes longer than 15 seconds is
 * stopped. Check runs the task's examples, and the edge cases listed in its solution, against your solution().
 * Shares its look with the SQL boxes (stylesheets/sql-play.css).
 */
(function () {
  "use strict";
  var ROOT = (function () {
    var s = document.currentScript && document.currentScript.src;
    return s ? s.replace(/javascripts\/py-play\.js.*$/, "") : "/";
  })();
  var LIMIT_MS = 15000;
  var worker = null, seq = 0, pending = {}, started = false;

  function startWorker() {
    worker = new Worker(ROOT + "javascripts/py-worker.mjs", { type: "module" });
    worker.onmessage = function (e) {
      var p = pending[e.data.id];
      if (p) { delete pending[e.data.id]; clearTimeout(p.timer); p.resolve(e.data.res); }
    };
    worker.onerror = function (e) {
      Object.keys(pending).forEach(function (k) { pending[k].resolve({ error: "Python could not start: " + (e.message || "unknown error"), tests: [], out: "" }); });
      pending = {};
      worker = null;
    };
  }
  function runPy(code, tests, firstLimit) {
    if (!worker) startWorker();
    var id = ++seq;
    return new Promise(function (resolve) {
      var timer = setTimeout(function () {
        if (!pending[id]) return;
        delete pending[id];
        worker.terminate();
        worker = null;
        started = false;
        resolve({ error: "Stopped after " + Math.round(firstLimit / 1000) + " seconds: the code is too slow or never ends " +
          "(an endless loop?). Python will restart on the next Run.", tests: [], out: "", stopped: true });
      }, firstLimit);
      pending[id] = { resolve: resolve, timer: timer };
      worker.postMessage({ id: id, code: code, tests: tests });
    });
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function store(key, val) {
    try {
      if (val === undefined) return window.localStorage.getItem(key);
      if (val === null) window.localStorage.removeItem(key); else window.localStorage.setItem(key, val);
    } catch (e) { return null; }
    return null;
  }

  // "solution(...) returns X" in a list item, with the call and the value in <code>
  function testsIn(list) {
    var out = [];
    if (!list) return out;
    list.querySelectorAll("li").forEach(function (li) {
      var codes = li.querySelectorAll("code");
      if (codes.length < 2 || !/returns/.test(li.textContent)) return;
      var call = codes[0].textContent.trim(), want = codes[codes.length - 1].textContent.trim();
      if (/^solution\(/.test(call)) out.push([call, want]);
    });
    return out;
  }

  function readTask(h) {
    var nodes = [], n = h.nextElementSibling;
    while (n && !/^H[1-3]$/.test(n.tagName)) { nodes.push(n); n = n.nextElementSibling; }
    var examples = null, start = null, solution = null, sig = null;
    nodes.forEach(function (p, i) {
      if (p.tagName === "DETAILS" && !solution) solution = p;
      if (solution) return;
      if (p.tagName === "P" && /^Examples?$/.test(p.textContent.trim()) && nodes[i + 1] && nodes[i + 1].tagName === "UL")
        examples = testsIn(nodes[i + 1]);
      var code = p.querySelector && p.querySelector("pre code");
      if (code && /\bdef solution\b/.test(code.textContent)) {
        if (/:\s*\n\s+pass\b/.test(code.textContent) || /\n\s+\S/.test(code.textContent)) start = code.textContent.replace(/\s+$/, "") + "\n";
        else sig = code.textContent;
      }
    });
    if (!examples || !examples.length || !solution) return null;
    if (!start) {
      var m = /def solution\(([^)]*)\)/.exec(sig || "");
      start = "def solution(" + (m ? m[1] : "A") + "):\n    pass\n";
    }
    var edges = [];
    solution.querySelectorAll(":scope > ul").forEach(function (ul) {
      if (/edge case/.test(ul.textContent)) edges = edges.concat(testsIn(ul));
    });
    return { examples: examples, edges: edges, start: start, solution: solution };
  }

  function makeBox(task, key) {
    var box = el("div", "sqlplay pyplay");
    var head = el("div", "sqlplay-head");
    head.appendChild(el("span", "sqlplay-title", "Try it here"));
    head.appendChild(el("span", "sqlplay-sub", "Python in your browser"));
    box.appendChild(head);
    var ta = el("textarea", "sqlplay-edit");
    ta.spellcheck = false;
    ta.setAttribute("autocapitalize", "off");
    ta.setAttribute("autocomplete", "off");
    ta.setAttribute("aria-label", "Python code");
    var saved = store(key);
    ta.value = saved != null ? saved : task.start;
    ta.rows = Math.min(18, Math.max(6, ta.value.split("\n").length + 1));
    box.appendChild(ta);
    var bar = el("div", "sqlplay-bar");
    var run = el("button", "md-button md-button--primary", "Run examples");
    run.type = "button";
    run.title = "Run the examples (Ctrl+Enter or Cmd+Enter)";
    var check = el("button", "md-button", "Check");
    check.type = "button";
    check.title = "Run the examples and the edge cases from the solution";
    var reset = el("button", "md-button", "Reset");
    reset.type = "button";
    bar.appendChild(run); bar.appendChild(check); bar.appendChild(reset);
    var status = el("span", "sqlplay-status", "");
    bar.appendChild(status);
    box.appendChild(bar);
    var verdict = el("div", "sqlplay-verdict");
    box.appendChild(verdict);
    var out = el("div", "sqlplay-out");
    box.appendChild(out);
    box.appendChild(el("p", "sqlplay-help", "Run tries the examples above; Check also tries the edge cases listed in " +
      "the solution, without showing the solution. print() output appears below. Standard library only."));

    var busy = false;
    function go(withEdges) {
      if (busy) return;
      busy = true; run.disabled = check.disabled = true;
      verdict.innerHTML = ""; out.innerHTML = "";
      status.textContent = started ? "Running..." : "Starting Python (first time: a few seconds)...";
      var tests = task.examples.concat(withEdges ? task.edges : []);
      store(key, ta.value === task.start ? null : ta.value);
      runPy(ta.value, tests, started ? LIMIT_MS : LIMIT_MS + 45000).then(function (res) {
        started = !res.stopped;
        status.textContent = "";
        if (res.error) out.appendChild(el("p", "sqlplay-error", res.error));
        var t = res.tests || [];
        if (t.length) {
          var wrap = el("div", "sqlplay-table"), tb = el("table"), hr = el("tr");
          ["", "Call", "Expected", "Your result"].forEach(function (x) { hr.appendChild(el("th", null, x)); });
          var th = el("thead"); th.appendChild(hr); tb.appendChild(th);
          var body = el("tbody");
          t.forEach(function (r, i) {
            var tr = el("tr");
            tr.appendChild(el("td", null, r.ok ? "✓" : "✗"));
            var label = i < task.examples.length ? r.call : "edge case " + (i - task.examples.length + 1) + ": " + r.call;
            tr.appendChild(el("td", null, label.length > 90 ? label.slice(0, 87) + "..." : label));
            tr.appendChild(el("td", null, r.want.length > 60 ? r.want.slice(0, 57) + "..." : r.want));
            tr.appendChild(el("td", r.ok ? null : "sqlplay-null", r.got && r.got.length > 60 ? r.got.slice(0, 57) + "..." : r.got));
            body.appendChild(tr);
          });
          tb.appendChild(body); wrap.appendChild(tb); out.appendChild(wrap);
          var passed = t.filter(function (r) { return r.ok; }).length;
          var msg = passed + " of " + t.length + " passed" + (res.ms != null ? " in " + res.ms + " ms" : "") + ".";
          if (passed === t.length) {
            verdict.appendChild(el("p", "sqlplay-good", msg + (withEdges ?
              " The hidden tests of a real test also try the largest inputs: check the cost of your answer against the limits." :
              " Now press Check for the edge cases.")));
          } else verdict.appendChild(el("p", "sqlplay-bad", "Not yet: " + msg));
        }
        if (res.out) {
          out.appendChild(el("p", "sqlplay-tname", "Printed"));
          var pre = el("pre", "pyplay-out"); pre.textContent = res.out; out.appendChild(pre);
        }
      }).then(function () { busy = false; run.disabled = check.disabled = false; });
    }
    run.addEventListener("click", function () { go(false); });
    check.addEventListener("click", function () { go(true); });
    reset.addEventListener("click", function () { ta.value = task.start; store(key, null); out.innerHTML = ""; verdict.innerHTML = ""; });
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
    return box;
  }

  function init() {
    if (!/\/interview\/codility\//.test(location.pathname)) return;
    var content = document.querySelector("article.md-content__inner") || document.querySelector(".md-content");
    if (!content) return;
    var path = location.pathname.replace(/\.html$/, "");
    content.querySelectorAll("h2, h3").forEach(function (h) {
      var task = readTask(h);
      if (!task) return;
      task.solution.parentNode.insertBefore(makeBox(task, "pyplay:" + path + "#" + (h.id || h.textContent)), task.solution);
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();

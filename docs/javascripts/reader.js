// Reading aids, the same file on all seven school sites: cs, math, networks, astronomy, physics, puzzles and cryptography.akadian.ca (copy it to all).
//  1. A bar at the top of every page: where you are (Books > Algorithms > Chapter 5 of 25) and Previous / Next.
//  2. Long chapters and lessons are read in parts of about 5 to 6 minutes: "Part 2 of 5", a progress bar, and
//     Previous part / Next part at the bottom. Each part has its own address (?part=2), so links, search results
//     (#section) and the Back button all work. The page text is never changed; the parts are made here.
//  3. Reading settings (the "Aa" button in the header): text size, reading mode (no menus, a narrow column),
//     light or dark, and whole page instead of parts. Saved in this browser only (localStorage).
//  4. Finished chapters get a tick in the menu, and a chapter remembers the last part you read.
(function () {
  "use strict";
  var KEY = "akadian-reader";
  var pageable = false;
  var MIN_WORDS = 400, MAX_WORDS = 1350, PAGE_WORDS = 1550, WPM = 220;   // parts of five to six minutes (Jim, 5 Nov 2026)

  function load(k) { try { return JSON.parse(localStorage.getItem(k)) || {}; } catch (e) { return {}; } }
  function save(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private window */ } }
  var S = load(KEY);
  var root = document.documentElement;
  function apply() {
    root.style.setProperty("--reader-scale", String(S.scale || 1));
    root.classList.toggle("reader-mode", !!S.focus);
  }
  apply();

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function norm(u) {
    var p = new URL(u, location.href).pathname;
    return p.replace(/index\.html$/, "");
  }
  function words(node) { var m = (node.textContent || "").match(/\S+/g); return m ? m.length : 0; }
  function label(node) {
    var e = node.querySelector(".md-ellipsis") || node;
    return e.textContent.replace(/\s+/g, " ").trim();
  }

  var here = norm(location.href);
  var lastSeg = decodeURIComponent(here.replace(/\/$/, "").split("/").pop().replace(/\.html$/, ""));
  var dirOf = function (p) { return p.replace(/\/$/, "").replace(/[^\/]*$/, ""); };

  // ---- the site menu, flattened in reading order ----
  var nav = [], seen = {};
  document.querySelectorAll(".md-nav--primary a.md-nav__link[href]").forEach(function (a) {
    if (a.closest(".md-nav--secondary")) return;
    var h = a.getAttribute("href");
    if (!h || h.charAt(0) === "#" || a.host !== location.host) return;
    var p = norm(a.href);
    if (seen[p]) return;
    seen[p] = 1;
    nav.push({ path: p, href: a.href, title: label(a), a: a });
  });
  var at = -1;
  nav.forEach(function (n, i) { if (n.path === here) at = i; });

  // ---- ticks for finished chapters ----
  var done = load(KEY + "-done"), pos = load(KEY + "-pos");
  // The tick explains itself (cntourit, 8 Nov 2026: "for users don't know this they might be confused"):
  // pointing at it says what it means, and a quiet line under any menu list holding a tick says it on phones too.
  var TICK_SAYS = "You have read this page to the end (remembered in this browser only)";
  function tick(a) {
    a.classList.add("reader-done"); a.title = TICK_SAYS;
    // on phones and tablets the open page is shown by a label next to the link: tick that too
    var lab = a.parentNode && a.parentNode.querySelector(":scope > label.md-nav__link");
    if (lab) { lab.classList.add("reader-done"); lab.title = TICK_SAYS; }
    var ul = a.closest("ul");
    if (!ul || (ul.nextElementSibling && ul.nextElementSibling.classList.contains("reader-legend"))) return;
    var p = document.createElement("p"); p.className = "reader-legend";
    p.textContent = "✓ = read to the end, remembered in this browser only";
    ul.parentNode.insertBefore(p, ul.nextSibling);
  }
  nav.forEach(function (n) { if (done[n.path]) tick(n.a); });

  // ---- books fold in the side menu (cntourit, 8 Nov 2026: "by default I like left panels to be collapsed,
  // listing only books. when clicked it will expand, and it will remember my choice"; 15:11Z: "all books by default
  // need to be collapsed in the left menu navigation"; 16:26Z: "click one time, I need to expand, and one click again
  // it should collapse. now any click just refresh and stay collapsed") ----
  // Every book starts closed, the one you are reading too: the Books (or Book) menu lists only the book names,
  // and the book you are on is highlighted. A click on a book's name or on its arrow opens its chapters in place;
  // a second click closes them; nothing is loaded. On wide screens that choice is remembered per book in this
  // browser only. The book's own front page is the first line inside the open book ("Start here"), since the name
  // no longer leads there. On phones and tablets the menu opens at the list of books; a tap on a book slides into
  // its chapters, as the arrow always did. A book that has read chapters shows "✓ n of m" beside its name.
  (function () {
    var wide = window.matchMedia && window.matchMedia("(min-width: 76.25em)").matches;
    // a new name for the saved choices: the old ones were partly written automatically (a book opened by itself
    // when it was being read, or when its name was clicked), so every book starts closed once more
    var FOLD = KEY + "-shelf", folds = load(FOLD);
    function head(li) {
      for (var c = li.firstElementChild; c; c = c.nextElementSibling) if (c.classList.contains("md-nav__link")) return c;
      return null;
    }
    document.querySelectorAll(".md-nav--primary > .md-nav__list > li.md-nav__item--nested").forEach(function (shelf) {
      var h = head(shelf);
      if (!h || !/^Books?$/.test(label(h))) return;
      var list = shelf.querySelector(":scope > nav > .md-nav__list");
      if (!list) return;
      list.querySelectorAll(":scope > li.md-nav__item--nested").forEach(function (li) {
        var box = li.querySelector(":scope > input.md-nav__toggle"), top = head(li), sub = li.querySelector(":scope > nav.md-nav");
        if (!box || !top || !sub) return;
        var link = top.tagName === "A" ? top : top.querySelector("a[href]");
        var arrow = top.tagName === "LABEL" ? top : top.querySelector("label");
        var key = link ? norm(link.href) : label(top);
        li.classList.remove("md-nav__item--section");
        li.classList.add("reader-book");
        var show = function (open) {
          box.checked = open;
          sub.setAttribute("aria-expanded", open ? "true" : "false");
          var say = open ? "Hide the chapters" : "Show the chapters";
          if (arrow) arrow.title = say;
          if (link) { link.title = say; link.setAttribute("aria-expanded", open ? "true" : "false"); }
        };
        var remember = function () { if (!wide) return; folds[key] = box.checked; save(FOLD, folds); };
        if (wide) {
          show(!!folds[key]);
        } else {
          // the phone menu slides into every open level, so close this book and the parts inside it
          show(false);
          sub.querySelectorAll("input.md-nav__toggle").forEach(function (b) { b.checked = false; });
        }
        // the arrow is a label for the checkbox: the browser toggles it, we only remember the choice
        box.addEventListener("change", function () { show(box.checked); remember(); });
        if (link) {
          // the name toggles the book in place instead of loading its front page
          link.addEventListener("click", function (e) {
            if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;   // a new tab still works
            e.preventDefault();
            show(!box.checked);
            remember();
          });
          // the front page itself moves inside the book, as its first line
          var ul = sub.querySelector(":scope > .md-nav__list");
          if (ul && !ul.querySelector(":scope > li > a.reader-bookhome")) {
            var fli = el("li", "md-nav__item"), fa = el("a", "md-nav__link reader-bookhome");
            fa.href = link.href;
            fa.appendChild(el("span", "md-ellipsis", "Start here"));
            fa.title = "The front page of this book";
            if (norm(link.href) === here) { fa.classList.add("md-nav__link--active"); fa.setAttribute("aria-current", "page"); }
            fli.appendChild(fa);
            ul.insertBefore(fli, ul.firstChild);
          }
        }
        // how much of this book is read, so the ticks stay in sight while the book is closed
        var pages = sub.querySelectorAll("a.md-nav__link[href]"), n = 0, m = 0, met = {};
        pages.forEach(function (a) {
          var p = norm(a.href), s = p.replace(/\/$/, "").split("/").pop();
          if (met[p] || !/^\d{1,3}-/.test(s)) return;
          met[p] = 1; m++; if (done[p]) n++;
        });
        if (n) {
          var c = el("span", "reader-bookcount", "✓ " + n + " of " + m);
          c.title = n + " of " + m + " chapters read to the end (remembered in this browser only)";
          (link || top).appendChild(c);
        }
      });
    });
  })();

  // ---- reading settings ----
  var header = document.querySelector(".md-header__inner");
  if (header) {
    var btn = el("button", "md-header__button reader-btn", "Aa");
    btn.type = "button";
    btn.title = "Reading settings";
    btn.setAttribute("aria-label", "Reading settings");
    btn.setAttribute("aria-expanded", "false");
    var panel = el("div", "reader-panel");
    panel.hidden = true;
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-label", "Reading settings");
    panel.innerHTML =
      '<p class="reader-panel__title">Reading settings</p>' +
      '<div class="reader-row"><span>Text size</span><span class="reader-seg">' +
      '<button type="button" data-act="smaller" aria-label="Smaller text">A−</button>' +
      '<output class="reader-size"></output>' +
      '<button type="button" data-act="bigger" aria-label="Bigger text">A+</button></span></div>' +
      '<div class="reader-row"><span>Reading mode<small>No menus, a narrow column</small></span>' +
      '<button type="button" class="reader-switch" data-act="focus" role="switch"></button></div>' +
      '<div class="reader-row"><span>Long chapters</span><span class="reader-seg">' +
      '<button type="button" data-act="parts">In parts</button>' +
      '<button type="button" data-act="whole">Whole page</button></span></div>' +
      '<div class="reader-row"><span>Colours</span><span class="reader-seg">' +
      '<button type="button" data-act="light">Light</button>' +
      '<button type="button" data-act="dark">Dark</button></span></div>' +
      '<button type="button" class="reader-reset" data-act="reset">Back to the usual settings</button>';
    var anchor = header.querySelector(".md-header__option") || header.querySelector("label[for='__search']");
    header.insertBefore(btn, anchor);
    document.body.appendChild(panel);

    var palettes = Array.prototype.slice.call(document.querySelectorAll("input[name='__palette']"));
    function scheme() { return document.body.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "light"; }
    function setScheme(want) {
      palettes.forEach(function (i) {
        var s = i.getAttribute("data-md-color-scheme") === "slate" ? "dark" : "light";
        if (s === want && !i.checked) i.click();
      });
    }
    function show() {
      var sc = S.scale || 1;
      panel.querySelector(".reader-size").textContent = Math.round(sc * 100) + "%";
      panel.querySelector("[data-act=smaller]").disabled = sc <= 0.85;
      panel.querySelector("[data-act=bigger]").disabled = sc >= 1.6;
      panel.querySelector("[data-act=focus]").setAttribute("aria-checked", S.focus ? "true" : "false");
      panel.querySelector("[data-act=parts]").setAttribute("aria-pressed", S.whole ? "false" : "true");
      panel.querySelector("[data-act=whole]").setAttribute("aria-pressed", S.whole ? "true" : "false");
      var sch = scheme();
      panel.querySelector("[data-act=light]").setAttribute("aria-pressed", sch === "light" ? "true" : "false");
      panel.querySelector("[data-act=dark]").setAttribute("aria-pressed", sch === "dark" ? "true" : "false");
    }
    function open(yes) {
      panel.hidden = !yes;
      btn.setAttribute("aria-expanded", yes ? "true" : "false");
      if (yes) show();
    }
    btn.addEventListener("click", function (e) { e.stopPropagation(); open(panel.hidden); });
    document.addEventListener("click", function (e) { if (!panel.hidden && !panel.contains(e.target)) open(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !panel.hidden) { open(false); btn.focus(); } });
    panel.addEventListener("click", function (e) {
      var b = e.target.closest("button[data-act]");
      if (!b) return;
      var act = b.getAttribute("data-act"), sc = S.scale || 1, reload = false;
      if (act === "smaller") S.scale = Math.max(0.85, Math.round((sc - 0.1) * 100) / 100);
      if (act === "bigger") S.scale = Math.min(1.6, Math.round((sc + 0.1) * 100) / 100);
      if (act === "focus") S.focus = !S.focus;
      if (act === "parts" || act === "whole") { reload = S.whole !== (act === "whole"); S.whole = act === "whole"; }
      if (act === "light" || act === "dark") setScheme(act);
      if (act === "reset") { reload = !!S.whole; S = {}; }
      save(KEY, S);
      apply();
      if (reload && pageable) { location.reload(); return; }
      setTimeout(show, 30);
    });
    var exit = el("button", "reader-exit", "Leave reading mode");
    exit.type = "button";
    exit.addEventListener("click", function () { S.focus = false; save(KEY, S); apply(); });
    document.body.appendChild(exit);
  }

  var article = document.querySelector(".md-content__inner");
  if (!article || document.querySelector(".mars-hero")) return; // the home page keeps its own layout
  var h1 = article.querySelector(":scope > h1");

  // ---- top bar: where you are, previous / next ----
  var crumbs = [];
  document.querySelectorAll(".md-nav--primary .md-nav__item--active.md-nav__item--nested").forEach(function (li) {
    var head = null;
    for (var c = li.firstElementChild; c; c = c.nextElementSibling) {
      if (c.classList.contains("md-nav__link")) { head = c; break; }
    }
    if (!head) return;
    var a = head.tagName === "A" ? head : head.querySelector("a[href]");
    var self = !!a && norm(a.href) === here;
    crumbs.push({ title: label(head), href: a && !self ? a.href : null, self: self });
  });
  var chapter = /^\d{1,3}-/.test(lastSeg) ? nav.filter(function (n) {
    var s = n.path.replace(/\/$/, "").split("/").pop();
    return dirOf(n.path) === dirOf(here) && /^\d{1,3}-/.test(s);
  }) : [];
  var chNo = 0;
  chapter.forEach(function (n, i) { if (n.path === here) chNo = i + 1; });
  var kind = !chNo ? "Page" : /\/(topics|start|first-steps)\//.test(here) ? "Lesson" : "Chapter";

  var top = el("nav", "reader-top");
  top.setAttribute("aria-label", "Where you are");
  if (crumbs.length && crumbs[crumbs.length - 1].self) crumbs.pop(); // a section's own first page
  var trail = el("div", "reader-crumbs");
  crumbs.forEach(function (c) {
    var x = c.href ? el("a", null, c.title) : el("span", null, c.title);
    if (c.href) x.href = c.href;
    trail.appendChild(x);
    trail.appendChild(el("span", "reader-sep", "›"));
  });
  trail.appendChild(el("span", "reader-here", chNo ? kind + " " + chNo + " of " + chapter.length
    : (at >= 0 ? nav[at].title : "")));
  var pn = el("div", "reader-pn");
  function pnLink(i, cls, word) {
    if (i < 0 || i >= nav.length) { var s = el("span", cls + " reader-off", word); s.setAttribute("aria-hidden", "true"); return s; }
    var a = el("a", cls, word);
    a.href = nav[i].href;
    a.title = nav[i].title;
    a.rel = cls === "reader-prev" ? "prev" : "next";
    return a;
  }
  if (at >= 0) {
    pn.appendChild(pnLink(at - 1, "reader-prev", "‹ Previous"));
    pn.appendChild(pnLink(at + 1, "reader-next", "Next ›"));
  }
  if (crumbs.length || at >= 0) {
    top.appendChild(trail);
    top.appendChild(pn);
    article.insertBefore(top, h1 || article.firstChild);
  }

  // ---- level: where this page sits on the ladder; each site's rules are in javascripts/levels.js ----
  var LEVELS = ["Beginner", "Intermediate", "Expert"];
  var lv = typeof window.akadianLevel === "function" ? window.akadianLevel(here, chNo, chapter.length) : null;
  var lvAt = h1 || article.querySelector("h1");
  if (lv && lvAt) {
    var lvBox = el("p", "reader-level");
    lvBox.setAttribute("aria-label", lv === "All" ? "Level: every level, part by part" : "Level: " + lv);
    lvBox.appendChild(el("span", "reader-level-name", "Level"));
    LEVELS.forEach(function (name) {
      lvBox.appendChild(el("span", lv === "All" || lv === name ? "reader-level-on" : "reader-level-off", name));
    });
    lvAt.parentNode.insertBefore(lvBox, lvAt.nextSibling);
  }

  // ---- parts ----
  var paged = null;
  var kids = Array.prototype.slice.call(article.children);
  var start = h1 ? kids.indexOf(h1) + 1 : 0;
  var body = kids.slice(start).filter(function (k) { return k !== top && !k.classList.contains("md-source-file"); });
  var total = 0;
  body.forEach(function (k) { total += words(k); });
  var secs = [], cur = { nodes: [], words: 0, title: null, id: null };
  body.forEach(function (k) {
    if (k.tagName === "H2") {
      if (cur.nodes.length) secs.push(cur);
  // a very long section is cut at its sub-headings, or between paragraphs, so no part runs much over 6 minutes
  secs = secs.reduce(function (out, s) {
    if (s.words <= MAX_WORDS) { out.push(s); return out; }
    var c = { nodes: [], words: 0, title: s.title };
    s.nodes.forEach(function (n) {
      if (n.tagName === "H3" && c.words >= MIN_WORDS / 2) {
        out.push(c);
        c = { nodes: [], words: 0, title: n.textContent.replace(/¶/g, "").trim() };
      } else if (c.words >= MIN_WORDS && c.words + words(n) > MAX_WORDS && !/^H[2-6]$/.test(n.tagName)) {
        out.push(c);
        c = { nodes: [], words: 0, title: s.title + " (continued)" };
      }
      c.nodes.push(n);
      c.words += words(n);
    });
    out.push(c);
    return out;
  }, []);
      cur = { nodes: [], words: 0, title: k.textContent.replace(/¶/g, "").trim(), id: k.id };
    }
    cur.nodes.push(k);
    cur.words += words(k);
  });
  if (cur.nodes.length) secs.push(cur);

  var parts = [], p = null;
  secs.forEach(function (s) {
    if (p && p.words >= MIN_WORDS && p.words + s.words > MAX_WORDS) { parts.push(p); p = null; }
    if (!p) p = { nodes: [], words: 0, title: null, ids: [] };
    p.nodes = p.nodes.concat(s.nodes);
    p.words += s.words;
    if (!p.title && s.title) p.title = s.title;
  });
  if (p) parts.push(p);
  if (parts.length > 1 && parts[parts.length - 1].words < 400) {
    var last = parts.pop(), prev = parts[parts.length - 1];
    prev.nodes = prev.nodes.concat(last.nodes);
    prev.words += last.words;
  }
  var isChapterLike = !/glossary|^index$/i.test(lastSeg);
  var nextHref = at >= 0 && at + 1 < nav.length ? nav[at + 1] : null;

  function markDone(target) {
    if (!("IntersectionObserver" in window) || !target) return;
    var io = new IntersectionObserver(function (es) {
      if (!es[0].isIntersecting) return;
      var first = !done[here];
      done[here] = 1; save(KEY + "-done", done);
      if (first && at >= 0) {
        var note = el("p", "reader-ticknote", "✓ Finished. This page now has a tick in the menu, so you can see what you have read.");
        var fin = document.querySelector(".reader-finished");
        if (fin) fin.parentNode.replaceChild(note, fin); else article.appendChild(note);
      }
      if (at >= 0) tick(nav[at].a);
      io.disconnect();
    });
    io.observe(target);
  }

  pageable = isChapterLike && total > PAGE_WORDS && parts.length > 1;
  if (pageable && !S.whole) {
    var idPart = {};
    parts.forEach(function (pt, i) {
      pt.nodes.forEach(function (n) {
        if (n.id) idPart[n.id] = i;
        n.querySelectorAll && n.querySelectorAll("[id]").forEach(function (x) { idPart[x.id] = i; });
      });
    });
    var params = new URLSearchParams(location.search);
    var k = parseInt(params.get("part"), 10) - 1;
    if (!(k >= 0 && k < parts.length)) k = 0;
    var hash = decodeURIComponent(location.hash.slice(1));
    if (hash && idPart[hash] != null) k = idPart[hash];
    paged = k;
    var partUrl = function (i, h) {
      var u = new URL(location.href);
      if (i > 0) u.searchParams.set("part", String(i + 1)); else u.searchParams.delete("part");
      u.hash = h ? "#" + h : "";
      return u.pathname + u.search + u.hash;
    };
    // keep only this part on the page
    parts.forEach(function (pt, i) {
      if (i !== k) pt.nodes.forEach(function (n) { if (n.parentNode) n.parentNode.removeChild(n); });
    });
    document.body.classList.add("reader-paged");
    var mins = function (w) { return Math.max(1, Math.round(w / WPM)); };

    // the progress bar under the title
    var bar = el("div", "reader-parts");
    var lab = el("p", "reader-parts__label");
    lab.appendChild(el("strong", null, "Part " + (k + 1) + " of " + parts.length));
    lab.appendChild(document.createTextNode(" · about " + mins(parts[k].words) + " min · whole " +
      kind.toLowerCase() + " about " + mins(total) + " min"));
    bar.appendChild(lab);
    var ol = el("ol", "reader-parts__bar");
    ol.setAttribute("aria-label", "Parts of this " + kind.toLowerCase());
    parts.forEach(function (pt, i) {
      var li = el("li", i < k ? "is-done" : i === k ? "is-here" : "");
      var a = el("a");
      a.href = partUrl(i);
      a.title = "Part " + (i + 1) + ": " + (pt.title || "Introduction");
      a.setAttribute("aria-label", a.title);
      if (i === k) a.setAttribute("aria-current", "step");
      li.appendChild(a);
      ol.appendChild(li);
    });
    bar.appendChild(ol);
    var saved = pos[here];
    if (k === 0 && !params.get("part") && saved > 1 && saved <= parts.length && !done[here]) {
      var res = el("a", "reader-resume", "Continue where you stopped: part " + saved + " ›");
      res.href = partUrl(saved - 1);
      bar.appendChild(res);
    }
    var firstNode = parts[k].nodes[0];
    article.insertBefore(bar, firstNode && firstNode.parentNode === article ? firstNode : null);
    if (k > 0) {
      var ttl = el("p", "reader-parts__title", parts[k].title || "");
      if (parts[k].title && firstNode && firstNode.tagName !== "H2") bar.appendChild(ttl);
    }

    // previous / next part at the bottom
    var foot = el("nav", "reader-partnav");
    foot.setAttribute("aria-label", "Parts");
    var big = function (href, cls, small, text) {
      var a = el("a", cls);
      a.href = href;
      a.appendChild(el("small", null, small));
      a.appendChild(el("span", null, text));
      return a;
    };
    if (k > 0) foot.appendChild(big(partUrl(k - 1), "reader-partnav__prev", "‹ Previous part",
      "Part " + k + ": " + (parts[k - 1].title || "Introduction")));
    else foot.appendChild(el("span"));
    if (k < parts.length - 1) {
      foot.appendChild(big(partUrl(k + 1), "reader-partnav__next", "Next part · " + (k + 2) + " of " + parts.length + " ›",
        parts[k + 1].title || ""));
    } else {
      var fin = el("div", "reader-partnav__end");
      fin.appendChild(el("p", "reader-finished", "✓ You have finished this " + kind.toLowerCase() + "."));
      if (nextHref) fin.appendChild(big(nextHref.href, "reader-partnav__next", "Next ›", nextHref.title));
      foot.appendChild(fin);
    }
    var tail = article.querySelector(":scope > .md-source-file");
    article.insertBefore(foot, tail);
    pos[here] = k + 1; save(KEY + "-pos", pos);
    if (k === parts.length - 1) markDone(foot);

    // "On this page": sections in other parts open that part
    document.querySelectorAll(".md-nav--secondary a.md-nav__link[href^='#']").forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute("href").slice(1)), i = idPart[id];
      if (i == null) return;
      a.href = partUrl(i, id);
      if (i !== k) a.parentNode.classList.add("reader-toc-away");
    });
    // links inside the text to a section in another part
    document.addEventListener("click", function (e) {
      var a = e.target.closest && e.target.closest("a[href*='#']");
      if (!a || e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey) return;
      var u = new URL(a.href, location.href);
      if (norm(u.href) !== here) return;
      var id = decodeURIComponent(u.hash.slice(1));
      if (id && idPart[id] != null && idPart[id] !== k) { e.preventDefault(); location.href = partUrl(idPart[id], id); }
    }, true);
    window.addEventListener("hashchange", function () {
      var id = decodeURIComponent(location.hash.slice(1));
      if (id && idPart[id] != null && idPart[id] !== k) location.replace(partUrl(idPart[id], id));
    });
  } else if (chNo && isChapterLike) {
    markDone(article.lastElementChild);
  }
})();

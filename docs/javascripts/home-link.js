// the site name in the header goes to this site's own first page (it.akadian.ca); "Mars" beside it is the
// way back to akadian.ca (extra.homepage). It used to copy the logo's link, so both went to akadian.ca (31 Oct 2026).
(function () {
  var logo = document.querySelector(".md-header__button.md-logo");
  var title = document.querySelector(".md-header__topic .md-ellipsis");
  if (!logo || !title) return;
  var a = document.createElement("a");
  var base = ".";
  try { base = JSON.parse(document.getElementById("__config").textContent).base || "."; } catch (e) { /* no config: this folder */ }
  a.href = new URL(base.replace(/\/?$/, "/"), location.href).href;
  a.className = "home-link";
  a.title = "Back to the IT home page";
  a.textContent = title.textContent.trim();
  title.textContent = "";
  title.appendChild(a);
})();

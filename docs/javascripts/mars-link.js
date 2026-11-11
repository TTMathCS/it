// the Akadian logo in the header goes back to akadian.ca; say so to screen readers (Material labels it with the site name)
document$.subscribe(function () {
  document.querySelectorAll("a.md-logo").forEach(function (a) {
    a.setAttribute("aria-label", "Akadian, Mars – your new home");
    a.setAttribute("title", "Akadian, Mars – your new home");
  });
});

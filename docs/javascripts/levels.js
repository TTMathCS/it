// the level shown at the top of a course chapter on it.akadian.ca, worked out from the course and the chapter number.
// SQL (databases/sql): chapters 1-6 beginner, 7-24 intermediate, 25-29 expert, practice and mock tests (30+) every level.
// Any other course: the first fifth beginner, the last quarter expert, the rest intermediate.
window.akadianLevel = function (path, ch, n) {
  var m = /\/databases\/sql\/(\d+)-/.exec(path);
  if (m) {
    var c = parseInt(m[1], 10);
    if (c >= 30) return "All";
    if (c <= 6) return "Beginner";
    if (c >= 25) return "Expert";
    return "Intermediate";
  }
  if (/\/[^\/]+\/[^\/]+\/\d+-/.test(path) && ch && n) {
    if (ch <= Math.ceil(n * 0.2)) return "Beginner";
    if (ch > n * 0.75) return "Expert";
    return "Intermediate";
  }
  return null;
};

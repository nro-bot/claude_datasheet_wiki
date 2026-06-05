// Client-side full-text search over window.DSW_SEARCH (tf-idf). Fully offline.
(function () {
  var root = window.DSW_ROOT || "";
  var DATA = window.DSW_SEARCH;
  var input = document.getElementById("q");
  var resultsEl = document.getElementById("results");
  var statusEl = document.getElementById("search-status");
  if (!DATA || !input) return;

  var N = DATA.n;
  // precompute idf
  var idf = {};
  for (var term in DATA.index) {
    idf[term] = Math.log(1 + N / DATA.index[term].length);
  }

  function tokenize(q) {
    return (q.toLowerCase().match(/[a-z0-9_]+/g) || []).filter(function (t) { return t.length > 1; });
  }

  function textSearch(q) {
    var terms = tokenize(q);
    if (!terms.length) return [];
    var scores = {};
    terms.forEach(function (t) {
      // exact + prefix matches (so "tim" hits "timer")
      for (var term in DATA.index) {
        if (term !== t && term.indexOf(t) !== 0) continue;
        var w = (term === t ? 1 : 0.5) * (idf[term] || 1);
        DATA.index[term].forEach(function (pair) {
          scores[pair[0]] = (scores[pair[0]] || 0) + pair[1] * w;
        });
      }
    });
    return Object.keys(scores)
      .map(function (i) { return { i: +i, score: scores[i] }; })
      .sort(function (a, b) { return b.score - a.score; })
      .slice(0, 40);
  }

  function highlight(text, terms) {
    var out = text;
    terms.forEach(function (t) {
      try {
        out = out.replace(new RegExp("(" + t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "ig"), "<mark>$1</mark>");
      } catch (e) {}
    });
    return out;
  }

  function render(q) {
    var terms = tokenize(q);
    var hits = textSearch(q);
    if (!q.trim()) { resultsEl.innerHTML = ""; statusEl.textContent = ""; return; }
    statusEl.textContent = hits.length + " result" + (hits.length === 1 ? "" : "s");
    resultsEl.innerHTML = hits.map(function (h) {
      var d = DATA.docs[h.i];
      return '<div class="result">' +
        '<div class="crumb">' + escapeHtml(d.b) + ' · ' + d.p + '</div>' +
        '<h3><a href="' + root + d.u + '">' + highlight(escapeHtml(d.t), terms) + '</a></h3>' +
        '<div class="snippet">' + highlight(escapeHtml(d.s), terms) + '</div>' +
        '</div>';
    }).join("");
  }

  function escapeHtml(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  var params = new URLSearchParams(location.search);
  if (params.get("q")) { input.value = params.get("q"); }

  var t;
  input.addEventListener("input", function () {
    clearTimeout(t);
    t = setTimeout(function () { render(input.value); }, 120);
  });
  if (input.value) render(input.value);
})();

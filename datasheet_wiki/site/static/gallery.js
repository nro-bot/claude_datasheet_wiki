// Drives both the Reference builder (reference.html) and the Personal Reference
// / starred-pages gallery (starred.html). Uses window.DSW_PAGES (the page
// manifest) and window.DSWStars (bookmarks). Fully client-side / offline.
(function () {
  var PAGES = window.DSW_PAGES || [];
  var byNum = {};
  PAGES.forEach(function (p) { byNum[p.n] = p; });
  var stars = window.DSWStars;
  var mode = document.body.getAttribute("data-page"); // "reference" | "starred"

  // ---- thumbnail-size preference (shared, persisted) ----
  var SIZE_KEY = "dsw:" + (window.DSW_ID || "datasheet") + ":thumbsize";
  function savedSize() {
    try { return parseInt(localStorage.getItem(SIZE_KEY), 10) || 220; } catch (e) { return 220; }
  }
  function saveSize(v) { try { localStorage.setItem(SIZE_KEY, v); } catch (e) {} }

  function escapeHtml(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function figureHTML(n) {
    var p = byNum[n];
    var caption = "Page " + n + (p && p.sec ? " · " + escapeHtml(p.sec) : "");
    var inner = (p && p.img)
      ? '<a href="' + p.img + '" target="_blank" rel="noopener"><img loading="lazy" src="' + p.img + '" alt="Page ' + n + '"></a>'
      : '<div class="noimg">Page ' + n + (p ? "" : " — out of range") + '<br><span>no image</span></div>';
    var cap = (p && p.url) ? '<a href="' + p.url + '">' + caption + "</a>" : caption;
    return '<figure class="thumb" data-page="' + n + '">' + inner + "<figcaption>" + cap + "</figcaption></figure>";
  }

  function renderGallery(container, nums) {
    if (!nums.length) {
      container.innerHTML = '<p class="muted empty">No pages yet.</p>';
      return;
    }
    container.innerHTML = nums.map(figureHTML).join("");
    if (stars) stars.decorate();
  }

  function sizeSlider(container, onChange) {
    var wrap = document.createElement("div");
    wrap.className = "size-ctl";
    var init = savedSize();
    wrap.innerHTML = '<label>Thumbnail size <input type="range" min="120" max="460" step="20" value="' + init + '"></label>';
    var input = wrap.querySelector("input");
    function apply(v) { container.style.setProperty("--thumb-w", v + "px"); }
    apply(init);
    input.addEventListener("input", function () { apply(input.value); saveSize(input.value); if (onChange) onChange(); });
    return wrap;
  }

  // ---- page spec parsing: "1, 3, 5-8, 12" -> [1,3,5,6,7,8,12] (input order) ----
  function parseSpec(s) {
    var out = [], seen = {};
    (s || "").split(",").forEach(function (part) {
      part = part.trim();
      if (!part) return;
      var m = part.match(/^(\d+)\s*[-–]\s*(\d+)$/);
      if (m) {
        var a = +m[1], b = +m[2];
        if (a > b) { var t = a; a = b; b = t; }
        for (var i = a; i <= b; i++) push(i);
      } else if (/^\d+$/.test(part)) push(+part);
    });
    function push(n) { if (n >= 1 && !seen[n]) { seen[n] = 1; out.push(n); } }
    return out;
  }

  // =====================================================================
  if (mode === "starred") initStarred();
  else if (mode === "reference") initReference();

  function initStarred() {
    var gallery = document.getElementById("gallery");
    var status = document.getElementById("status");
    var controls = document.getElementById("controls");
    if (!gallery) return;
    controls.appendChild(sizeSlider(gallery));

    function refresh() {
      var nums = stars ? stars.list() : [];
      status.textContent = nums.length
        ? nums.length + " starred page" + (nums.length === 1 ? "" : "s")
        : "No starred pages yet — open any section and click ★ on a source page.";
      renderGallery(gallery, nums);
    }
    document.getElementById("clear-all").addEventListener("click", function () {
      if (confirm("Remove all starred pages?")) stars.clear();
    });
    document.getElementById("print").addEventListener("click", function () { window.print(); });
    if (stars) stars.subscribe(refresh);
    refresh();
  }

  function initReference() {
    var input = document.getElementById("pagespec");
    var gallery = document.getElementById("gallery");
    var status = document.getElementById("status");
    var controls = document.getElementById("controls");
    var search = document.getElementById("page-search");
    var results = document.getElementById("search-results");
    if (!input) return;
    controls.appendChild(sizeSlider(gallery));

    function update() {
      var nums = parseSpec(input.value);
      status.textContent = nums.length ? nums.length + " page" + (nums.length === 1 ? "" : "s") : "";
      renderGallery(gallery, nums);
      try { history.replaceState(null, "", "#pages=" + nums.join(",")); } catch (e) {}
    }
    var t;
    input.addEventListener("input", function () { clearTimeout(t); t = setTimeout(update, 200); });

    document.getElementById("star-all").addEventListener("click", function () {
      parseSpec(input.value).forEach(function (n) { stars.add(n); });
      flash(status, "Starred all listed pages");
    });
    document.getElementById("copy-link").addEventListener("click", function () {
      var url = location.href.split("#")[0] + "#pages=" + parseSpec(input.value).join(",");
      if (navigator.clipboard) navigator.clipboard.writeText(url).catch(function () {});
      flash(status, "Shareable link copied");
    });

    // page-number search
    var st;
    search.addEventListener("input", function () { clearTimeout(st); st = setTimeout(runSearch, 160); });

    function runSearch() {
      var q = search.value.trim().toLowerCase();
      if (!q) { results.innerHTML = ""; return; }
      var toks = q.match(/[a-z0-9_]+/g) || [];
      if (!toks.length) { results.innerHTML = ""; return; }
      var hits = [];
      for (var i = 0; i < PAGES.length; i++) {
        var p = PAGES[i];
        var hay = (p.sec + " " + (p.t || "")).toLowerCase();
        var ok = true, score = 0;
        for (var k = 0; k < toks.length; k++) {
          var idx = hay.indexOf(toks[k]);
          if (idx === -1) { ok = false; break; }
          score += 1;
        }
        if (ok) hits.push({ p: p, hay: hay, tok: toks[0] });
      }
      hits = hits.slice(0, 40);
      if (!hits.length) { results.innerHTML = '<p class="muted">No pages match.</p>'; return; }
      results.innerHTML = hits.map(function (h) {
        var idx = h.hay.indexOf(h.tok);
        var snip = (h.p.t || "").replace(/\s+/g, " ").substr(Math.max(0, idx - 30), 110);
        return '<div class="sr"><button type="button" class="add" data-n="' + h.p.n + '">+ p.' + h.p.n + '</button> '
          + '<span class="sr-sec">' + escapeHtml(h.p.sec) + '</span> '
          + '<span class="muted">…' + escapeHtml(snip) + '…</span></div>';
      }).join("");
      results.querySelectorAll(".add").forEach(function (b) {
        b.addEventListener("click", function () {
          addPage(+b.getAttribute("data-n"));
        });
      });
    }
    function addPage(n) {
      var nums = parseSpec(input.value);
      if (nums.indexOf(n) === -1) {
        input.value = (input.value.trim() ? input.value.replace(/,\s*$/, "") + ", " : "") + n;
        update();
      }
    }

    // seed from URL hash (#pages=1,3,5)
    var m = location.hash.match(/pages=([0-9,\-–\s]+)/);
    if (m) input.value = parseSpec(m[1]).join(", ");
    update();
  }

  function flash(el, msg) {
    var prev = el.textContent;
    el.textContent = msg;
    setTimeout(function () { el.textContent = prev; }, 1400);
  }
})();

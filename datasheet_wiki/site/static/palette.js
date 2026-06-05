// Ctrl-K / ⌘-K quick-jump command palette over window.DSW_PALETTE
// (sections, registers, key pages). Fully client-side.
(function () {
  var DATA = window.DSW_PALETTE || [];
  var root = window.DSW_ROOT || "";
  var box, input, list, items = [], sel = 0;

  function build() {
    box = document.createElement("div");
    box.className = "palette";
    box.setAttribute("hidden", "");
    box.innerHTML =
      '<div class="pal-card"><input class="pal-input" type="text" placeholder="Jump to a section, register or page…" aria-label="Quick jump">' +
      '<div class="pal-list" role="listbox"></div>' +
      '<div class="pal-hint">↑↓ navigate · ↵ open · esc close</div></div>';
    document.body.appendChild(box);
    input = box.querySelector(".pal-input");
    list = box.querySelector(".pal-list");
    box.addEventListener("click", function (e) { if (e.target === box) close(); });
    input.addEventListener("input", render);
    input.addEventListener("keydown", onKey);
  }

  function score(entry, q, toks) {
    var t = entry.t.toLowerCase();
    for (var i = 0; i < toks.length; i++) if (t.indexOf(toks[i]) === -1 && (entry.k + " " + (entry.s || "")).toLowerCase().indexOf(toks[i]) === -1) return -1;
    var s = 0;
    if (t === q) s += 100;
    else if (t.indexOf(q) === 0) s += 50;
    else if (t.indexOf(q) !== -1) s += 20;
    if (entry.k === "register") s += 8;          // favour registers (engineers jump to these)
    else if (entry.k === "page") s += 4;
    return s - t.length * 0.05;
  }

  function render() {
    var q = input.value.trim().toLowerCase();
    var toks = q ? q.split(/\s+/) : [];
    var ranked;
    if (!q) ranked = DATA.slice(0, 30);
    else ranked = DATA.map(function (e) { return { e: e, s: score(e, q, toks) }; })
      .filter(function (x) { return x.s >= 0; })
      .sort(function (a, b) { return b.s - a.s; })
      .slice(0, 30).map(function (x) { return x.e; });
    items = ranked;
    sel = 0;
    list.innerHTML = ranked.map(function (e, i) {
      var meta = e.k === "register" ? ("register · " + (e.s || "")) : e.k;
      return '<div class="pal-item' + (i === 0 ? " sel" : "") + '" data-i="' + i + '">' +
        '<span class="pal-t">' + esc(e.t) + "</span>" +
        '<span class="pal-k pal-k-' + e.k + '">' + esc(meta) + "</span></div>";
    }).join("") || '<div class="pal-empty">No matches</div>';
    Array.prototype.forEach.call(list.querySelectorAll(".pal-item"), function (el) {
      el.addEventListener("mousemove", function () { select(+el.getAttribute("data-i")); });
      el.addEventListener("click", function () { go(+el.getAttribute("data-i")); });
    });
  }

  function select(i) {
    sel = i;
    Array.prototype.forEach.call(list.children, function (el, j) { el.classList.toggle("sel", j === i); });
  }
  function go(i) {
    var e = items[i];
    if (e) { close(); location.href = root + e.u; }
  }
  function onKey(ev) {
    if (ev.key === "ArrowDown") { ev.preventDefault(); if (sel < items.length - 1) { select(sel + 1); ensure(); } }
    else if (ev.key === "ArrowUp") { ev.preventDefault(); if (sel > 0) { select(sel - 1); ensure(); } }
    else if (ev.key === "Enter") { ev.preventDefault(); go(sel); }
    else if (ev.key === "Escape") { ev.preventDefault(); close(); }
  }
  function ensure() {
    var el = list.children[sel];
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
  }
  function open() {
    if (!box) build();
    box.removeAttribute("hidden");
    document.body.classList.add("pal-open");
    input.value = "";
    render();
    input.focus();
  }
  function close() {
    if (box) box.setAttribute("hidden", "");
    document.body.classList.remove("pal-open");
  }
  var esc = window.DSW.esc;

  document.addEventListener("keydown", function (ev) {
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === "k" || ev.key === "K")) {
      ev.preventDefault();
      (box && !box.hasAttribute("hidden")) ? close() : open();
    }
  });
  var btn = document.getElementById("cmdk");
  if (btn) btn.addEventListener("click", open);
})();

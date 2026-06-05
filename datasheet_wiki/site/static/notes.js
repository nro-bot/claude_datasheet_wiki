// Personal per-section notes, saved in localStorage (per datasheet). Powers the
// "My notes" box on each section page and the aggregated notes.html page.
(function () {
  var PFX = window.DSW.key("note:");

  function get(sec) { try { return localStorage.getItem(PFX + sec) || ""; } catch (e) { return ""; } }
  function set(sec, val) {
    try { if (val) localStorage.setItem(PFX + sec, val); else localStorage.removeItem(PFX + sec); } catch (e) {}
  }
  function list() {
    var out = [];
    try {
      for (var i = 0; i < localStorage.length; i++) {
        var k = localStorage.key(i);
        if (k && k.indexOf(PFX) === 0) out.push({ sec: k.slice(PFX.length), text: localStorage.getItem(k) });
      }
    } catch (e) {}
    return out;
  }
  window.DSWNotes = { get: get, set: set, list: list };

  var esc = window.DSW.esc;

  // section-page editor
  var ta = document.getElementById("note");
  if (ta) {
    var sec = ta.getAttribute("data-section");
    ta.value = get(sec);
    var ind = document.getElementById("note-status");
    var t;
    ta.addEventListener("input", function () {
      clearTimeout(t);
      t = setTimeout(function () {
        set(sec, ta.value);
        if (ind) { ind.textContent = "Saved ✓"; setTimeout(function () { ind.textContent = ""; }, 1000); }
      }, 400);
    });
  }

  // aggregated notes.html
  var box = document.getElementById("notes-list");
  if (box) {
    var S = window.DSW_SECTIONS || {};
    var root = window.DSW_ROOT || "";
    var items = list().filter(function (n) { return (n.text || "").trim(); });
    if (!items.length) {
      box.innerHTML = '<p class="muted">No notes yet — open any section and write in its “My notes” box.</p>';
      return;
    }
    box.innerHTML = items.map(function (n) {
      var s = S[n.sec] || { t: n.sec, u: "" };
      var title = s.u ? '<a href="' + root + s.u + '">' + esc(s.t) + "</a>" : esc(s.t);
      return '<div class="note-entry"><h3>' + title + "</h3><pre>" + esc(n.text) + "</pre></div>";
    }).join("");
  }
})();

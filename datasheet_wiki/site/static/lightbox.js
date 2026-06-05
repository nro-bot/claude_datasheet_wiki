// Dependency-free image lightbox with left/right navigation.
// Exposes window.DSWLightbox.open(items, index) where items = [{src, caption}],
// reused by the reference/starred galleries. Also auto-wires static source-page
// thumbnails and inline figures on the current page (progressive enhancement —
// the links still open the image directly with JS off).
(function () {
  var esc = window.DSW.esc;
  var box, bImg, bCap, bPrev, bNext, items = [], idx = -1;

  function buildBox() {
    box = document.createElement("div");
    box.className = "lightbox";
    box.setAttribute("hidden", "");
    box.innerHTML =
      '<button class="lb-close" aria-label="Close (Esc)">×</button>' +
      '<button class="lb-nav lb-prev" aria-label="Previous (←)">‹</button>' +
      '<button class="lb-nav lb-next" aria-label="Next (→)">›</button>' +
      '<figure class="lb-stage"><img alt=""><figcaption></figcaption></figure>';
    document.body.appendChild(box);
    bImg = box.querySelector("img");
    bCap = box.querySelector("figcaption");
    bPrev = box.querySelector(".lb-prev");
    bNext = box.querySelector(".lb-next");
    bPrev.addEventListener("click", function (e) { e.stopPropagation(); show(idx - 1); });
    bNext.addEventListener("click", function (e) { e.stopPropagation(); show(idx + 1); });
    box.querySelector(".lb-close").addEventListener("click", close);
    box.addEventListener("click", function (e) {
      if (e.target === box || e.target.classList.contains("lb-stage")) close();
    });
    bImg.addEventListener("click", function () { if (items.length > 1) show(idx + 1); });
    document.addEventListener("keydown", function (e) {
      if (!box || box.hasAttribute("hidden")) return;
      if (e.key === "Escape") close();
      else if (e.key === "ArrowLeft") show(idx - 1);
      else if (e.key === "ArrowRight") show(idx + 1);
    });
  }

  function show(i) {
    idx = (i + items.length) % items.length;
    var it = items[idx];
    bImg.src = it.src;
    bImg.alt = it.caption || "";
    var multi = items.length > 1;
    bPrev.style.display = bNext.style.display = multi ? "" : "none";
    bCap.innerHTML =
      esc(it.caption || "") + (multi ? " (" + (idx + 1) + "/" + items.length + ")" : "") +
      ' · <a href="' + encodeURI(it.src) + '" target="_blank" rel="noopener">open original ↗</a>';
  }

  function open(list, start) {
    if (!list || !list.length) return;
    if (!box) buildBox();
    items = list;
    show(start || 0);
    box.removeAttribute("hidden");
    document.body.classList.add("lb-open");
  }
  function close() {
    if (box) { box.setAttribute("hidden", ""); bImg.src = ""; }
    document.body.classList.remove("lb-open");
  }

  window.DSWLightbox = { open: open };

  // Auto-wire whatever static thumbnails/figures exist on this page.
  function autowire() {
    var list = [], triggers = [];
    document.querySelectorAll(".thumb a").forEach(function (a) {
      var fig = a.closest(".thumb");
      var cap = fig ? fig.querySelector("figcaption") : null;
      list.push({ src: a.getAttribute("href"), caption: cap ? cap.textContent.trim() : a.querySelector("img") ? a.querySelector("img").alt : "" });
      triggers.push(a);
    });
    document.querySelectorAll("figure.dsfig img").forEach(function (img) {
      list.push({ src: img.getAttribute("src"), caption: img.alt || "Figure" });
      triggers.push(img);
    });
    triggers.forEach(function (t, i) {
      t.style.cursor = "zoom-in";
      t.addEventListener("click", function (e) { e.preventDefault(); open(list, i); });
    });
  }
  if (document.readyState !== "loading") autowire();
  else document.addEventListener("DOMContentLoaded", autowire);
})();

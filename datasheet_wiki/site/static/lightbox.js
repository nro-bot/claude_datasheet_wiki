// Minimal, dependency-free image lightbox. Progressive enhancement: page-image
// links still open the image directly when JS is off; with JS they open here.
(function () {
  // Collect viewable images in document order: source-page thumbnails (links to
  // the full image) and inline figures.
  var items = [];
  document.querySelectorAll(".thumb a").forEach(function (a) {
    var img = a.querySelector("img");
    var cap = a.parentElement.querySelector("figcaption");
    items.push({
      trigger: a,
      src: a.getAttribute("href"),
      caption: cap ? cap.textContent.trim() : (img ? img.alt : ""),
    });
  });
  document.querySelectorAll("figure.dsfig img").forEach(function (img) {
    items.push({ trigger: img, src: img.getAttribute("src"), caption: img.alt || "Figure" });
  });
  if (!items.length) return;

  // Build the overlay once.
  var box = document.createElement("div");
  box.className = "lightbox";
  box.setAttribute("hidden", "");
  box.innerHTML =
    '<button class="lb-close" aria-label="Close (Esc)">×</button>' +
    '<button class="lb-nav lb-prev" aria-label="Previous">‹</button>' +
    '<button class="lb-nav lb-next" aria-label="Next">›</button>' +
    '<figure class="lb-stage"><img alt=""><figcaption></figcaption></figure>';
  document.body.appendChild(box);

  var bImg = box.querySelector("img");
  var bCap = box.querySelector("figcaption");
  var idx = -1;

  function show(i) {
    idx = (i + items.length) % items.length;
    var it = items[idx];
    bImg.src = it.src;
    bImg.alt = it.caption;
    var more = items.length > 1 ? " (" + (idx + 1) + "/" + items.length + ")" : "";
    bCap.innerHTML =
      escapeHtml(it.caption) + more +
      ' · <a href="' + encodeURI(it.src) + '" target="_blank" rel="noopener">open original ↗</a>';
  }

  function open(i) {
    show(i);
    box.removeAttribute("hidden");
    document.body.classList.add("lb-open");
  }
  function close() {
    box.setAttribute("hidden", "");
    document.body.classList.remove("lb-open");
    bImg.src = "";
  }
  var escapeHtml = window.DSW.esc;

  items.forEach(function (it, i) {
    it.trigger.style.cursor = "zoom-in";
    it.trigger.addEventListener("click", function (e) {
      e.preventDefault();
      open(i);
    });
  });

  if (items.length < 2) {
    box.querySelectorAll(".lb-nav").forEach(function (b) { b.style.display = "none"; });
  }
  box.querySelector(".lb-close").addEventListener("click", close);
  box.querySelector(".lb-prev").addEventListener("click", function (e) { e.stopPropagation(); show(idx - 1); });
  box.querySelector(".lb-next").addEventListener("click", function (e) { e.stopPropagation(); show(idx + 1); });
  // click on the backdrop (not the image/controls) closes
  box.addEventListener("click", function (e) {
    if (e.target === box || e.target.classList.contains("lb-stage")) close();
  });
  bImg.addEventListener("click", function () { if (items.length > 1) show(idx + 1); });

  document.addEventListener("keydown", function (e) {
    if (box.hasAttribute("hidden")) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") show(idx - 1);
    else if (e.key === "ArrowRight") show(idx + 1);
  });
})();

// Progressive enhancement for the (server-rendered) sidebar navigation.
// The nav tree is already in the HTML, so navigation works with JS disabled.
// This adds collapsible branches, mobile menu toggle, and current-page focus.
(function () {
  var tree = document.getElementById("nav-tree");

  if (tree) {
    // collapse every branch, then re-open the path to the current page
    var branches = tree.querySelectorAll("li");
    branches.forEach(function (li) {
      var sub = li.querySelector(":scope > ul");
      var toggle = li.querySelector(":scope > .row > .toggle");
      if (!sub) return;
      li.classList.add("collapsed");
      if (toggle) {
        toggle.textContent = "▸";
        toggle.style.cursor = "pointer";
        toggle.addEventListener("click", function (e) {
          e.preventDefault();
          var collapsed = li.classList.toggle("collapsed");
          toggle.textContent = collapsed ? "▸" : "▾";
        });
      }
    });

    var current = tree.querySelector(".current");
    if (current) {
      var node = current;
      while (node && node !== tree) {
        if (node.tagName === "LI" && node.classList.contains("collapsed")) {
          node.classList.remove("collapsed");
          var t = node.querySelector(":scope > .row > .toggle");
          if (t && t.textContent) t.textContent = "▾";
        }
        node = node.parentElement;
      }
      current.scrollIntoView({ block: "center" });
    }
  }

  var toggle = document.getElementById("menu-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      document.body.classList.toggle("nav-open");
    });
  }

  // Open a collapsed <details> (e.g. Raw Text) when its anchor is navigated to.
  function openTargetDetails() {
    var h = location.hash;
    if (!h || h.length < 2) return;
    var el;
    try { el = document.querySelector(h); } catch (e) { return; }
    if (!el) return;
    var det = el.tagName === "DETAILS" ? el : (el.closest && el.closest("details"));
    if (det) det.open = true;
  }
  window.addEventListener("hashchange", openTargetDetails);
  openTargetDetails();

  // Permalinks: clicking the "#" next to a heading still updates the URL hash
  // (default), and additionally copies the absolute link to the clipboard.
  document.querySelectorAll(".permalink").forEach(function (a) {
    a.addEventListener("click", function () {
      var url = location.href.split("#")[0] + a.getAttribute("href");
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).catch(function () {});
      }
      var tip = document.createElement("span");
      tip.className = "copied";
      tip.textContent = "Link copied";
      a.appendChild(tip);
      setTimeout(function () { tip.remove(); }, 1200);
    });
  });
})();

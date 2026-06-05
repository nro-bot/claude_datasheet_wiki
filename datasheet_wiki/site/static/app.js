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
})();

// Sidebar navigation: render the tree from window.DSW_NAV, support collapse,
// and highlight the current page. Works fully offline (no fetch).
(function () {
  var root = window.DSW_ROOT || "";
  var here = location.pathname.split("/").pop();

  function build(nodes) {
    var ul = document.createElement("ul");
    nodes.forEach(function (n) {
      var li = document.createElement("li");
      var row = document.createElement("div");
      row.className = "row";
      var hasKids = n.children && n.children.length;
      var toggle = document.createElement("span");
      toggle.className = "toggle";
      toggle.textContent = hasKids ? "▸" : "";
      row.appendChild(toggle);

      var a = document.createElement("a");
      a.href = root + n.url;
      if (n.number) {
        var num = document.createElement("span");
        num.className = "secnum";
        num.textContent = n.number;
        a.appendChild(num);
        a.appendChild(document.createTextNode(" "));
      }
      a.appendChild(document.createTextNode(n.title));
      row.appendChild(a);
      li.appendChild(row);

      var isCurrent = n.url.split("/").pop() === here;
      if (isCurrent) li.classList.add("current");

      if (hasKids) {
        var sub = build(n.children);
        li.appendChild(sub);
        li.classList.add("collapsed");
        toggle.addEventListener("click", function (e) {
          e.preventDefault();
          li.classList.toggle("collapsed");
          toggle.textContent = li.classList.contains("collapsed") ? "▸" : "▾";
        });
        // auto-expand the branch containing the current page
        if (containsCurrent(n)) {
          li.classList.remove("collapsed");
          toggle.textContent = "▾";
        }
      }
      ul.appendChild(li);
    });
    return ul;
  }

  function containsCurrent(node) {
    if (node.url.split("/").pop() === here) return true;
    return (node.children || []).some(containsCurrent);
  }

  var tree = document.getElementById("nav-tree");
  if (tree && window.DSW_NAV) {
    tree.appendChild(build(window.DSW_NAV));
    var cur = tree.querySelector(".current");
    if (cur) cur.scrollIntoView({ block: "center" });
  }

  var toggle = document.getElementById("menu-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      document.body.classList.toggle("nav-open");
    });
  }
})();

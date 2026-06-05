// Per-datasheet page bookmarks ("star" pages). State lives in localStorage,
// namespaced by window.DSW_ID, so different datasheets don't collide. Exposed as
// window.DSWStars for the reference/starred pages. Falls back to an in-memory
// store if localStorage is unavailable (e.g. some browsers over file://).
(function () {
  var KEY = "dsw:" + (window.DSW_ID || "datasheet") + ":stars";
  var mem = null; // in-memory fallback
  var subs = [];

  function read() {
    if (mem) return mem.slice();
    try {
      var v = JSON.parse(localStorage.getItem(KEY) || "[]");
      return Array.isArray(v) ? v : [];
    } catch (e) {
      mem = mem || [];
      return mem.slice();
    }
  }
  function write(arr) {
    arr = arr.filter(function (x, i) { return arr.indexOf(x) === i; }).sort(function (a, b) { return a - b; });
    try {
      localStorage.setItem(KEY, JSON.stringify(arr));
    } catch (e) {
      mem = arr.slice();
    }
    subs.forEach(function (fn) { try { fn(arr.slice()); } catch (e) {} });
    return arr;
  }

  var API = {
    list: function () { return read(); },
    has: function (n) { return read().indexOf(+n) !== -1; },
    add: function (n) { var a = read(); if (a.indexOf(+n) === -1) a.push(+n); return write(a); },
    remove: function (n) { return write(read().filter(function (x) { return x !== +n; })); },
    toggle: function (n) { return API.has(n) ? API.remove(n) : API.add(n); },
    clear: function () { return write([]); },
    subscribe: function (fn) { subs.push(fn); return fn; },
    decorate: function () { decorate(); },
  };
  window.DSWStars = API;

  // Enhance source-page thumbnails with a star toggle.
  function decorate() {
    document.querySelectorAll(".thumb[data-page]").forEach(function (fig) {
      if (fig.querySelector(".star")) return;
      var n = +fig.getAttribute("data-page");
      var btn = document.createElement("button");
      btn.className = "star";
      btn.type = "button";
      btn.title = "Star this page for your Personal Reference";
      btn.setAttribute("aria-label", "Star page " + n);
      btn.textContent = "★";
      sync(btn, n);
      btn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        API.toggle(n);
      });
      fig.appendChild(btn);
    });
  }
  function sync(btn, n) {
    var on = API.has(n);
    btn.classList.toggle("on", on);
    btn.setAttribute("aria-pressed", on ? "true" : "false");
  }
  function syncAll() {
    document.querySelectorAll(".thumb[data-page] .star").forEach(function (btn) {
      sync(btn, +btn.parentElement.getAttribute("data-page"));
    });
  }

  if (document.readyState !== "loading") decorate();
  else document.addEventListener("DOMContentLoaded", decorate);
  API.subscribe(syncAll);
})();

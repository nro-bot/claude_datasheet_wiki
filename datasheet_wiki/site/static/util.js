// Tiny shared helpers for the wiki's client scripts. Loaded before all others.
(function () {
  window.DSW = window.DSW || {};
  // HTML-escape a string for safe insertion into markup.
  window.DSW.esc = function (s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  };
  // Build a localStorage key namespaced to this datasheet.
  window.DSW.key = function (suffix) {
    return "dsw:" + (window.DSW_ID || "datasheet") + ":" + suffix;
  };
})();

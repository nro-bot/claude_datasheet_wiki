// Interactive bit-field calculator. For every register table (.register with a
// .bits table) it adds a collapsible panel: set field values -> live register
// hex/binary, or paste a hex value to decode it back into the fields.
(function () {
  function parseBits(s) {
    s = (s || "").replace(/\s/g, "");
    var m = s.match(/^(\d+)[:\-–](\d+)$/);
    if (m) { var a = +m[1], b = +m[2]; return { hi: Math.max(a, b), lo: Math.min(a, b) }; }
    if (/^\d+$/.test(s)) return { hi: +s, lo: +s };
    return null;
  }

  function build(reg) {
    var table = reg.querySelector("table.bits");
    if (!table || reg.querySelector(".bitcalc")) return;
    var fields = [];
    table.querySelectorAll("tbody tr").forEach(function (tr) {
      var cells = tr.querySelectorAll("td");
      if (cells.length < 2) return;
      var bits = parseBits(cells[0].textContent);
      if (!bits) return;
      var name = (cells[1].textContent || "").trim() || (bits.hi + ":" + bits.lo);
      fields.push({ hi: bits.hi, lo: bits.lo, name: name });
    });
    if (!fields.length) return;

    var maxBit = fields.reduce(function (m, f) { return Math.max(m, f.hi); }, 0);
    var width = maxBit < 8 ? 8 : maxBit < 16 ? 16 : maxBit < 32 ? 32 : 32;
    var digits = width / 4;

    var details = document.createElement("details");
    details.className = "bitcalc";
    var rows = fields.map(function (f, i) {
      var span = f.hi - f.lo + 1;
      var ctl = span === 1
        ? '<input type="checkbox" data-i="' + i + '">'
        : '<input type="number" min="0" max="' + ((Math.pow(2, span) - 1)) + '" value="0" data-i="' + i + '" style="width:6em">';
      return '<tr><td class="bc-bits">' + (f.hi === f.lo ? f.hi : f.hi + ":" + f.lo) +
        '</td><td><code>' + escapeHtml(f.name) + "</code></td><td>" + ctl + "</td></tr>";
    }).join("");
    details.innerHTML =
      "<summary>Bit calculator (" + width + "-bit)</summary>" +
      '<div class="bc-body"><table class="bc-fields"><tbody>' + rows + "</tbody></table>" +
      '<div class="bc-out"><label>Value <code class="bc-hex">0x' + zero(digits) + "</code></label>" +
      '<label>Binary <code class="bc-bin"></code></label>' +
      '<label>Decode hex <input class="bc-decode" placeholder="0x.." style="width:8em"></label></div></div>';
    reg.appendChild(details);

    var inputs = details.querySelectorAll(".bc-fields input");
    var hexOut = details.querySelector(".bc-hex");
    var binOut = details.querySelector(".bc-bin");
    var decode = details.querySelector(".bc-decode");

    function recompute() {
      var v = 0;
      inputs.forEach(function (inp) {
        var f = fields[+inp.getAttribute("data-i")];
        var span = f.hi - f.lo + 1;
        var fv = inp.type === "checkbox" ? (inp.checked ? 1 : 0) : (parseInt(inp.value, 10) || 0);
        var mask = span >= 32 ? 0xffffffff : (Math.pow(2, span) - 1);
        fv = fv & mask;
        v += fv * Math.pow(2, f.lo); // avoid 32-bit shift overflow
      });
      v = v >>> 0;
      hexOut.textContent = "0x" + v.toString(16).toUpperCase().padStart(digits, "0");
      binOut.textContent = v.toString(2).padStart(width, "0").replace(/(.{4})(?=.)/g, "$1 ");
    }
    inputs.forEach(function (inp) { inp.addEventListener("input", recompute); });
    decode.addEventListener("input", function () {
      var v = parseInt(decode.value.replace(/^0x/i, ""), 16);
      if (isNaN(v)) return;
      v = v >>> 0;
      inputs.forEach(function (inp) {
        var f = fields[+inp.getAttribute("data-i")];
        var span = f.hi - f.lo + 1;
        var fv = Math.floor(v / Math.pow(2, f.lo)) & (span >= 32 ? 0xffffffff : (Math.pow(2, span) - 1));
        if (inp.type === "checkbox") inp.checked = !!fv; else inp.value = fv;
      });
      recompute();
    });
    recompute();
  }

  function zero(n) { return new Array(n + 1).join("0"); }
  function escapeHtml(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function run() { document.querySelectorAll(".register").forEach(build); }
  if (document.readyState !== "loading") run();
  else document.addEventListener("DOMContentLoaded", run);
})();

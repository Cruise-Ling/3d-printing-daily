/* ADAPTER: resin_tpl.html（光固化，复用页面已有的 EXPORT_FIELDS 与 filtered()） */
var ADAPTER = (function () {
  function F() {
    try {
      if (typeof EXPORT_FIELDS !== "undefined" && EXPORT_FIELDS.length) return EXPORT_FIELDS;
    } catch (e) {}
    return [["id", "记录编号"]];
  }
  function MT() { try { return META || {}; } catch (e) { return {}; } }
  return {
    kind: "resin",
    title: "光固化专栏",
    ref: (function () { var m = MT(); return m.refDate || m.updated || ""; })(),
    fields: F,
    rows: function () {
      try { return filtered(); } catch (e) {
        try { return (ITEMS || []).slice(); } catch (e2) { return []; }
      }
    },
    scope: function () {
      try {
        var o = {}, n = 0;
        ["subject", "brand", "model", "region", "source", "scope", "range", "problem", "q"].forEach(function (k) {
          var v = S[k];
          if (v && v !== "all") { o[k] = v; n++; }
        });
        return n ? JSON.stringify(o) : "无筛选（全部）";
      } catch (e) { return "—"; }
    }
  };
})();

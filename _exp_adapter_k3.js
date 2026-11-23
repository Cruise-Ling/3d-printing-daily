/* ADAPTER: creality-k3.html（H3C 由本页派生，改这里后须重跑 _build_h3c.py） */
var ADAPTER = (function () {
  var F = [
    ["id", "记录编号"], ["date", "入库日期"], ["publishedAt", "发布日期"],
    ["channel", "渠道归属"], ["sourceType", "信源类型"], ["contentKind", "载体"],
    ["platform", "平台"], ["site", "站点"], ["country", "区域"], ["language", "语种"],
    ["sentiment", "情感"], ["problemPoints", "问题点"], ["topics", "主题"],
    ["heat", "热度"], ["isP0", "P0"], ["reviewGrade", "复核状态"],
    ["originalText", "原文"], ["translation", "中文译文"], ["summaryCn", "中文摘要"],
    ["sourceLink", "原文链接"]
  ];
  function D() { try { return K3_FEEDBACK_DATA || {}; } catch (e) { return {}; } }
  return {
    kind: "k3",
    title: "Creality K3 用户反馈",
    ref: (function () { var d = D(); return d.updated || d.updatedAt || ""; })(),
    fields: function () { return F; },
    rows: function () {
      try { return applyFilters(); } catch (e) {
        try { return (K3_FEEDBACK_DATA.items || []).slice(); } catch (e2) { return []; }
      }
    },
    scope: function () {
      try {
        var o = {}, n = 0;
        ["sentiment", "channel", "sourceType", "topic", "contentKind", "platform", "q"].forEach(function (k) {
          var v = activeFilters[k];
          if (v && v !== "all") { o[k] = v; n++; }
        });
        return n ? JSON.stringify(o) : "无筛选（全部）";
      } catch (e) { return "—"; }
    }
  };
})();

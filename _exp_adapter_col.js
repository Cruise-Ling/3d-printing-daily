/* ADAPTER: _col_shell.html（mBox / 软件 / 全彩 三页同源，按 KIND 切字段）
   数据必须经 window.__colExp 取：主逻辑包在独立 IIFE 里，外部拿不到 apply()/S */
var ADAPTER = (function () {
  function H() { try { return window.__colExp || {}; } catch (e) { return {}; } }
  var h = H();
  var kind = h.kind || "col";
  var meta = h.meta || {};

  var F_MBOX = [
    ["uid", "记录编号"], ["date", "发布日期"], ["platform", "平台"], ["site", "站点"],
    ["channel", "渠道归属"], ["country", "区域"], ["language", "语种"],
    ["title", "原文标题"], ["titleCn", "标题中译"],
    ["signal", "信号档"], ["heat", "热度"],
    ["productLine", "产品线"], ["model", "机型"], ["problemType", "问题类型"], ["grade", "判定"],
    ["replyCount", "回复数"], ["views", "浏览量"], ["likeCount", "点赞数"],
    ["sourceType", "信源类型"], ["author", "作者"],
    ["textCn", "中文摘要"], ["originalText", "原文"], ["url", "原文链接"]
  ];
  var F_SW = [
    ["uid", "记录编号"], ["date", "发布日期"], ["platform", "平台"], ["site", "站点"],
    ["channel", "渠道归属"], ["country", "区域"], ["language", "语种"],
    ["title", "原文标题"], ["titleCn", "标题中译"],
    ["productLine", "产品线"], ["model", "机型"],
    ["stage", "使用环节"], ["tool", "工具"], ["toolName", "工具名"], ["flair", "版块"],
    ["problemType", "问题类型"], ["grade", "判定"],
    ["replyCount", "回复数"], ["views", "浏览量"], ["likeCount", "点赞数"],
    ["sourceType", "信源类型"], ["author", "作者"],
    ["textCn", "中文摘要"], ["originalText", "原文"], ["url", "原文链接"]
  ];
  var F_FC = [
    ["uid", "记录编号"], ["date", "发布日期"], ["platform", "平台"], ["site", "站点"],
    ["channel", "渠道归属"], ["country", "区域"], ["language", "语种"],
    ["title", "原文标题"], ["titleCn", "标题中译"],
    ["model", "机型"], ["tier", "技术档次"], ["techRoute", "技术路线"], ["discussLevel", "讨论度"],
    ["heat", "热度"], ["heatScore", "热度分"],
    ["sourceType", "信源类型"], ["author", "作者"], ["grade", "判定"],
    ["textCn", "中文摘要"], ["originalText", "原文"], ["url", "原文链接"]
  ];

  return {
    kind: kind,
    title: meta.title || meta.name || ("专栏 · " + kind),
    ref: meta.refDate || meta.updated || "",
    fields: function () {
      if (kind === "mbox") return F_MBOX;
      if (kind === "fc") return F_FC;
      return F_SW;
    },
    rows: function () {
      var x = H();
      if (typeof x.rows === "function") { try { return x.rows(); } catch (e) { return []; } }
      return [];
    },
    scope: function () {
      var x = H(), st = x.state || {};
      try {
        var o = {}, n = 0;
        ["product", "problem", "model", "grade", "channel", "source", "platform",
          "lang", "stage", "toolType", "topic", "range", "tech", "level", "q"].forEach(function (k) {
          var v = st[k];
          if (v && v !== "all") { o[k] = v; n++; }
        });
        return n ? JSON.stringify(o) : "无筛选（全部）";
      } catch (e) { return "—"; }
    }
  };
})();

# -*- coding: utf-8 -*-
"""K3 明细流：新增「渠道」按钮组筛选器（YouTube / B 站 / Reddit / 什么值得买…）
   K3 的 platform 字段就是渠道级（site 与之基本一致），因此直接复用 activeFilters.platform，
   不新增状态键，避免与 S4 渠道面板的下钻出现两套口径。"""
import io

F = "creality-k3.html"
s = io.open(F, encoding="utf-8").read()
o = s

anchor = '''  html += '<span class="filter-sep"></span><span class="filter-label">信源</span>';
  ["all","用户","媒体","社区综述","电商","官方"].forEach(function(t){'''

new_block = '''  // ---------- 渠道（平台级）：用户 2026-10-27 要求明细流能直接按 YouTube / Reddit 这类具体渠道筛 ----------
  // 用按钮组而不是下拉：一眼看到各渠道条数，单击即筛、再点取消。
  // 平台超过 8 个时只把「≥5 条」的前 8 个做成按钮，长尾收进「其他渠道」下拉（K3 有 14 个平台，
  // 其中 4 个占 96%，长尾全是 1–2 条的小站，铺开会把筛选栏撑成两屏）。
  html += '<span class="filter-sep"></span><span class="filter-label">渠道</span>';
  (function(){
    const base = applyFilters("platform");
    const cnt = {}, rawOf = {};
    base.forEach(function(x){
      const raw = x.platform || "未标注";
      // 「B 站」与「B站」中间空格不同，不归一会变成两个渠道
      const nm = String(raw).replace(/\\s+/g, "") === "B站" ? "B站" : raw;
      cnt[nm] = (cnt[nm] || 0) + 1;
      if (!(nm in rawOf)) rawOf[nm] = raw;
    });
    const names = Object.keys(cnt).sort(function(a, b){ return cnt[b] - cnt[a]; });
    const shown = names.length <= 8 ? names : names.filter(function(k){ return cnt[k] >= 5; }).slice(0, 8);
    html += '<button class="filter-btn ' + (activeFilters.platform === "all" ? "active" : "") +
      '" onclick="setF(\\'platform\\',\\'all\\')">全部 ' + base.length + '</button>';
    shown.forEach(function(nm){
      const v = String(rawOf[nm]).replace(/'/g, "\\\\'");
      html += '<button class="filter-btn ' + (activeFilters.platform === rawOf[nm] ? "active" : "") +
        '" onclick="setF(\\'platform\\',\\'' + v + '\\')" title="只看 ' + esc(nm) + ' 的内容">' +
        esc(nm) + ' ' + cnt[nm] + '</button>';
    });
    const rest = names.filter(function(k){ return shown.indexOf(k) < 0; });
    if (rest.length) {
      html += '<select onchange="if(this.value)setF(\\'platform\\',this.value)">' +
        '<option value="">其他渠道 ' + rest.length + ' 个</option>' +
        rest.map(function(nm){
          return '<option value="' + esc(rawOf[nm]) + '">' + esc(nm) + ' ' + cnt[nm] + '</option>';
        }).join("") + '</select>';
    }
  })();
''' + anchor

assert anchor in s
s = s.replace(anchor, new_block, 1)

# 摘要条：platform 现在是渠道级，label 与显示名一起校正
old_chip = '''  if (activeFilters.platform !== "all") parts.push(fsumChip("站点：" + activeFilters.platform, "platform"));'''
new_chip = '''  if (activeFilters.platform !== "all") {
    const pn = String(activeFilters.platform).replace(/\\s+/g, "") === "B站" ? "B站" : activeFilters.platform;
    parts.push(fsumChip("渠道：" + pn, "platform"));
  }'''
assert old_chip in s
s = s.replace(old_chip, new_chip, 1)

if s != o:
    io.open(F, "w", encoding="utf-8", newline="\n").write(s)
print("K3 渠道筛选器完成，%d 字符" % len(s))

# -*- coding: utf-8 -*-
"""专栏结构规范 v1.0 · 修正补丁（幂等）
1) mBox 的「B 站」实际平台名是「B站」，覆盖清单按名字精确匹配，名字必须与数据一致
2) 摘要与标题重复时不渲染（短文原文=标题的情况）
3) 原文很短时不给「展开全文」按钮
4) 已选条件里的关注点显示中文名
5) 英文标题 clamp 2 行
"""
import io

TARGETS = ["creality-mbox.html", "software-columns.html"]

NEW_SUMMARY = r'''function clipTxt(s,n){
  s = String(s||"").replace(/\s+/g," ").trim();
  return s.length>n ? s.slice(0,n)+"…" : s;
}
/** 卡片摘要：先人工摘要，再译文首句，最后原文首句。目标是不点开也知道这条在说什么。
    摘要是标题的重复时返回空串 —— 宁可少一行，也不让卡片出现两句一样的话。 */
function summaryOf(it){
  var t = String(it.titleCn||it.title||"").trim();
  var sm = "";
  if(it.summaryCn && String(it.summaryCn).trim()){
    sm = String(it.summaryCn).trim();
  }else{
    function firstSent(body, min){
      var m = body.match(/^[\s\S]{0,220}?[。！？!?]/);
      if(m && m[0].length>=min) return m[0];
      return body;
    }
    var cn = String(it.textCn||"").trim();
    var raw = String(it.originalText||"").trim();
    if(raw.indexOf(t)===0) raw = raw.slice(t.length).trim();
    if(cn) sm = clipTxt(firstSent(cn,40), 160);
    else if(raw) sm = clipTxt(firstSent(raw,40), 160);
    else sm = "";
  }
  var a = sm.replace(/[…\s]/g,""), b = t.replace(/[…\s]/g,"");
  if(!a || a===b || (a.length>10 && b.indexOf(a)===0)) return "";
  return sm;
}
'''

OLD_SUMMARY_HEAD = "function clipTxt(s,n){"


def patch_bzhan(s):
    n = s.count('"B 站"')
    if n == 0:
        return s, "bz:skip"
    s = s.replace('["B 站","todo","国内创作者实测 · 待接入"]', '["B站","todo","国内创作者实测 · 待接入"]')
    s = s.replace('["B 站","ok","国内主源 · 2026-10-26 接入"]', '["B站","ok","国内主源 · 2026-10-26 接入"]')
    return s, "bz:n=%d" % n


def patch_summary(s):
    if "宁可少一行" in s:
        return s, "sum:skip"
    i = s.find(OLD_SUMMARY_HEAD)
    if i < 0:
        return s, "sum:NO-HEAD"
    j = s.find("function cardHTML(it){", i)
    if j < 0:
        return s, "sum:NO-CARD"
    s = s[:i] + NEW_SUMMARY + s[j:]
    return s, "sum:ok"


def patch_card_body(s):
    old = ("""    '<div class="c-title">'+esc(title)+'</div>'+
    (enT? '<div class="c-title-en">'+esc(enT)+'</div>':'')+
    '<div class="c-sum">'+esc(sm)+'</div>'+
    ((full||cnBody)? '<div class="c-more" data-exp="1">展开全文 ▾</div>':'')+""")
    new = ("""    '<div class="c-title">'+esc(title)+'</div>'+
    (enT? '<div class="c-title-en">'+esc(enT)+'</div>':'')+
    (sm? '<div class="c-sum">'+esc(sm)+'</div>':'')+
    (canFold? '<div class="c-more" data-exp="1">展开全文 ▾</div>':'')+""")
    if new in s:
        return s, "body:skip"
    if old not in s:
        return s, "body:NO-MATCH"
    s = s.replace(old, new, 1)
    # 声明 canFold
    o2 = "  var mt = (cnT===rawT || !enT) ? \"\" : \"\";\n"
    n2 = ("  var floor = Math.max(60, sm.length + 20);\n"
          "  var canFold = full.length > floor || cnBody.length > floor;\n")
    if o2 in s:
        s = s.replace(o2, n2, 1)
    else:
        o2b = "  var cnBody = it.textCn || \"\";\n"
        n2b = o2b + ("  var floor = Math.max(60, sm.length + 20);\n"
                     "  var canFold = full.length > floor || cnBody.length > floor;\n")
        s = s.replace(o2b, n2b, 1)
    return s, "body:ok"


def patch_chip(s):
    anchor = '  if(k==="product") return PRODUCT_NAME[v]||v;'
    add = ('\n  if(k==="topic"){ var tn=""; TOPIC_MBOX.forEach(function(t){ if(t[0]===v) tn=t[1]; }); return tn||v; }')
    if 'k==="topic"' in s:
        return s, "chip:skip"
    if anchor not in s:
        return s, "chip:NO-MATCH"
    return s.replace(anchor, anchor + add, 1), "chip:ok"


def patch_css3(s):
    if ".c-title-en{display:-webkit-box" in s:
        return s, "css3:skip"
    return s.replace("</style>",
                     ".c-title-en{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}\n</style>",
                     1), "css3:ok"


def main():
    for f in TARGETS:
        raw = io.open(f, encoding="utf-8").read()
        s = raw
        out = []
        for fn in (patch_bzhan, patch_summary, patch_card_body, patch_chip, patch_css3):
            s, r = fn(s)
            out.append(r)
        if s != raw:
            io.open(f, "w", encoding="utf-8").write(s)
        print("%-26s %s" % (f, " ".join(out)))


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""专栏结构规范 v1.0 · JS 改造（幂等）

1) renderPanels 一拆三 -> renderOverview / renderTopics / renderChannels
2) cardHTML 全文 -> 摘要（clamp 4 行 + 就地展开）
3) 分页器 -> 页码下拉直达
4) S / match / clearAll / LABELS 增加 topic 维度
"""
import re, io

TARGETS = ["creality-mbox.html", "software-columns.html"]

CSS2 = """.topic-grid>.stgrid,.topic-grid>.stgap,.topic-grid>.stnote{grid-column:1/-1}
.pgsel{background:#21262d;border:1px solid #30363d;border-radius:6px;padding:4px 8px;color:#c9d1d9;font-size:12px;cursor:pointer;font-family:inherit}
</style>"""

# ---------- S3/S4 + 概览 ----------
NEW_PANELS = r'''
/* ================= S2 总体概览 ================= */
function renderOverview(){
  var A=document.getElementById("ovA"), B=document.getElementById("ovB");
  document.getElementById("ovHint").textContent = "分析口径：有效档单列，逐项可点筛选";
  if(KIND==="sw"){
    var p1 = applyValid("problem");
    var arr1 = Object.keys(countBy(p1,function(x){return x.problemType||"未分类";}))
      .map(function(k){return [k,countBy(p1,function(x){return x.problemType||"未分类";})[k]];})
      .sort(function(a,b){return b[1]-a[1];});
    var mx1 = Math.max.apply(null, arr1.map(function(z){return z[1];}).concat([1]));
    A.innerHTML = panel("问题类型构成","分析口径 · 有效 "+p1.length+" 条",
      arr1.length? arr1.map(function(r){
        var lab = PROBLEM_NAME[r[0]]||r[0];
        var on = S.problem===r[0]?" on":"";
        return '<div class="brow'+on+'" data-pick="problem" data-val="'+esc(r[0])+'">'+
          '<span class="nm" title="'+esc(lab)+'">'+esc(lab)+'</span>'+
          '<span class="track"><i class="fill" style="width:'+(r[1]/mx1*100)+'%;background:'+(PROBLEM_COLOR[r[0]]||"#8b949e")+'"></i></span>'+
          '<span class="vl">'+r[1]+' · '+(r[1]/p1.length*100).toFixed(1)+'%</span></div>';
      }).join("") : '<div class="empty">当前筛选下无有效档条目</div>');

    var p3 = apply("major");
    var arr3 = Object.keys(countBy(p3,function(x){return majorOf(x.version);}))
      .map(function(k){return [k,countBy(p3,function(x){return majorOf(x.version);})[k]];})
      .sort(function(a,b){return parseFloat(b[0])-parseFloat(a[0]);});
    var mx3 = Math.max.apply(null, arr3.map(function(z){return z[1];}).concat([1]));
    B.innerHTML = panel("主版本热度","条数 · 点击可筛选",
      arr3.length? arr3.map(function(r){
        var on = S.major===r[0]?" on":"";
        return '<div class="brow'+on+'" data-pick="major" data-val="'+esc(r[0])+'">'+
          '<span class="nm">'+esc(r[0])+'</span><span class="track"><i class="fill" style="width:'+(r[1]/mx3*100)+'%;background:'+(VER_COLOR[r[0].replace(".x","")]||"#8b949e")+'"></i></span>'+
          '<span class="vl">'+r[1]+' 条</span></div>';
      }).join("")+
      '<div class="pnote">原「版本 × 问题类型」矩阵已删除：35 格里多数只有 1–2 条，且 237 条泛讨论进不去，读不出规律。</div>'
      : '<div class="empty">当前筛选下无版本数据</div>');
  }else{
    var pA = apply("channel");
    var arrA = Object.keys(countBy(pA,function(x){return x.channel;}))
      .map(function(k){return [k,countBy(pA,function(x){return x.channel;})[k]];})
      .sort(function(a,b){return b[1]-a[1];});
    A.innerHTML = panel("信源结构","按渠道组 · 点击可筛选",
      arrA.length? barRows(arrA,pA.length,"channel",null) : '<div class="empty">暂无数据</div>');
    var pB = apply("source");
    var arrB = Object.keys(countBy(pB,function(x){return x.sourceType;}))
      .map(function(k){return [k,countBy(pB,function(x){return x.sourceType;})[k]];})
      .sort(function(a,b){return b[1]-a[1];});
    A.innerHTML += panel("载体结构","媒体 / 官方 · 点击可筛选",
      arrB.length? barRows(arrB,pB.length,"source",function(){return "#bc8cff";}) : '<div class="empty">暂无数据</div>');
    var noProblem = ITEMS.filter(function(x){return x.problemType;}).length;
    B.innerHTML = panel("问题点 Top","—",
      noProblem? '<div class="empty">已有 '+noProblem+' 条可归类的问题点</div>'
      : '<div class="empty">当前 '+ITEMS.length+' 条均为媒体报道与官方物料，尚无可归类到具体问题点的用户反馈。<br>该面板在有第一条用户反馈后自动填充，不需要改页面。</div>', true);
  }
}

/* ================= S3 专项分析 =================
   规范：专项分析 = 该专栏的「组织维度」，必须在此显式定义（不是从数据 group by 出来）。
   维度定义在前，0 条也出卡片并标「待样本」—— 避免「没出现」被读成「没有问题」。
   K3 用机型特性 / 软件用实现路径六段 / mBox 用机型关注点。 */
var TOPIC_MBOX = [
  ["safety","儿童安全 / 五重防护","高温件封闭 · 门锁 · 材料安全",/(安全|防护|儿童|孩子|小朋友|低龄|PEGI|门锁|烫手)/],
  ["ai","AI 生成 / 文生 3D","自然语言或图片直接生成模型",/(AI|人工智能|生成|文生|图生|灵感)/i],
  ["park","Creality Park 应用","配套 App 与云平台联动",/(Park|配套\s*app|应用|手机|安卓|iOS)/i],
  ["compact","紧凑体积","153 × 153 × 153 mm · 桌面占用",/(紧凑|小巧|体积|153|立方|桌面)/],
  ["ready","开箱即用","免组装 · 上手门槛",/(开箱|免组装|不用组装|即用|上手|独立造物)/],
  ["price","价格与定位","家庭可接受的价格带",/(价格|售价|定价|美元|性价比|多少钱)/],
  ["material","耗材与多色","PLA 与耗材体系",/(耗材|多色|材料|PLA|丝材|换色)/i],
  ["noise","噪音与静音","运行噪声表现",/(噪音|噪声|静音|分贝|dB)/i],
  ["eco","生态与模型资源","模型库与社区内容",/(模型库|生态|社区|素材|资源)/]
];
function topicText(it){ return [it.title,it.titleCn,it.originalText,it.textCn].join(" "); }
function topicHit(it,key){
  if(!key) return true;
  var def = null;
  TOPIC_MBOX.forEach(function(t){ if(t[0]===key) def=t; });
  if(!def) return true;
  if(KIND==="sw") return (it.stage||"跨环节")===key;
  return def[3].test(topicText(it));
}
function renderTopics(){
  var hint = document.getElementById("topicHint");
  var grid = document.getElementById("topicGrid"), dist = document.getElementById("topicDist");
  if(KIND==="sw"){
    hint.textContent = "主维度：用户实现路径六段 · 点卡片筛明细";
    grid.innerHTML = stagePanel();
    var base = apply("toolType");
    var tc = countBy(base, function(x){ return x.toolType || "__none__"; });
    var arrT = Object.keys(tc).map(function(k){ return [k, tc[k]]; })
      .sort(function(a,b){
        if(a[0]==="__none__") return 1;
        if(b[0]==="__none__") return -1;
        return b[1]-a[1];
      });
    if(!tc["model"] && S.toolType!=="model") arrT.splice(Math.max(arrT.length-1,0), 0, ["model", 0]);
    var mxT = Math.max.apply(null, arrT.map(function(z){ return z[1]; }).concat([1]));
    dist.innerHTML = panel("工具结构","辅维度 · 按功能类型 · 点击行可筛选",
      arrT.length? arrT.map(function(r){
        var key = r[0]==="__none__"? "" : r[0];
        var val = r[0]==="__none__"? "__none__" : r[0];
        var zero = r[1]===0;
        var on = S.toolType===val? " on":"";
        return '<div class="brow'+on+(zero?" zero":"")+'" data-pick="toolType" data-val="'+esc(val)+'">'+
          '<span class="nm">'+esc(TOOLTYPE_NAME[key]||key)+(zero?' <em class="gapm">缺口</em>':'')+'</span>'+
          '<span class="track"><i class="fill" style="width:'+(r[1]/mxT*100).toFixed(1)+'%;background:'+(TOOLTYPE_COLOR[key]||"#8b949e")+'"></i></span>'+
          '<span class="vl">'+r[1]+' · '+(r[1]/base.length*100).toFixed(1)+'%</span></div>'+
          toolSubHTML(key, base);
      }).join("")+
      '<div class="pnote"><i class="dot self"></i>自家 <i class="dot comp" style="margin-left:10px"></i>竞品'+
      ' —— 归属只做色点标识。每条只归一个类型（按主工具）。<br>'+
      '覆盖率提示：论坛帖多数未提具体工具名，'+(tc["__none__"]||0)+' 条落在「未提具体工具」，'+
      '因此这一层的结构只反映「提到工具的帖」，不代表全站。</div>'
      : '<div class="empty">暂无数据</div>');
    return;
  }
  // mBox：机型关注点 · 关键词预标注（诚实标注，不冒充人工结论）
  hint.textContent = "按机型关注点 · 关键词预标注（未经人工复核）· 点卡片筛明细";
  var live = [], pend = [], cnt = {};
  TOPIC_MBOX.forEach(function(t){
    var n = ITEMS.filter(function(it){ return t[3].test(topicText(it)); }).length;
    cnt[t[0]] = n;
    if(n){
      var on = S.topic===t[0]? " on":"";
      live.push('<div class="tcard'+on+'" data-pick="topic" data-val="'+t[0]+'" title="点击只看该关注点">'+
        '<div class="tn"><span>'+esc(t[1])+'</span><b>'+n+'</b></div>'+
        '<div class="td">'+esc(t[2])+'</div></div>');
    }else{
      pend.push('<div class="tcard zero" title="当前 0 条样本：既不等于没有该问题，也不等于没有问题以外的结论">'+
        '<div class="tn"><span>'+esc(t[1])+'</span><b style="color:#6e7681">0</b></div>'+
        '<div class="td">'+esc(t[2])+'</div>'+
        '<div class="tflag">待样本 · 空白 ≠ 无问题</div></div>');
    }
  });
  grid.innerHTML = live.join("") + pend.join("");
  var arr = TOPIC_MBOX.map(function(t){ return [t[0], cnt[t[0]]||0, t[1]]; })
    .filter(function(r){ return r[1]>0; })
    .sort(function(a,b){ return b[1]-a[1]; });
  var mx = Math.max.apply(null, arr.map(function(r){ return r[1]; }).concat([1]));
  dist.innerHTML = panel("关注点分布",
    "一条可命中多个关注点，故合计大于样本数 · 点击行可筛选",
    arr.length? arr.map(function(r){
      var on = S.topic===r[0]? " on":"";
      return '<div class="brow'+on+'" data-pick="topic" data-val="'+esc(r[0])+'">'+
        '<span class="nm">'+esc(r[2])+'</span>'+
        '<span class="track"><i class="fill" style="width:'+(r[1]/mx*100)+'%;background:#58a6ff"></i></span>'+
        '<span class="vl">'+r[1]+' 条</span></div>';
    }).join("") : '<div class="empty">当前 '+ITEMS.length+' 条均为媒体与官方物料，暂无关注点命中</div>'+
    '<div class="pnote">关注点由标题与正文关键词预标注，未经人工复核 —— 只用于「哪类话题被提及得多」，'+
    '不作为情感或问题结构结论。全部 '+ITEMS.length+' 条样本，人工复核后可去掉此提示。</div>');
}

/* ================= S4 渠道结构 =================
   规范：覆盖清单「必显」，占比榜「≥5 个有效平台才出」。
   原因：2–3 个平台下的百分比会被读成「用户分布」，实际只是采集能力的倒影。 */
var CH_MIN_PLAT = 5;
var CH_TARGET = {
  sw: [
    ["Creality 官方论坛","ok","用户声量主源 · 已接入"],
    ["GitHub","ok","缺陷单 · 可复现问题 · 已接入"],
    ["Reddit","todo","海外社区主战场 · 待接入"],
    ["B 站","todo","国内创作者实测 · 待接入"],
    ["YouTube","todo","海外视频评测 · 待接入"],
    ["知乎","todo","需登录态 Cookie"],
    ["什么值得买","blocked","风控 · 不可自动"],
    ["抖音 / 小红书","blocked","需签名 · 只探不采"]
  ],
  mbox: [
    ["B 站","ok","国内主源 · 2026-10-26 接入"],
    ["YouTube","ok","海外视频 · 已接入"],
    ["3druck","ok","德语 / 英文媒体 · 已接入"],
    ["Creality 官方论坛","todo","已接入 · 当前 0 条"],
    ["creality.com 官网","blocked","产品页探针 absent"],
    ["知乎","todo","需登录态 Cookie"],
    ["抖音","blocked","需签名 · 受限"],
    ["小红书","blocked","需签名 · 受限"]
  ]
};
var CH_ST = {ok:"已有数据",todo:"待接入",blocked:"不可自动"};
function barRowsPlain(rows,total){
  var mx = Math.max.apply(null, rows.map(function(r){return r[1];}).concat([1]));
  return rows.map(function(r){
    return '<div class="brow">'+
      '<span class="nm" title="'+esc(r[0])+'">'+esc(r[0])+'</span>'+
      '<span class="track"><i class="fill" style="width:'+(r[1]/mx*100)+'%;background:#58a6ff"></i></span>'+
      '<span class="vl">'+r[1]+' · '+(total?(r[1]/total*100).toFixed(1):"0.0")+'%</span></div>';
  }).join("");
}
function renderChannels(){
  var list = CH_TARGET[KIND] || CH_TARGET.mbox;
  var cnt = {};
  ITEMS.forEach(function(x){ var k = x.platform||"未知"; cnt[k]=(cnt[k]||0)+1; });
  var plats = Object.keys(cnt);
  var total = ITEMS.length || 1;
  var covered = list.filter(function(r){ return cnt[r[0]]; }).length;
  document.getElementById("chanHint").textContent =
    "覆盖 "+covered+" / "+list.length+" 个目标渠道 · 有效平台 "+plats.length+" 个";

  var rows = list.map(function(r){
    var n = cnt[r[0]]||0;
    var cls = n>0? "ok" : (r[1]==="blocked"? "blocked" : "todo");
    return '<div class="chan-row '+cls+(n?"":" zero")+'">'+
      '<span class="cn">'+esc(r[0])+'</span>'+
      '<span class="cst">'+CH_ST[cls]+'</span>'+
      '<span class="cnum">'+(n? n+' 条' : '—')+'</span>'+
      '<span class="cwhy">'+esc(r[2])+'</span></div>';
  }).join("");
  var cov = panel("渠道覆盖清单","目标渠道 × 当前覆盖 · 0 条即缺口 · 这是判断「要不要补信源」的依据", rows);
  if(KIND==="sw"){
    cov += panel("环节 × 信源覆盖","哪一段在哪个信源有内容 · 双源都没有的行才是真缺口", covMatrix());
  }
  document.getElementById("chanCover").innerHTML = cov;

  if(plats.length >= CH_MIN_PLAT){
    var arr = plats.map(function(k){ return [k,cnt[k]]; }).sort(function(a,b){ return b[1]-a[1]; });
    document.getElementById("chanShare").innerHTML =
      panel("渠道占比","全量口径 · 平台数已达 "+plats.length+" 个", barRowsPlain(arr,total));
  }else{
    document.getElementById("chanShare").innerHTML = panel("渠道占比","未达准入门槛 · 不渲染",
      '<div class="empty">当前仅 <b style="color:#c9d1d9">'+plats.length+'</b> 个信源（'+
      plats.map(function(k){ return esc(k)+' '+cnt[k]; }).join(' · ')+
      '），未达 '+CH_MIN_PLAT+' 个平台门槛，不出占比图。<br>'+
      '少数平台下的百分比会被读成「用户分布」，实际只是采集能力的倒影 —— 请以上方覆盖清单的缺口为准。</div>');
  }
}
'''

# ---------- 卡片：摘要 + 展开 + 分页器 ----------
NEW_CARD = r'''function clipTxt(s,n){
  s = String(s||"").replace(/\s+/g," ").trim();
  return s.length>n ? s.slice(0,n)+"…" : s;
}
/** 卡片摘要：先人工摘要，再译文，最后原文首句。目标是「不点开也知道这条在说什么」。 */
function summaryOf(it){
  if(it.summaryCn && String(it.summaryCn).trim()) return String(it.summaryCn).trim();
  var t = String(it.titleCn||it.title||"").trim();
  function firstSent(body, min){
    var m = body.match(/^[\s\S]{0,220}?[。！？!?]/);
    if(m && m[0].length>=min) return m[0];
    return body;
  }
  var cn = String(it.textCn||"").trim();
  if(cn) return clipTxt(firstSent(cn,40), 160);
  var raw = String(it.originalText||"").trim();
  if(raw.indexOf(t)===0) raw = raw.slice(t.length).trim();
  if(!raw) return clipTxt(t, 160);
  return clipTxt(firstSent(raw,40), 160);
}
function cardHTML(it){
  var cnT = it.titleCn || "", rawT = it.title || "";
  var title = cnT || rawT;
  var enT = cnT ? rawT : "";
  var sm = summaryOf(it);
  var full = it.originalText || "";
  var cnBody = it.textCn || "";
  var mt = (cnT===rawT || !enT) ? "" : "";
  return '<div class="card'+(it.countInVolume===false?" ghcard":"")+(it.grade==="泛讨论"?" gencard":"")+'" data-uid="'+esc(it.uid)+'">'+
    '<div class="c-top">'+tagsOf(it)+
      '<span class="c-date">'+esc(it.date)+'</span>'+
      '<span class="c-src">'+esc(it.platform)+'</span>'+
      (it.url? '<a class="c-link" href="'+esc(it.url)+'" target="_blank" rel="noopener">原文 ↗</a>':'')+
    '</div>'+
    '<div class="c-title">'+esc(title)+'</div>'+
    (enT? '<div class="c-title-en">'+esc(enT)+'</div>':'')+
    '<div class="c-sum">'+esc(sm)+'</div>'+
    ((full||cnBody)? '<div class="c-more" data-exp="1">展开全文 ▾</div>':'')+
    ((full||cnBody)? '<div class="fold">'+
      (full? '<div class="c-seg"><span class="seg-lb">原文 · '+esc(langOf(it))+'</span>'+
        '<span class="seg-tx">'+esc(full)+'</span></div>':'')+
      (cnBody? '<div class="c-seg"><span class="seg-lb">译文<span class="mt">机翻</span></span>'+
        '<span class="seg-tx cn">'+esc(cnBody)+'</span></div>':'')+
      '</div>':'')+
    (it.truncated? '<div class="cut">原文过长已截断（保留前 1,200 字），完整内容见原帖。</div>':'')+
  '</div>';
}
function renderCards(){
  var list = apply();
  var pages = Math.max(1, Math.ceil(list.length / PAGE_SZ));
  if(S.page > pages) S.page = pages;
  var start = (S.page-1)*PAGE_SZ;
  var slice = list.slice(start, start+PAGE_SZ);
  document.getElementById("cardGrid").innerHTML = slice.length
    ? slice.map(cardHTML).join("")
    : '<div class="panel"><div class="empty">当前筛选条件下没有条目。<br>试着清空条件，或把时间范围放宽。</div></div>';

  var ghN = list.filter(function(x){ return x.countInVolume===false; }).length;
  document.getElementById("countLine").textContent =
    "共 "+list.length+" 条"+(ghN? "（含 GitHub 缺陷单 "+ghN+" 条）":"")+
    " · 第 "+S.page+" / "+pages+" 页 · 每页 "+PAGE_SZ+" 条";
  document.getElementById("flowHint").textContent =
    "每条给摘要，展开看原文与机翻 · 上方面板与这里筛选同源";

  var opts = "";
  for(var i=1;i<=pages;i++) opts += '<option value="'+i+'"'+(i===S.page?" selected":"")+'>第 '+i+' 页</option>';
  var h = "";
  h += '<button data-pg="'+(S.page-1)+'"'+(S.page<=1?" disabled":"")+'>上一页</button>';
  h += '<select class="pgsel" data-pgsel="1" title="选择页码直接跳转">'+opts+'</select>';
  h += '<span class="pg">共 '+pages+' 页</span>';
  h += '<button data-pg="'+(S.page+1)+'"'+(S.page>=pages?" disabled":"")+'>下一页</button>';
  document.getElementById("pager").innerHTML = h;
  return list;
}
'''

OLD_PANELS_PAT = re.compile(r'function renderPanels\(\)\{[\s\S]*?\n\}\n\n/\* -+ 筛选栏 -+ \*/')
OLD_CARD_PAT = re.compile(r'function cardHTML\(it\)\{[\s\S]*?\n\}\nfunction renderCards\(\)\{[\s\S]*?\n\}\n\n/\* -+ 页脚 -+ \*/')


def patch_css2(s):
    if "pgsel" in s:
        return s, "css2:skip"
    s = s.replace("</style>", CSS2.strip(), 1)
    return s, "css2:ok"


def patch_s_def(s):
    old = 'stage:"",toolType:"",range:"all",q:"",page:1};'
    new = 'stage:"",toolType:"",topic:"",range:"all",q:"",page:1};'
    if new in s:
        return s, "S:skip"
    if old not in s:
        return s, "S:NO-MATCH"
    return s.replace(old, new, 1), "S:ok"


def patch_match(s):
    old = '  if(skip!=="toolType" && S.toolType && (it.toolType || "__none__") !== S.toolType) return false;'
    new = old + '\n  if(skip!=="topic" && S.topic && !topicHit(it, S.topic)) return false;'
    if 'skip!=="topic"' in s:
        return s, "match:skip"
    if old not in s:
        return s, "match:NO-MATCH"
    return s.replace(old, new, 1), "match:ok"


def patch_labels(s):
    old = 'stage:"环节",toolType:"工具类型"};'
    new = 'stage:"环节",toolType:"工具类型",topic:"关注点"};'
    if new in s:
        return s, "lbl:skip"
    if old not in s:
        return s, "lbl:NO-MATCH"
    return s.replace(old, new, 1), "lbl:ok"


def patch_clearall(s):
    old = '"stage","toolType"].forEach(function(k){S[k]="";});'
    new = '"stage","toolType","topic"].forEach(function(k){S[k]="";});'
    if new in s:
        return s, "clr:skip"
    if old not in s:
        return s, "clr:NO-MATCH"
    return s.replace(old, new, 1), "clr:ok"


def patch_panels(s):
    if "function renderOverview()" in s:
        return s, "panels:skip"
    if not OLD_PANELS_PAT.search(s):
        return s, "panels:NO-MATCH"
    s = OLD_PANELS_PAT.sub(lambda m: NEW_PANELS.strip() + "\n\n/* ---------------- 筛选栏 ---------------- */", s, count=1)
    return s, "panels:ok"


def patch_card(s):
    if "function summaryOf(it)" in s:
        return s, "card:skip"
    if not OLD_CARD_PAT.search(s):
        return s, "card:NO-MATCH"
    s = OLD_CARD_PAT.sub(lambda m: NEW_CARD.strip() + "\n\n/* ---------------- 页脚 ---------------- */", s, count=1)
    return s, "card:ok"


def patch_renderall(s):
    old = "  renderUpdateBar(); renderKPI(); renderPanels(); renderFilters();"
    new = ("  renderUpdateBar(); renderKPI(); renderOverview(); renderTopics(); renderChannels(); renderFilters();")
    if new in s:
        return s, "all:skip"
    if old not in s:
        return s, "all:NO-MATCH"
    return s.replace(old, new, 1), "all:ok"


def patch_events(s):
    # 展开全文
    anchor = '  if(e.target.id==="clearAllBtn"){ clearAll(); }'
    if 'closest("[data-exp]")' not in s:
        addex = ('  var ex = e.target.closest("[data-exp]");\n'
                 '  if(ex){ var cd = ex.closest(".card"); if(cd){ cd.classList.toggle("open");\n'
                 '    ex.textContent = cd.classList.contains("open") ? "收起 ▴" : "展开全文 ▾"; } return; }\n')
        if anchor in s:
            s = s.replace(anchor, addex + anchor, 1)
    # 页码下拉
    if 'getAttribute("data-pgsel")' not in s:
        poly = ('  var ps = e.target.getAttribute && e.target.getAttribute("data-pgsel");\n'
                '  if(ps){ S.page = parseInt(e.target.value,10)||1; renderAll(); return; }\n')
        oldch = 'document.addEventListener("change",function(e){\n'
        if oldch in s:
            s = s.replace(oldch, oldch + poly, 1)
    return s, "evt:ok"


def main():
    for f in TARGETS:
        raw = io.open(f, encoding="utf-8").read()
        s = raw
        reps = []
        for fn in (patch_css2, patch_s_def, patch_match, patch_labels, patch_clearall,
                   patch_panels, patch_card, patch_renderall, patch_events):
            s, r = fn(s)
            reps.append(r)
        if s != raw:
            io.open(f, "w", encoding="utf-8").write(s)
        print("%-26s %s  changed=%s" % (f, " ".join(reps), s != raw))


if __name__ == "__main__":
    main()

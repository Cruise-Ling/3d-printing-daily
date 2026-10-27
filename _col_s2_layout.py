# -*- coding: utf-8 -*-
"""S2 概览左右并排 + 明细流渠道筛选器（作用对象：_col_shell.html 模板）"""
import io, re

F = "_col_shell.html"
s = io.open(F, encoding="utf-8").read()
o = s

# ---------------- 1) DOM：两个 grid-2 容器合成一个 ----------------
old_dom = '''  <div class="grid-2" id="ovA"></div>
  <div class="grid-2" id="ovB"></div>'''
new_dom = '''  <div class="grid-s2" id="ovA"></div>'''
assert old_dom in s
s = s.replace(old_dom, new_dom, 1)

# ---------------- 2) CSS ----------------
css_anchor = ".grid-2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}"
assert css_anchor in s
s = s.replace(css_anchor, css_anchor + '''
/* S2 概览容器：原设计是两个独立 .grid-2，各只放 1 个面板 -> 各占半宽、右侧留白、上下堆叠。
   合并成一个容器后两面板并排。软件专栏用不对称比例（0.85 : 1.35）给「工具 × 环节」矩阵留够列宽，
   其余专栏维持 1:1。断点 900（原 .grid-2 是 1100，1024 视口会被误判成窄屏）。 */
.grid-s2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;align-items:start}
.grid-s2.asym{grid-template-columns:minmax(0,.85fr) minmax(0,1.35fr)}
@media(max-width:900px){.grid-s2,.grid-s2.asym{grid-template-columns:1fr}}
/* 矩阵面板在窄容器里的保护：行名不折行，超宽可横向滑动而不是被裁掉 */
.mx-wrap{overflow-x:auto}
table.mx td:first-child{white-space:nowrap}''', 1)

# 渠道筛选按钮组
s = s.replace(".filters{display:flex;",
  '''.btnset{display:flex;flex-wrap:wrap;gap:6px}
.fbtn{background:#0d1117;color:#8b949e;border:1px solid #30363d;border-radius:6px;padding:5px 10px;font-size:11.5px;cursor:pointer;white-space:nowrap;font-family:inherit}
.fbtn:hover{border-color:#58a6ff;color:#c9d1d9}
.fbtn.on{background:rgba(88,166,255,.15);border-color:rgba(88,166,255,.55);color:#79c0ff;font-weight:600}
.filters{display:flex;''', 1)

# ---------------- 3) renderOverview：字符串收集后合并 ----------------
start = s.find("function renderOverview(){")
end = s.find("\n/* ================= S3 专项分析 =================", start)
assert start > 0 and end > start
body = s[start:end]

body = body.replace(
  '  var A=document.getElementById("ovA"), B=document.getElementById("ovB");',
  '''  // 两个面板组先各自拼字符串，最后并入同一个网格 —— 否则两个独立 grid 容器会各占半宽并上下堆叠
  var A=document.getElementById("ovA"), hA="", hB="";''', 1)

body = re.sub(r"A\.innerHTML\s*\+=\s*", "hA += ", body)
body = re.sub(r"A\.innerHTML\s*=\s*", "hA += ", body)
body = re.sub(r"B\.innerHTML\s*\+=\s*", "hB += ", body)
body = re.sub(r"B\.innerHTML\s*=\s*", "hB += ", body)

# 函数末尾统一落盘（替换最后一个独占的 }）
assert body.rstrip().endswith("}")
tail = '''
  // 软件专栏矩阵列多，单独给不对称比例；其余专栏维持 1:1
  A.className = "grid-s2" + (KIND==="sw" ? " asym" : "");
  A.innerHTML = hA + hB;
}'''
body = body.rstrip()
body = body[:body.rfind("}")] + tail + "\n"
s = s[:start] + body + s[end:]

# ---------------- 4) 状态与匹配：新增 platform ----------------
s = s.replace(
  '''var S = {product:"",problem:"",model:"",grade:"",channel:"",source:"",lang:"",
         stage:"",toolType:"",topic:"",range:"all",q:"",page:1,tech:"",level:""};''',
  '''var S = {product:"",problem:"",model:"",grade:"",channel:"",source:"",lang:"",
         stage:"",toolType:"",topic:"",range:"all",q:"",page:1,tech:"",level:"",
         // 2026-10-27 用户要求：明细流要有「具体渠道」筛选器（YouTube / Reddit / B站…），
         // 与 channel（国内/海外）、source（信源类型）是三个不同维度，不能混用。
         platform:""};''', 1)

# 平台名归一：K3 写「B 站」、采集器写「B站」，中间空格不同会被拆成两个渠道
s = s.replace('''function uniq(a){''',
'''// 平台名归一：不同采集器输出的 "B 站" / "B站" 必须合并，否则渠道筛选器里会出现两个 B 站
function platOf(it){
  return String((it&&it.platform)||"未标注").replace(/\\s+/g,"") === "B站" ? "B站"
       : String((it&&it.platform)||"未标注").trim();
}
function uniq(a){''', 1)

s = s.replace('''  if(skip!=="source" && S.source && (it.sourceType||"未知")!==S.source) return false;''',
'''  if(skip!=="source" && S.source && (it.sourceType||"未知")!==S.source) return false;
  if(skip!=="platform" && S.platform && platOf(it)!==S.platform) return false;''', 1)

# ---------------- 5) 筛选栏：渠道按钮组（三页统一） ----------------
s = s.replace('''function renderFilters(){
  var el = document.getElementById("filters"), h = "";''',
'''/* 渠道按钮组：一行放「全部 + 各渠道条数」，单击即筛、再点取消。
   用按钮而不是下拉 —— 用户要的是「一眼看到有哪些渠道、各多少条，直接点进去」，
   下拉要先展开才知道有什么。渠道数量最多 7 个，一行放得下。 */
function platBtns(){
  var base = ITEMS.filter(function(x){ return match(x, "platform"); });
  var m = {};
  base.forEach(function(x){ var p = platOf(x); m[p] = (m[p]||0)+1; });
  var keys = Object.keys(m).sort(function(a,b){ return m[b]-m[a]; });
  var btn = function(val, label, n){
    return '<button class="fbtn'+(S.platform===val?" on":"")+'" data-plat="'+esc(val)+'">'+
      esc(label)+' '+n+'</button>';
  };
  return '<div class="fg" style="align-items:flex-start"><label style="padding-top:5px">渠道</label>'+
    '<div class="btnset">'+btn("", "全部", base.length)+
    keys.map(function(k){ return btn(k, k, m[k]); }).join("")+
    '</div></div>';
}
function renderFilters(){
  var el = document.getElementById("filters"), h = "";
  // 渠道筛选器固定排在第一位：它是用户最常切的维度
  h += platBtns() + '<div class="break" style="flex-basis:100%;height:0"></div>';''', 1)

# ---------------- 6) 已选条件摘要 ----------------
s = s.replace('''              stage:"环节",toolType:"工具类型",topic:"议题",tech:"档次",level:"讨论度"};''',
'''              stage:"环节",toolType:"工具类型",topic:"议题",tech:"档次",level:"讨论度",
              platform:"渠道"};''', 1)

io.open(F, "w", encoding="utf-8", newline="\n").write(s)
print("模板 S2 布局 + 渠道筛选器 完成 %d 字符" % len(s))
